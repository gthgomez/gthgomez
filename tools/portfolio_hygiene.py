#!/usr/bin/env python3
"""Portfolio hygiene checker (offline, deterministic, standard library only).

Implements the rules H001-H008 from DESIGNS/HYGIENE_CHECKER_SPEC.md in the
portfolio audit packet. This checker:

  * never executes README snippets, workflow contents, or any URL;
  * never touches the network (remote probing is a separate trusted mode
    that does not exist yet);
  * reads only files inside the repository given via --repo.

CLI:
    python tools/portfolio_hygiene.py check --repo PATH --config PATH \
        [--format text|json] [--head SHA]

Exit codes:
    0  no blocking or warning findings
    1  findings present (exempt suppressions do not count)
    2  invalid configuration or tool failure
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from typing import Any

SCHEMA_VERSION = 1

# Truth/status vocabulary from DESIGNS/TRUTH_STATUS.md (evidence receipt v1).
CHECK_STATES = {"PASS", "FAIL", "BLOCKED", "NOT_RUN", "UNKNOWN", "INCONCLUSIVE"}
NON_GREEN_STATES = {"FAIL", "BLOCKED", "NOT_RUN", "UNKNOWN", "INCONCLUSIVE"}

RECEIPT_REQUIRED_FIELDS = (
    "schema_version",
    "repository",
    "source_sha",
    "generated_at_utc",
    "producer",
    "exit_code",
    "checks",
    "artifact_hashes",
    "limitations",
)

COMMAND_REQUIRED_FIELDS = (
    "id",
    "argv",
    "cwd",
    "allowed_env",
    "network",
    "output_artifact",
)

MANIFEST_REQUIRED_FIELDS = (
    "schema_version",
    "repository",
    "project_type",
    "maturity",
    "source_visibility_policy",
    "license_path",
    "default_branch",
    "supported_toolchains",
    "approved_commands",
    "evidence_links",
    "release_policy",
    "cross_repo_dependencies",
    "flagship_role",
)

SEVERITY_ORDER = {"blocking": 0, "warning": 1, "exempt": 2}

# Workstation/private-path indicators (H001).
PRIVATE_PATH_PATTERNS = [
    (re.compile(r"file:///?", re.IGNORECASE), "file:// URL"),
    (re.compile(r"\b[A-Za-z]:\\[A-Za-z0-9_\- .\\]+"), "Windows drive path"),
    (re.compile(r"(?<![A-Za-z0-9])/Users/[A-Za-z0-9_\- .]+"), "macOS home path"),
    (re.compile(r"(?<![A-Za-z0-9])/home/[A-Za-z0-9_\- .]+"), "Linux home path"),
]

# Volatile prose (H007): counts/coverage/prices that drift.
VOLATILE_PATTERNS = [
    (re.compile(r"\b\d{2,}\s+(?:passing|failing|unit|integration|conformance)\s+tests?\b", re.IGNORECASE),
     "test count in prose"),
    (re.compile(r"\b\d+(?:\.\d+)?%\s+(?:test\s+)?coverage\b", re.IGNORECASE),
     "coverage percentage in prose"),
    (re.compile(r"\$\d+(?:\.\d+)?\s*(?:per|/)\s*(?:1[MK]|M|K)?\s*tokens?\b", re.IGNORECASE),
     "model price in prose"),
]

MARKDOWN_LINK_RE = re.compile(r"(!?)\[([^\]]*)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
BADGE_WORKFLOW_RE = re.compile(r"/workflows/([A-Za-z0-9._\-]+)\.ya?ml/badge\.svg")


class CheckerError(Exception):
    """Invalid configuration or tool failure (exit 2)."""


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def git_head(repo: str) -> str | None:
    try:
        out = subprocess.run(
            ["git", "-C", repo, "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=15, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if out.returncode != 0:
        return None
    return out.stdout.strip() or None


class Report:
    def __init__(self) -> None:
        self.findings: list[dict[str, Any]] = []
        self.errors: list[str] = []
        self.rules_run: set[str] = set()
        self.files_scanned = 0

    def add(self, rule_id: str, severity: str, path: str, line: int,
            message: str, evidence: str, suppression: dict | None = None) -> None:
        self.findings.append({
            "rule_id": rule_id,
            "severity": severity if suppression is None else "exempt",
            "path": path.replace("\\", "/"),
            "line": line,
            "message": message,
            "evidence": evidence[:200],
            "suppression": suppression,
        })
        self.rules_run.add(rule_id)

    def finalize(self, repo: str, inspected_source: str) -> dict:
        self.findings.sort(key=lambda f: (f["path"], f["line"],
                                          f["rule_id"], f["message"]))
        return {
            "schema_version": SCHEMA_VERSION,
            "repo": repo,
            "inspected_source": inspected_source,
            "findings": self.findings,
            "coverage": {
                "rules_run": sorted(self.rules_run),
                "files_scanned": self.files_scanned,
            },
            "errors": sorted(self.errors),
        }


def load_config(path: str) -> dict:
    if not os.path.isfile(path):
        raise CheckerError(f"config file not found: {path}")
    try:
        with open(path, "r", encoding="utf-8") as f:
            config = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        raise CheckerError(f"config not readable JSON: {exc}") from exc
    if not isinstance(config, dict):
        raise CheckerError("config must be a JSON object")
    missing = [k for k in MANIFEST_REQUIRED_FIELDS if k not in config]
    if missing:
        raise CheckerError("config missing required fields: " + ", ".join(missing))
    if config["schema_version"] != 1:
        raise CheckerError(f"unsupported schema_version: {config['schema_version']!r}")
    if not isinstance(config["approved_commands"], list):
        raise CheckerError("approved_commands must be a list")
    if not isinstance(config["evidence_links"], list):
        raise CheckerError("evidence_links must be a list")
    return config


def suppression_for(config: dict, rule_id: str, rel_path: str) -> dict | None:
    for sup in config.get("suppressions", []):
        if sup.get("rule_id") == rule_id and sup.get("path") == rel_path:
            if not sup.get("reason") or not sup.get("owner"):
                continue  # malformed suppression: ignore, do not exempt
            return sup
    return None


# ---------------------------------------------------------------- H001
def check_private_paths(report: Report, config: dict, repo: str,
                        doc_files: list[str]) -> None:
    for rel in doc_files:
        with open(os.path.join(repo, rel), "r", encoding="utf-8", errors="replace") as f:
            for lineno, line in enumerate(f, 1):
                for pattern, kind in PRIVATE_PATH_PATTERNS:
                    m = pattern.search(line)
                    if m:
                        sup = suppression_for(config, "H001", rel)
                        report.add("H001", "blocking", rel, lineno,
                                   f"{kind} in public documentation",
                                   line.strip(), sup)
                        break


# ---------------------------------------------------------------- H002/H003
def strip_fenced(text: str) -> str:
    out = []
    fence = re.compile(r"^\s*(```|~~~)")
    in_fence = False
    marker = ""
    for line in text.splitlines():
        m = fence.match(line)
        if not in_fence and m:
            in_fence = True
            marker = m.group(1)
            continue
        if in_fence and line.strip().startswith(marker):
            in_fence = False
            continue
        if not in_fence:
            out.append(line)
    return "\n".join(out)


def github_anchor(text: str) -> str:
    slug = text.strip().lower()
    slug = re.sub(r"[^\w\- ]", "", slug)
    slug = slug.replace(" ", "-")
    return slug


def collect_anchors(md_text: str) -> set[str]:
    anchors: set[str] = {}
    for line in strip_fenced(md_text).splitlines():
        m = HEADING_RE.match(line)
        if m:
            base = github_anchor(m.group(2))
            n = anchors.get(base, 0)
            anchors[base] = n + 1
    result = set()
    for base, count in anchors.items():
        result.add(base)
        for i in range(1, count):
            result.add(f"{base}-{i}")
    return result


def check_links(report: Report, config: dict, repo: str, doc_files: list[str]) -> None:
    # Preload markdown targets for fragment checks.
    md_cache: dict[str, set[str]] = {}
    for rel in doc_files:
        norm = rel.lower()
        if norm not in md_cache:
            with open(os.path.join(repo, rel), "r", encoding="utf-8",
                      errors="replace") as f:
                md_cache[norm] = collect_anchors(f.read())

    for rel in doc_files:
        base_dir = os.path.dirname(os.path.join(repo, rel))
        with open(os.path.join(repo, rel), "r", encoding="utf-8",
                  errors="replace") as f:
            text = strip_fenced(f.read())
        for lineno, line in enumerate(text.splitlines(), 1):
            for _img, _label, target in MARKDOWN_LINK_RE.findall(line):
                # H003 applies to badge URLs too (they name a workflow file
                # that must exist locally); network fetching stays out of scope.
                m = BADGE_WORKFLOW_RE.search(target)
                if m:
                    wf = os.path.join(repo, ".github", "workflows", m.group(1) + ".yml")
                    wf_yml = os.path.join(repo, ".github", "workflows", m.group(1) + ".yaml")
                    if not os.path.isfile(wf) and not os.path.isfile(wf_yml):
                        report.add("H003", "blocking", rel, lineno,
                                   "workflow badge references a workflow file that "
                                   "does not exist in this checkout", target)
                if target.startswith(("http://", "https://", "mailto:", "<")):
                    continue  # network checking is out of scope here
                path_part, _, frag = target.partition("#")
                path_part = path_part.strip()
                if not path_part:
                    continue  # same-document fragment
                decoded = path_part.replace("%20", " ")
                if decoded.startswith("file:"):
                    sup = suppression_for(config, "H001", rel)
                    report.add("H001", "blocking", rel, lineno,
                               "file:// URL in markdown link", target, sup)
                    continue
                if os.path.isabs(decoded) or decoded.startswith("\\\\"):
                    report.add("H002", "blocking", rel, lineno,
                               "absolute path link in public docs", target)
                    continue
                resolved = os.path.normpath(os.path.join(base_dir, decoded))
                repo_root = os.path.abspath(repo)
                if not resolved.startswith(repo_root + os.sep) and resolved != repo_root:
                    report.add("H002", "blocking", rel, lineno,
                               "link escapes the public checkout", target)
                    continue
                exists_ci, exact_case = resolve_link_target(repo_root, resolved)
                if exists_ci:
                    if not exact_case:
                        report.add("H002", "blocking", rel, lineno,
                                   "link target exists but with different case "
                                   "(breaks on case-sensitive filesystems)",
                                   target)
                        continue
                else:
                    report.add("H002", "blocking", rel, lineno,
                               "relative link target not found", target)
                    continue
                if frag:
                    rel_target = os.path.relpath(resolved, repo_root).replace("\\", "/")
                    key = rel_target.lower()
                    if key not in md_cache and rel_target.lower().endswith(DOC_EXTENSIONS):
                        try:
                            with open(resolved, "r", encoding="utf-8",
                                      errors="replace") as f:
                                md_cache[key] = collect_anchors(f.read())
                        except OSError:
                            md_cache[key] = set()
                    anchors = md_cache.get(key)
                    if anchors is not None and frag not in anchors:
                        report.add("H002", "blocking", rel, lineno,
                                   "markdown anchor not found in target document",
                                   target)


def resolve_link_target(repo_root: str, resolved: str) -> tuple[bool, bool]:
    """Walks the path components and returns (exists_case_insensitively, exact_case_match).

    Works identically on case-insensitive (Windows, macOS) and case-sensitive (Linux)
    filesystems by inspecting directory entry lists.
    """
    cur = os.path.abspath(repo_root)
    rel = os.path.relpath(os.path.abspath(resolved), cur)
    if rel.startswith(".."):
        return (False, False)
    exact = True
    for part in rel.split(os.sep):
        try:
            entries = os.listdir(cur)
        except OSError:
            return (False, False)
        if part in entries:
            cur = os.path.join(cur, part)
        else:
            part_lower = part.lower()
            matches = [e for e in entries if e.lower() == part_lower]
            if not matches:
                return (False, False)
            exact = False
            cur = os.path.join(cur, matches[0])
    return (True, exact)


# ---------------------------------------------------------------- H004
def check_license_policy(report: Report, config: dict, repo: str) -> None:
    license_path = config["license_path"]
    policy = config["source_visibility_policy"]
    if not os.path.isfile(os.path.join(repo, license_path)):
        report.add("H004", "blocking", license_path, 0,
                   "configured license file is missing", license_path)
        return
    with open(os.path.join(repo, license_path), "r", encoding="utf-8",
              errors="replace") as f:
        text = f.read(20000).lower()
    oss_markers = ("mit license", "apache license", "bsd ", "gpl", "mozilla public")
    is_oss_license = any(m in text for m in oss_markers)
    proprietary_claim = "proprietary" in policy or "all rights reserved" in policy
    if proprietary_claim and is_oss_license:
        report.add("H004", "blocking", license_path, 0,
                   "license file looks like an open-source license but the "
                   "manifest declares a proprietary source-visibility policy",
                   policy)
    if not proprietary_claim and not is_oss_license and policy not in ("none",):
        report.add("H004", "blocking", license_path, 0,
                   "license file does not match the declared open-source policy",
                   policy)
    if config.get("require_security_reporting"):
        if not (os.path.isfile(os.path.join(repo, "SECURITY.md"))
                or config.get("security_reporting_path")):
            report.add("H004", "blocking", "SECURITY.md", 0,
                       "sensitive repository requires a security-reporting path",
                       "")


# ---------------------------------------------------------------- H005
def check_versions(report: Report, config: dict, repo: str) -> None:
    for vc in config.get("version_checks", []):
        try:
            rel = vc["file"]
            domain = vc.get("domain", "unknown")
            status = vc.get("status", "unreleased")
            expect = vc.get("expected_version")
        except (KeyError, TypeError):
            raise CheckerError("version_checks entry missing 'file'") from None
        full = os.path.join(repo, rel)
        if not os.path.isfile(full):
            report.add("H005", "blocking", rel, 0,
                       f"version source for domain '{domain}' is missing", rel)
            continue
        with open(full, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        actual = None
        if "json_pointer" in vc:
            try:
                data = json.loads(content)
                for part in vc["json_pointer"].lstrip("/").split("/"):
                    data = data[part]
                actual = str(data)
            except (json.JSONDecodeError, KeyError, TypeError) as exc:
                report.add("H005", "blocking", rel, 0,
                           "version source is not readable JSON at the "
                           "configured pointer", str(exc))
                continue
        else:
            m = re.search(vc.get("pattern", r"(.*)"), content)
            if m:
                actual = m.group(1).strip()
        if actual is None:
            report.add("H005", "blocking", rel, 0,
                       "version value not found in declared source", rel)
            continue
        if status == "released" and expect is not None and actual != expect:
            report.add("H005", "blocking", rel, 0,
                       f"version in domain '{domain}' ({actual}) does not match "
                       f"the released version ({expect}); unreleased development "
                       "versions must be declared status=unreleased",
                       f"{actual} != {expect}")


# ---------------------------------------------------------------- H006
def check_evidence(report: Report, config: dict, repo: str, head: str | None) -> None:
    for entry in config.get("evidence_links", []):
        if isinstance(entry, str):
            entry = {"path": entry, "current": False}
        rel = entry.get("path")
        if not rel:
            raise CheckerError("evidence_links entry missing 'path'")
        full = os.path.join(repo, rel)
        current = bool(entry.get("current", False))
        if not os.path.isfile(full):
            report.add("H006", "blocking", rel, 0,
                       "linked evidence receipt file is missing", rel)
            continue
        try:
            with open(full, "r", encoding="utf-8") as f:
                receipt = json.load(f)
        except (OSError, json.JSONDecodeError) as exc:
            report.add("H006", "blocking", rel, 0,
                       "evidence receipt is not valid JSON", str(exc))
            continue
        missing = [k for k in RECEIPT_REQUIRED_FIELDS if k not in receipt]
        if missing:
            report.add("H006", "blocking", rel, 0,
                       "evidence receipt missing required fields: "
                       + ", ".join(missing), ", ".join(missing))
            continue
        checks = receipt.get("checks")
        if not isinstance(checks, list) or not checks:
            report.add("H006", "blocking", rel, 0,
                       "evidence receipt has no checks; an empty receipt must "
                       "not imply PASS", "checks")
            continue
        for chk in checks:
            state = chk.get("state")
            if state is None:
                report.add("H006", "blocking", rel, 0,
                           "check without explicit state; no omitted check "
                           "defaults to PASS",
                           json.dumps(chk.get("name", "?")))
            elif state not in CHECK_STATES:
                report.add("H006", "blocking", rel, 0,
                           f"check state '{state}' is outside the truth-status "
                           "vocabulary", json.dumps(chk.get("name", "?")))
            elif state in NON_GREEN_STATES and current:
                report.add("H006", "blocking", rel, 0,
                       f"current evidence claims success while check "
                       f"'{chk.get('name', '?')}' is {state}; UNKNOWN/NOT_RUN/FAIL "
                       "must never render as green",
                       json.dumps(chk.get("name", "?")))
        # Digest verification for artifacts present in the checkout.
        for art_rel, digest in (receipt.get("artifact_hashes") or {}).items():
            art_full = os.path.normpath(os.path.join(repo, art_rel))
            if not art_full.startswith(os.path.abspath(repo) + os.sep):
                report.add("H006", "blocking", rel, 0,
                           "artifact hash entry escapes the repository", art_rel)
                continue
            if not os.path.isfile(art_full):
                report.add("H006", "blocking", rel, 0,
                           "receipt references an artifact that does not exist",
                           art_rel)
                continue
            actual = sha256_file(art_full)
            if actual != digest:
                report.add("H006", "blocking", rel, 0,
                           "artifact digest mismatch", art_rel)
        # Stale purported current proof.
        if current and head and receipt.get("source_sha") != head:
            report.add("H006", "blocking", rel, 0,
                       "receipt marked current does not match the inspected "
                       "source SHA; a cached PASS stays historical and must not "
                       "be recertified for a new SHA",
                       f"{receipt.get('source_sha')} != {head}")


# ---------------------------------------------------------------- H007
def check_volatile_prose(report: Report, config: dict, repo: str,
                         doc_files: list[str]) -> None:
    generated_markers = tuple(config.get("generated_doc_markers", []))
    for rel in doc_files:
        with open(os.path.join(repo, rel), "r", encoding="utf-8",
                  errors="replace") as f:
            head = f.read(200)
        is_generated = head.startswith(generated_markers) if generated_markers else False
        if is_generated:
            continue
        with open(os.path.join(repo, rel), "r", encoding="utf-8",
                  errors="replace") as f:
            for lineno, line in enumerate(strip_fenced(f.read()).splitlines(), 1):
                for pattern, kind in VOLATILE_PATTERNS:
                    if pattern.search(line):
                        sup = suppression_for(config, "H007", rel)
                        report.add("H007", "warning", rel, lineno,
                                   f"{kind} drifts unless generated or attached "
                                   "to immutable dated evidence",
                                   line.strip(), sup)
                        break


# ---------------------------------------------------------------- H008
def check_commands(report: Report, config: dict, repo: str) -> None:
    for cmd in config["approved_commands"]:
        missing = [k for k in COMMAND_REQUIRED_FIELDS if k not in cmd]
        if missing:
            raise CheckerError(
                f"approved command entry missing fields: {', '.join(missing)}")
        if cmd.get("network") not in ("none",):
            raise CheckerError(
                f"approved command '{cmd['id']}' must declare network=none; "
                "networked verification is a separate trusted mode")
        argv = cmd["argv"]
        if not isinstance(argv, list) or not argv:
            raise CheckerError(f"approved command '{cmd['id']}' argv must be a non-empty list")
        cwd = os.path.join(repo, cmd.get("cwd", "."))
        # The checker does not execute commands. It only verifies that the
        # registry references things that exist: npm/pnpm script names against
        # package.json, and repository file arguments against the checkout.
        for i, token in enumerate(argv):
            if i > 0 and argv[i - 1] in ("run",) and os.path.isfile(os.path.join(cwd, "package.json")):
                try:
                    with open(os.path.join(cwd, "package.json"), "r", encoding="utf-8") as f:
                        scripts = json.load(f).get("scripts", {})
                except (OSError, json.JSONDecodeError):
                    scripts = {}
                if token not in scripts:
                    report.add("H008", "blocking", "portfolio-manifest.json", 0,
                               f"approved command '{cmd['id']}' references npm "
                               f"script '{token}' that package.json does not "
                               "define", token)
                continue
            if isinstance(token, str) and re.match(r"^[\w./\-]+\.(py|json|md|ya?ml|toml|gradle|kts)$", token):
                if not os.path.isfile(os.path.join(cwd, token)):
                    report.add("H008", "blocking", "portfolio-manifest.json", 0,
                               f"approved command '{cmd['id']}' references a file "
                               "that does not exist in the checkout", token)


DOC_EXTENSIONS = (".md", ".markdown")


def doc_files_for(config: dict, repo: str) -> list[str]:
    """Docs under public entrypoints, deterministically ordered."""
    entries = config.get("public_entrypoints")
    if not isinstance(entries, list) or not entries:
        raise CheckerError("config missing non-empty 'public_entrypoints' list")
    files: set[str] = set()
    for entry in entries:
        full = os.path.join(repo, entry)
        if os.path.isdir(full):
            for root, _dirs, names in os.walk(full):
                for name in sorted(names):
                    if name.lower().endswith(DOC_EXTENSIONS):
                        files.add(os.path.relpath(
                            os.path.join(root, name), repo).replace("\\", "/"))
        elif os.path.isfile(full) and entry.lower().endswith(DOC_EXTENSIONS):
            files.add(entry.replace("\\", "/"))
    return sorted(files)


def run_check(repo: str, config_path: str, fmt: str, head_override: str | None) -> int:
    try:
        config = load_config(config_path)
    except CheckerError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    repo = os.path.abspath(repo)
    if not os.path.isdir(repo):
        print(f"ERROR: repo path not found: {repo}", file=sys.stderr)
        return 2

    head = head_override or git_head(repo)
    report = Report()
    try:
        docs = doc_files_for(config, repo)
        report.files_scanned = len(docs)
        check_private_paths(report, config, repo, docs)
        check_links(report, config, repo, docs)
        check_license_policy(report, config, repo)
        check_versions(report, config, repo)
        check_evidence(report, config, repo, head)
        check_volatile_prose(report, config, repo, docs)
        check_commands(report, config, repo)
    except CheckerError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    inspected = head or "no-git-metadata"
    result = report.finalize(repo, inspected)
    blocking = [f for f in result["findings"] if f["severity"] == "blocking"]
    warnings = [f for f in result["findings"] if f["severity"] == "warning"]
    if fmt == "json":
        print(json.dumps(result, indent=2, sort_keys=False))
    else:
        print(f"repo: {repo}")
        print(f"inspected_source: {inspected}")
        print(f"blocking findings: {len(blocking)}  warnings: {len(warnings)}  "
              f"exempt: {len(result['findings']) - len(blocking) - len(warnings)}")
        for f in result["findings"]:
            loc = f"{f['path']}:{f['line']}" if f["line"] else f["path"]
            print(f"  [{f['severity']}] {f['rule_id']} {loc}: {f['message']}")
            if f["evidence"]:
                print(f"      evidence: {f['evidence']}")
    if blocking or warnings:
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    p_check = sub.add_parser("check", help="run hygiene checks against a repo")
    p_check.add_argument("--repo", required=True, help="path to repository checkout")
    p_check.add_argument("--config", required=True, help="path to portfolio-manifest.json")
    p_check.add_argument("--format", choices=("text", "json"), default="text")
    p_check.add_argument("--head", default=None,
                         help="override inspected source SHA (for deterministic tests)")
    args = parser.parse_args(argv)
    if args.command == "check":
        return run_check(args.repo, args.config, args.format, args.head)
    return 2


if __name__ == "__main__":
    sys.exit(main())
