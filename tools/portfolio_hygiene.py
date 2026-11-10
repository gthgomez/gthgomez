#!/usr/bin/env python3
"""Portfolio hygiene checker (offline, deterministic, standard library only).

Implements the rules H001-H009 from DESIGNS/HYGIENE_CHECKER_SPEC.md in the
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
import html
import json
import os
import re
import struct
import subprocess
import sys
import xml.etree.ElementTree as ET
from typing import Any
from urllib.parse import unquote

SCHEMA_VERSION = 1

# Truth/status vocabulary from DESIGNS/TRUTH_STATUS.md (evidence receipt v1).
CHECK_STATES = {"PASS", "FAIL", "BLOCKED", "NOT_RUN", "UNKNOWN", "INCONCLUSIVE"}
NON_GREEN_STATES = {"FAIL", "BLOCKED", "NOT_RUN", "UNKNOWN", "INCONCLUSIVE"}

SHOWCASE_REQUIRED_FIELDS = (
    "schema_version",
    "manifest_name",
    "generated_at_utc",
    "flagships",
)

FLAGSHIP_REQUIRED_FIELDS = (
    "id",
    "name",
    "repository",
    "source_sha",
    "captured_version",
    "capture_date",
    "demonstration_type",
    "primary_media",
    "live_url",
    "capture_method",
    "test_evidence",
    "known_limitations",
    "verification_status",
)

VALID_VERIFICATION_STATUSES = {"CURRENT", "HISTORICAL"}
HEX_SHA_RE = re.compile(r"^[0-9a-f]{7,40}$", re.IGNORECASE)
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z)?$")

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
HTML_TAG_RE = re.compile(r"<[^>]+>")
HTML_ANCHOR_RE = re.compile(
    r"<[A-Za-z][^>]*?\b(?:name|id)\s*=\s*"
    r"(?:\"(?P<double>[^\"]+)\"|'(?P<single>[^']+)')[^>]*>",
    re.IGNORECASE,
)


class CheckerError(Exception):
    """Invalid configuration or tool failure (exit 2)."""


def confine(repo: str, rel: str) -> str | None:
    """Resolve rel against the checkout, refusing escapes.

    Returns the in-checkout absolute path, or None when rel is absolute,
    traverses out of the checkout lexically, or resolves through a symlink
    to a location outside it. Callers must never read the target when None
    is returned, and must report only the caller-supplied rel path so
    out-of-checkout locations never leak into findings.
    """
    repo_real = os.path.realpath(repo)
    if os.path.isabs(rel):
        return None
    resolved = os.path.normpath(os.path.join(repo, rel))
    # realpath containment covers lexical traversal and symlinks in one
    # check, and still accepts a checkout that is itself reached through a
    # symlink (repo_real is resolved on both sides).
    real = os.path.realpath(resolved)
    if not (real == repo_real or real.startswith(repo_real + os.sep)):
        return None
    return resolved


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

    def finalize(self, repo: str, inspected_source: str) -> dict:
        self.findings.sort(key=lambda f: (f["path"], f["line"],
                                          f["rule_id"], f["message"]))
        return {
            "schema_version": SCHEMA_VERSION,
            "repo": repo,
            "inspected_source": inspected_source,
            "findings": self.findings,
            "coverage": {
                # Rule IDs of rules that actually executed on this run —
                # not only the rules that emitted findings.
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
    stripped, _ = strip_fenced_with_lines(text)
    return stripped


def strip_fenced_with_lines(text: str) -> tuple[str, list[int]]:
    """Strip fenced code blocks and keep each surviving line's original
    line number so findings point at the real file line."""
    out: list[str] = []
    line_numbers: list[int] = []
    fence = re.compile(r"^\s*(```|~~~)")
    in_fence = False
    marker = ""
    for lineno, line in enumerate(text.splitlines(), 1):
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
            line_numbers.append(lineno)
    return "\n".join(out), line_numbers


def render_heading_text(text: str) -> str:
    """Approximate the rendered text of an inline Markdown heading.

    GitHub derives a heading's anchor from the *rendered* heading text, not
    from the Markdown source. Slugging the source verbatim keeps link URLs and
    image targets inside the slug, so a heading such as
    ``### 1. [Babel](https://github.com/gthgomez/Babel) — Runtime`` would get
    an anchor no reader could ever produce. This collapses the inline markup
    to the text a reader sees: links contribute their label, images and raw
    HTML tags contribute no text, code spans keep their content.
    """
    # Images render as <img> and contribute no text, so drop them before the
    # link rule below can turn them into their alt text.
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)
    # Inline links -> label; reference links -> label.
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"\[([^\]]*)\]\[[^\]]*\]", r"\1", text)
    # Code spans keep their content, lose their delimiters.
    text = re.sub(r"`+([^`]*)`+", r"\1", text)
    # Raw HTML (including <a name="..."> wrappers) contributes no text.
    text = HTML_TAG_RE.sub("", text)
    # Markdown backslash escapes render as the escaped character.
    text = re.sub(r"\\([\\`*_{}\[\]()#+\-.!|>~])", r"\1", text)
    # Entities render before slugging (&amp; -> &, &nbsp; -> space).
    text = html.unescape(text).replace("\u00a0", " ")
    # Emphasis markers are markup, not text. Underscores *between* word
    # characters are literal (e.g. GBA_Emulator) and GitHub keeps them, so
    # single underscores are only removed at word boundaries.
    text = text.replace("**", "").replace("__", "").replace("~~", "")
    text = text.replace("*", "")
    text = re.sub(r"(?:\A|(?<=[\s(\[{]))_+", "", text)
    text = re.sub(r"_+(?=\Z|[\s)\]}\.,;:!?])", "", text)
    return text


def github_anchor(text: str) -> str:
    """Slug for a heading, matching GitHub's github-slugger behaviour.

    Lowercase, drop punctuation/symbols (GitHub keeps letters, digits,
    underscores and hyphens), then turn spaces into hyphens.
    """
    slug = render_heading_text(text).strip().lower()
    slug = re.sub(r"[^\w\- ]", "", slug)
    slug = slug.replace(" ", "-")
    return slug


def normalize_fragment(frag: str) -> str:
    """Normalise a link fragment the way GitHub matches it.

    Fragments are percent-encoded in Markdown sources and GitHub resolves
    them case-insensitively against lower-case generated ids, so ``#Usage``
    and ``#%55sage`` both reach ``usage``.
    """
    return unquote(frag).strip().lower()


def collect_anchors(md_text: str) -> set[str]:
    """Return every in-document fragment target GitHub would generate.

    Heading slugs are deduplicated with GitHub's numeric suffixes (``-1``,
    ``-2``, ...). Explicit HTML anchors (``<a name="x">`` / ``id="x"``) are
    valid targets too, and are accepted in their declared spelling and
    lower-cased, because fragment matching on this side is lower-cased.
    """
    stripped = strip_fenced(md_text)
    anchors: dict[str, int] = {}
    for line in stripped.splitlines():
        m = HEADING_RE.match(line)
        if m:
            base = github_anchor(m.group(2))
            anchors[base] = anchors.get(base, 0) + 1
    result: set[str] = set()
    for base, count in anchors.items():
        result.add(base)
        for i in range(1, count):
            result.add(f"{base}-{i}")
    result.discard("")
    for match in HTML_ANCHOR_RE.finditer(stripped):
        name = (match.group("double") or match.group("single") or "").strip()
        if name:
            result.add(name)
            result.add(name.lower())
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
            text, line_numbers = strip_fenced_with_lines(f.read())
        for stripped_lineno, line in enumerate(text.splitlines(), 1):
            for _img, _label, target in MARKDOWN_LINK_RE.findall(line):
                # H003 applies to badge URLs too (they name a workflow file
                # that must exist locally); network fetching stays out of scope.
                m = BADGE_WORKFLOW_RE.search(target)
                if m:
                    wf = os.path.join(repo, ".github", "workflows", m.group(1) + ".yml")
                    wf_yml = os.path.join(repo, ".github", "workflows", m.group(1) + ".yaml")
                    if not os.path.isfile(wf) and not os.path.isfile(wf_yml):
                        report.add("H003", "blocking", rel, line_numbers[stripped_lineno - 1],
                                   "workflow badge references a workflow file that "
                                   "does not exist in this checkout", target)
                if target.startswith(("http://", "https://", "mailto:", "<")):
                    continue  # network checking is out of scope here
                path_part, _, frag = target.partition("#")
                path_part = path_part.strip()
                if not path_part:
                    # Same-document fragment: validate against this
                    # document's own headings.
                    anchors = md_cache.get(rel.lower(), set())
                    if frag and normalize_fragment(frag) not in anchors:
                        report.add("H002", "blocking", rel,
                                   line_numbers[stripped_lineno - 1],
                                   "markdown anchor not found in this document",
                                   target)
                    continue
                decoded = path_part.replace("%20", " ")
                if decoded.startswith("file:"):
                    sup = suppression_for(config, "H001", rel)
                    report.add("H001", "blocking", rel, line_numbers[stripped_lineno - 1],
                               "file:// URL in markdown link", target, sup)
                    continue
                if os.path.isabs(decoded) or decoded.startswith("\\\\"):
                    report.add("H002", "blocking", rel, line_numbers[stripped_lineno - 1],
                               "absolute path link in public docs", target)
                    continue
                resolved = os.path.normpath(os.path.join(base_dir, decoded))
                repo_root = os.path.abspath(repo)
                if not resolved.startswith(repo_root + os.sep) and resolved != repo_root:
                    report.add("H002", "blocking", rel, line_numbers[stripped_lineno - 1],
                               "link escapes the public checkout", target)
                    continue
                exists_ci, exact_case = resolve_link_target(repo_root, resolved)
                if exists_ci:
                    if not exact_case:
                        report.add("H002", "blocking", rel, line_numbers[stripped_lineno - 1],
                                   "link target exists but with different case "
                                   "(breaks on case-sensitive filesystems)",
                                   target)
                        continue
                else:
                    report.add("H002", "blocking", rel, line_numbers[stripped_lineno - 1],
                               "relative link target not found", target)
                    continue
                if frag:
                    rel_target = os.path.relpath(resolved, repo_root).replace("\\", "/")
                    key = rel_target.lower()
                    if key not in md_cache and rel_target.lower().endswith(DOC_EXTENSIONS):
                        if os.path.realpath(resolved).startswith(
                                os.path.realpath(repo_root) + os.sep):
                            try:
                                with open(resolved, "r", encoding="utf-8",
                                          errors="replace") as f:
                                    md_cache[key] = collect_anchors(f.read())
                            except OSError:
                                md_cache[key] = set()
                        else:
                            # Symlinked target resolves outside the checkout;
                            # never read or leak its contents.
                            md_cache[key] = set()
                    anchors = md_cache.get(key)
                    if (anchors is not None
                            and normalize_fragment(frag) not in anchors):
                        report.add("H002", "blocking", rel, line_numbers[stripped_lineno - 1],
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
        sec_rel = config.get("security_reporting_path") or "SECURITY.md"
        if not os.path.isfile(os.path.join(repo, sec_rel)):
            report.add("H004", "blocking", sec_rel, 0,
                       "sensitive repository requires a security-reporting "
                       "path and the declared file does not exist", sec_rel)


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
            pattern = vc.get("pattern", r"(.*)")
            m = re.search(pattern, content)
            if m and m.groups():
                actual = m.group(1).strip()
            elif m:
                raise CheckerError(
                    f"version_checks pattern for '{rel}' matches but has no "
                    "capture group to extract the version value")
            elif "pattern" in vc:
                report.add("H005", "blocking", rel, 0,
                           "version pattern matched nothing in the declared "
                           "source", pattern)
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
        full = confine(repo, rel)
        if full is None:
            report.add("H006", "blocking", rel.replace("\\", "/"), 0,
                       "evidence receipt path escapes the repository; the "
                       "file was not read", rel.replace("\\", "/"))
            continue
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
        if isinstance(receipt, dict) and receipt.get("manifest_name") == "showcase-evidence-manifest":
            # Showcase manifests are checked by H009
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
            art_full = confine(repo, art_rel)
            if art_full is None:
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
            stripped, line_numbers = strip_fenced_with_lines(f.read())
        for stripped_lineno, line in enumerate(stripped.splitlines(), 1):
            for pattern, kind in VOLATILE_PATTERNS:
                if pattern.search(line):
                    sup = suppression_for(config, "H007", rel)
                    report.add("H007", "warning", rel,
                               line_numbers[stripped_lineno - 1],
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
        cwd = confine(repo, cmd.get("cwd", "."))
        if cwd is None:
            raise CheckerError(
                f"approved command '{cmd['id']}' cwd escapes the repository: "
                f"{cmd.get('cwd')}")
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
            if isinstance(token, str) and (re.match(r"^[A-Za-z]:[\\/]", token)
                                           or token.startswith("\\\\")):
                # Windows-style absolute paths never match the file-token
                # regex below (no colon/backslash), so flag them here.
                report.add("H008", "blocking", "portfolio-manifest.json", 0,
                           f"approved command '{cmd['id']}' references a file "
                           "outside the checkout via an absolute path", token)
                continue
            if isinstance(token, str) and re.match(r"^[\w./\-]+\.(py|json|md|ya?ml|toml|gradle|kts)$", token):
                if os.path.isabs(token):
                    report.add("H008", "blocking", "portfolio-manifest.json", 0,
                               f"approved command '{cmd['id']}' references a file "
                               "outside the checkout via an absolute path", token)
                    continue
                token_full = confine(repo, os.path.join(cmd.get("cwd", "."), token))
                if token_full is None:
                    report.add("H008", "blocking", "portfolio-manifest.json", 0,
                               f"approved command '{cmd['id']}' references a file "
                               "outside the checkout", token)
                elif not os.path.isfile(token_full):
                    report.add("H008", "blocking", "portfolio-manifest.json", 0,
                               f"approved command '{cmd['id']}' references a file "
                               "that does not exist in the checkout", token)


# ---------------------------------------------------------------- H009
EXPECTED_FLAGSHIP_IDS = (
    "babel",
    "monte-carlo-ledger",
    "prismatix",
    "gba-emulator",
    "proofpath",
    "reliquary",
)

MAX_MEDIA_BYTES = 2 * 1024 * 1024  # 2MB
ALLOWED_MEDIA_EXTENSIONS = (".png", ".jpg", ".jpeg", ".svg", ".webp", ".gif", ".mp4")


def validate_media_file_integrity(report: Report, manifest_rel: str, f_id: str,
                                 m_kind: str, m_path: str, m_full: str) -> None:
    size = os.path.getsize(m_full)
    if size > MAX_MEDIA_BYTES:
        report.add("H009", "blocking", manifest_rel, 0,
                   f"flagship '{f_id}' {m_kind} file exceeds 2MB limit ({size} bytes): {m_path}",
                   m_path)
        return

    ext = os.path.splitext(m_path)[1].lower()
    if ext not in ALLOWED_MEDIA_EXTENSIONS:
        report.add("H009", "blocking", manifest_rel, 0,
                   f"flagship '{f_id}' {m_kind} has unsupported file extension: {m_path}",
                   m_path)
        return

    try:
        with open(m_full, "rb") as f:
            head = f.read(64)
    except OSError as exc:
        report.add("H009", "blocking", manifest_rel, 0,
                   f"flagship '{f_id}' {m_kind} cannot be read: {exc}", m_path)
        return

    if ext == ".png":
        if not head.startswith(b"\x89PNG\r\n\x1a\n"):
            report.add("H009", "blocking", manifest_rel, 0,
                       f"flagship '{f_id}' {m_kind} is not a valid PNG (missing PNG signature): {m_path}",
                       m_path)
        elif len(head) >= 24 and head[12:16] == b"IHDR":
            w, h = struct.unpack(">II", head[16:24])
            if w == 0 or h == 0:
                report.add("H009", "blocking", manifest_rel, 0,
                           f"flagship '{f_id}' {m_kind} has zero or invalid dimensions: {m_path}",
                           m_path)
    elif ext in (".jpg", ".jpeg"):
        if not head.startswith(b"\xff\xd8"):
            report.add("H009", "blocking", manifest_rel, 0,
                       f"flagship '{f_id}' {m_kind} is not a valid JPEG (missing SOI marker): {m_path}",
                       m_path)
    elif ext == ".gif":
        if not (head.startswith(b"GIF87a") or head.startswith(b"GIF89a")):
            report.add("H009", "blocking", manifest_rel, 0,
                       f"flagship '{f_id}' {m_kind} is not a valid GIF: {m_path}",
                       m_path)
    elif ext == ".svg":
        try:
            tree = ET.parse(m_full)
            root_tag = tree.getroot().tag.lower()
            if not root_tag.endswith("svg"):
                report.add("H009", "blocking", manifest_rel, 0,
                           f"flagship '{f_id}' {m_kind} root element is not <svg>: {m_path}",
                           m_path)
        except ET.ParseError as exc:
            report.add("H009", "blocking", manifest_rel, 0,
                       f"flagship '{f_id}' {m_kind} is not a valid SVG (XML parse error: {exc}): {m_path}",
                       m_path)
    elif ext == ".mp4":
        if b"ftyp" not in head[:16]:
            report.add("H009", "blocking", manifest_rel, 0,
                       f"flagship '{f_id}' {m_kind} is not a valid MP4 container: {m_path}",
                       m_path)


def check_showcase_manifest(report: Report, config: dict, repo: str) -> None:
    manifest_rel = config.get("showcase_manifest")
    if not manifest_rel:
        candidate = os.path.join(repo, "docs", "showcase-manifest.json")
        if os.path.isfile(candidate) or config.get("project_type") == "profile":
            manifest_rel = "docs/showcase-manifest.json"
        else:
            return

    full = confine(repo, manifest_rel)
    if full is None:
        report.add("H009", "blocking", manifest_rel.replace("\\", "/"), 0,
                   "showcase manifest path escapes the repository",
                   manifest_rel.replace("\\", "/"))
        return
    if not os.path.isfile(full):
        report.add("H009", "blocking", manifest_rel, 0,
                   "showcase manifest file does not exist", manifest_rel)
        return

    try:
        with open(full, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        report.add("H009", "blocking", manifest_rel, 0,
                   "showcase manifest is not valid JSON", str(exc))
        return

    missing = [k for k in SHOWCASE_REQUIRED_FIELDS if k not in data]
    if missing:
        report.add("H009", "blocking", manifest_rel, 0,
                   f"showcase manifest missing required fields: {', '.join(missing)}",
                   ", ".join(missing))
        return

    flagships = data.get("flagships")
    if not isinstance(flagships, list) or not flagships:
        report.add("H009", "blocking", manifest_rel, 0,
                   "showcase manifest flagships must be a non-empty list", "flagships")
        return

    seen_ids: set[str] = set()
    cataloged_media: set[str] = set()
    for idx, item in enumerate(flagships):
        if not isinstance(item, dict):
            report.add("H009", "blocking", manifest_rel, 0,
                       f"flagship entry at index {idx} must be an object", str(idx))
            continue
        f_id = item.get("id", f"entry-{idx}")
        seen_ids.add(f_id)

        missing_fields = [k for k in FLAGSHIP_REQUIRED_FIELDS if k not in item]
        if missing_fields:
            report.add("H009", "blocking", manifest_rel, 0,
                       f"flagship '{f_id}' missing required fields: {', '.join(missing_fields)}",
                       ", ".join(missing_fields))
            continue

        sha = str(item.get("source_sha", ""))
        if not HEX_SHA_RE.match(sha):
            report.add("H009", "blocking", manifest_rel, 0,
                       f"flagship '{f_id}' has invalid git hex SHA: '{sha}'", sha)

        cdate = str(item.get("capture_date", ""))
        if not DATE_RE.match(cdate):
            report.add("H009", "blocking", manifest_rel, 0,
                       f"flagship '{f_id}' has invalid capture_date format: '{cdate}'", cdate)

        status = item.get("verification_status")
        if status not in VALID_VERIFICATION_STATUSES:
            report.add("H009", "blocking", manifest_rel, 0,
                       f"flagship '{f_id}' has invalid verification_status: '{status}'", str(status))

        limitations = item.get("known_limitations")
        if not isinstance(limitations, str) or not limitations.strip():
            report.add("H009", "blocking", manifest_rel, 0,
                       f"flagship '{f_id}' has empty known_limitations disclaimer", str(limitations))

        # Media checks
        media_paths: list[tuple[str, str]] = []
        if item.get("primary_media"):
            media_paths.append(("primary_media", item["primary_media"]))
        for sm in item.get("supporting_media", []):
            media_paths.append(("supporting_media", sm))

        for m_kind, m_path in media_paths:
            if not isinstance(m_path, str) or not m_path.strip():
                report.add("H009", "blocking", manifest_rel, 0,
                           f"flagship '{f_id}' has invalid {m_kind} path", str(m_path))
                continue

            # Workstation path leaks
            leaked = False
            for pat, desc in PRIVATE_PATH_PATTERNS:
                if pat.search(m_path):
                    report.add("H009", "blocking", manifest_rel, 0,
                               f"flagship '{f_id}' {m_kind} leaks workstation path ({desc}): {m_path}",
                               m_path)
                    leaked = True
                    break
            if leaked:
                continue

            # Confinement and file existence
            m_full = confine(repo, m_path)
            if m_full is None:
                report.add("H009", "blocking", manifest_rel, 0,
                           f"flagship '{f_id}' {m_kind} path escapes repository: {m_path}", m_path)
            elif not os.path.isfile(m_full):
                report.add("H009", "blocking", manifest_rel, 0,
                           f"flagship '{f_id}' {m_kind} file does not exist: {m_path}", m_path)
            elif os.path.getsize(m_full) == 0:
                report.add("H009", "blocking", manifest_rel, 0,
                           f"flagship '{f_id}' {m_kind} file is empty (0 bytes): {m_path}", m_path)
            else:
                validate_media_file_integrity(report, manifest_rel, f_id, m_kind, m_path, m_full)
                cataloged_media.add(os.path.normpath(m_path).replace("\\", "/"))

    if config.get("project_type") == "profile":
        missing_flagships = set(EXPECTED_FLAGSHIP_IDS) - seen_ids
        if missing_flagships:
            report.add("H009", "blocking", manifest_rel, 0,
                       f"showcase manifest missing expected flagships: {', '.join(sorted(missing_flagships))}",
                       ", ".join(sorted(missing_flagships)))

        # Verify no uncataloged showcase assets exist on disk
        showcase_dir = os.path.join(repo, "assets", "showcase")
        if os.path.isdir(showcase_dir):
            for fname in sorted(os.listdir(showcase_dir)):
                disk_full = os.path.join(showcase_dir, fname)
                if os.path.isfile(disk_full):
                    rel_disk = os.path.normpath(os.path.join("assets", "showcase", fname)).replace("\\", "/")
                    if rel_disk not in cataloged_media:
                        report.add("H009", "blocking", manifest_rel, 0,
                                   f"uncataloged media file on disk in assets/showcase: {rel_disk}",
                                   rel_disk)


DOC_EXTENSIONS = (".md", ".markdown")


def doc_files_for(config: dict, repo: str) -> list[str]:
    """Docs under public entrypoints, deterministically ordered."""
    entries = config.get("public_entrypoints")
    if not isinstance(entries, list) or not entries:
        raise CheckerError("config missing non-empty 'public_entrypoints' list")
    files: set[str] = set()
    for entry in entries:
        full = confine(repo, entry)
        if full is None:
            raise CheckerError(
                f"public entrypoint escapes the repository: {entry}")
        if os.path.isdir(full):
            for root, _dirs, names in os.walk(full):
                for name in sorted(names):
                    if name.lower().endswith(DOC_EXTENSIONS):
                        files.add(os.path.relpath(
                            os.path.join(root, name), repo).replace("\\", "/"))
        elif os.path.isfile(full) and entry.lower().endswith(DOC_EXTENSIONS):
            files.add(entry.replace("\\", "/"))
        else:
            raise CheckerError(
                f"public entrypoint not found or not a Markdown doc: {entry}")
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
        # coverage.rules_run must reflect executed rules, not only rules
        # that happened to emit findings on this run.
        report.rules_run.update(
            ("H001", "H002", "H003", "H004", "H005", "H006", "H007", "H008", "H009"))
        check_private_paths(report, config, repo, docs)
        check_links(report, config, repo, docs)
        check_license_policy(report, config, repo)
        check_versions(report, config, repo)
        check_evidence(report, config, repo, head)
        check_volatile_prose(report, config, repo, docs)
        check_commands(report, config, repo)
        check_showcase_manifest(report, config, repo)
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
