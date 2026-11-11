"""Fixture tests for tools/portfolio_hygiene.py.

Every blocking rule (H001-H008) gets one clean and one deliberately bad
fixture: the negative control must fail (exit 1) with the named rule before
any fix would exist to hide it, and the clean fixture must pass (exit 0).
The checker is executed as a subprocess so exit-code propagation is tested
the same way CI would see it.
"""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CHECKER = os.path.join(REPO_ROOT, "tools", "portfolio_hygiene.py")
FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")

HEAD_A = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
HEAD_B = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"

BASE_CONFIG = {
    "schema_version": 1,
    "repository": "fixture/repo",
    "project_type": "library",
    "maturity": "prototype",
    "source_visibility_policy": "open-source-mit",
    "license_path": "LICENSE",
    "default_branch": "main",
    "supported_toolchains": ["python>=3.9"],
    "approved_commands": [],
    "evidence_links": [],
    "release_policy": "none",
    "cross_repo_dependencies": [],
    "flagship_role": "none",
    "public_entrypoints": ["README.md"],
    "require_security_reporting": False,
    "version_checks": [],
    "generated_doc_markers": [],
    "suppressions": [],
}


def digest(path: str) -> str:
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


class FixtureCase(unittest.TestCase):
    """Copies a fixture tree into a temp dir and runs the checker on it."""

    def setup_fixture(self, name: str, config_overrides: dict | None = None,
                      transform_receipts: bool = True) -> str:
        tmp = tempfile.mkdtemp(prefix="hygiene-fixture-")
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        shutil.copytree(os.path.join(FIXTURES, name), tmp, dirs_exist_ok=True)
        config = json.loads(json.dumps(BASE_CONFIG))
        config.update(config_overrides or {})
        if transform_receipts:
            evidence_dir = os.path.join(tmp, "evidence")
            if os.path.isdir(evidence_dir):
                for name_ in sorted(os.listdir(evidence_dir)):
                    if not name_.endswith(".json"):
                        continue
                    path = os.path.join(evidence_dir, name_)
                    with open(path, "r", encoding="utf-8") as f:
                        raw = f.read()
                    report_txt = os.path.join(tmp, "evidence", "report.txt")
                    if os.path.isfile(report_txt):
                        raw = raw.replace("__DIGEST__", digest(report_txt))
                    raw = raw.replace("__SOURCE_SHA__", HEAD_A)
                    with open(path, "w", encoding="utf-8") as f:
                        f.write(raw)
        with open(os.path.join(tmp, "portfolio-manifest.json"), "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
        return tmp

    def run_checker(self, tmp: str, head: str = HEAD_A, fmt: str = "json"):
        return subprocess.run(
            [sys.executable, CHECKER, "check", "--repo", tmp,
             "--config", os.path.join(tmp, "portfolio-manifest.json"),
             "--format", fmt, "--head", head],
            capture_output=True, text=True, timeout=60,
        )

    def rule_ids(self, proc) -> list:
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        payload = json.loads(proc.stdout)
        return [f["rule_id"] for f in payload["findings"]]


class CleanFixtureTests(FixtureCase):
    def test_clean_repo_exits_zero(self):
        tmp = self.setup_fixture("clean", config_overrides={
            "evidence_links": [{"path": "evidence/receipt.json", "current": True}],
            "public_entrypoints": ["README.md"],
        })
        proc = self.run_checker(tmp)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["findings"], [])
        self.assertEqual(payload["errors"], [])
        self.assertEqual(payload["inspected_source"], HEAD_A)

    def test_honest_historical_receipt_is_not_stale(self):
        """Old evidence with an honest historical label must pass."""
        tmp = self.setup_fixture("bad_stale_status", config_overrides={
            "evidence_links": [{"path": "evidence/receipt.json", "current": False}],
        })
        proc = self.run_checker(tmp)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)


class H001PrivatePathTests(FixtureCase):
    def test_workstation_paths_fail(self):
        tmp = self.setup_fixture("bad_paths")
        ids = self.rule_ids(self.run_checker(tmp))
        self.assertIn("H001", ids)

    def test_deliberate_provenance_with_suppression_is_exempt_not_silent(self):
        tmp = self.setup_fixture("bad_suppressed", config_overrides={
            "suppressions": [{
                "rule_id": "H001", "path": "README.md",
                "reason": "archived provenance, path retained deliberately",
                "owner": "fixture-owner",
            }],
        })
        proc = self.run_checker(tmp)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        payload = json.loads(proc.stdout)
        exempt = [f for f in payload["findings"] if f["severity"] == "exempt"]
        self.assertTrue(exempt, "exempt findings must still be reported")
        self.assertIn("H001", [f["rule_id"] for f in exempt])
        self.assertEqual(exempt[0]["suppression"]["owner"], "fixture-owner")


class H002LinkTests(FixtureCase):
    def test_wrong_case_broken_escaping_and_anchor_links_fail(self):
        tmp = self.setup_fixture("bad_links")
        proc = self.run_checker(tmp)
        ids = self.rule_ids(proc)
        self.assertIn("H002", ids)
        payload = json.loads(proc.stdout)
        messages = " | ".join(f["message"] for f in payload["findings"] if f["rule_id"] == "H002")
        self.assertIn("different case", messages)
        self.assertIn("not found", messages)
        self.assertIn("escapes the public checkout", messages)
        self.assertIn("anchor not found", messages)

    def test_json_output_order_is_deterministic(self):
        tmp = self.setup_fixture("bad_links")
        runs = [self.run_checker(tmp).stdout for _ in range(2)]
        self.assertEqual(runs[0], runs[1])
        findings = json.loads(runs[0])["findings"]
        keys = [(f["path"], f["line"], f["rule_id"]) for f in findings]
        self.assertEqual(keys, sorted(keys))


class H003BadgeTests(FixtureCase):
    def test_broken_workflow_badge_fails(self):
        tmp = self.setup_fixture("bad_badge")
        ids = self.rule_ids(self.run_checker(tmp))
        self.assertIn("H003", ids)


class H004LicenseTests(FixtureCase):
    def test_proprietary_policy_with_oss_license_text_fails(self):
        tmp = self.setup_fixture("clean", config_overrides={
            "source_visibility_policy": "proprietary-all-rights-reserved",
            "require_security_reporting": True,
        })
        ids = self.rule_ids(self.run_checker(tmp))
        self.assertIn("H004", ids)

    def test_missing_license_file_fails(self):
        tmp = self.setup_fixture("clean", config_overrides={"license_path": "MISSING"})
        os.remove(os.path.join(tmp, "LICENSE"))
        ids = self.rule_ids(self.run_checker(tmp))
        self.assertIn("H004", ids)


class H005VersionTests(FixtureCase):
    def test_declared_release_mismatch_fails(self):
        tmp = self.setup_fixture("bad_version", config_overrides={
            "version_checks": [{
                "file": "version.json", "json_pointer": "/version",
                "domain": "core", "status": "released",
                "expected_version": "1.2.4",
            }],
        })
        ids = self.rule_ids(self.run_checker(tmp))
        self.assertIn("H005", ids)

    def test_unreleased_dev_version_is_allowed(self):
        tmp = self.setup_fixture("bad_version", config_overrides={
            "version_checks": [{
                "file": "version.json", "json_pointer": "/version",
                "domain": "core", "status": "unreleased",
            }],
        })
        proc = self.run_checker(tmp)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)


class H006EvidenceTests(FixtureCase):
    def test_stale_sha_marked_current_fails(self):
        tmp = self.setup_fixture("bad_stale_status", config_overrides={
            "evidence_links": [{"path": "evidence/receipt.json", "current": True}],
        })
        proc = self.run_checker(tmp, head=HEAD_B)
        ids = self.rule_ids(proc)
        self.assertIn("H006", ids)
        payload = json.loads(proc.stdout)
        messages = " | ".join(f["message"] for f in payload["findings"] if f["rule_id"] == "H006")
        self.assertIn("historical", messages)

    def test_unknown_and_omitted_states_never_render_green(self):
        tmp = self.setup_fixture("bad_nongreen", config_overrides={
            "evidence_links": [{"path": "evidence/receipt.json", "current": True}],
        })
        ids = self.rule_ids(self.run_checker(tmp))
        self.assertIn("H006", ids)

    def test_missing_artifact_fails(self):
        tmp = self.setup_fixture("bad_missing_artifact", config_overrides={
            "evidence_links": [{"path": "evidence/receipt.json", "current": True}],
        })
        ids = self.rule_ids(self.run_checker(tmp))
        self.assertIn("H006", ids)

    def test_invalid_receipt_json_fails_with_finding_not_crash(self):
        tmp = self.setup_fixture("bad_receipt", config_overrides={
            "evidence_links": [{"path": "evidence/receipt.json", "current": True}],
        })
        ids = self.rule_ids(self.run_checker(tmp))
        self.assertIn("H006", ids)

    def test_missing_receipt_file_fails(self):
        tmp = self.setup_fixture("clean", config_overrides={
            "evidence_links": [{"path": "evidence/receipt.json", "current": True}],
        })
        shutil.rmtree(os.path.join(tmp, "evidence"))
        ids = self.rule_ids(self.run_checker(tmp))
        self.assertIn("H006", ids)


class H007VolatileProseTests(FixtureCase):
    def test_volatile_prose_warns(self):
        tmp = self.setup_fixture("clean", config_overrides={
            "public_entrypoints": ["README.md"],
        })
        with open(os.path.join(tmp, "README.md"), "a", encoding="utf-8") as f:
            f.write("Our suite reports 128 unit tests and 87.4% coverage.\n")
        proc = self.run_checker(tmp)
        ids = self.rule_ids(proc)
        self.assertIn("H007", ids)
        payload = json.loads(proc.stdout)
        self.assertTrue(all(f["severity"] == "warning"
                            for f in payload["findings"] if f["rule_id"] == "H007"))


class H008CommandRegistryTests(FixtureCase):
    def test_missing_referenced_file_fails(self):
        tmp = self.setup_fixture("clean", config_overrides={
            "approved_commands": [{
                "id": "check", "argv": ["python", "tools/absent.py", "check"],
                "cwd": ".", "allowed_env": [], "network": "none",
                "output_artifact": "stdout",
            }],
        })
        ids = self.rule_ids(self.run_checker(tmp))
        self.assertIn("H008", ids)

    def test_missing_npm_script_fails_without_execution(self):
        tmp = self.setup_fixture("clean", config_overrides={
            "approved_commands": [{
                "id": "lint", "argv": ["npm", "run", "no-such-script"],
                "cwd": ".", "allowed_env": [], "network": "none",
                "output_artifact": "stdout",
            }],
        })
        with open(os.path.join(tmp, "package.json"), "w", encoding="utf-8") as f:
            json.dump({"name": "fixture", "scripts": {"real": "echo hi"}}, f)
        ids = self.rule_ids(self.run_checker(tmp))
        self.assertIn("H008", ids)

    def test_networked_command_is_rejected_as_invalid_config(self):
        tmp = self.setup_fixture("clean", config_overrides={
            "approved_commands": [{
                "id": "probe", "argv": ["curl", "https://example.com"],
                "cwd": ".", "allowed_env": [], "network": "full",
                "output_artifact": "stdout",
            }],
        })
        proc = self.run_checker(tmp)
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)

    def test_valid_registry_passes_and_never_executes(self):
        tmp = self.setup_fixture("clean", config_overrides={
            "approved_commands": [{
                "id": "check",
                "argv": ["python", "-c", "raise SystemExit(3)"],
                "cwd": ".", "allowed_env": [], "network": "none",
                "output_artifact": "stdout",
            }],
        })
        proc = self.run_checker(tmp)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)


class ConfigAndToolFailureTests(FixtureCase):
    def test_missing_config_is_exit_2(self):
        tmp = tempfile.mkdtemp(prefix="hygiene-nocfg-")
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        proc = subprocess.run(
            [sys.executable, CHECKER, "check", "--repo", tmp,
             "--config", os.path.join(tmp, "nope.json"), "--format", "json"],
            capture_output=True, text=True, timeout=60)
        self.assertEqual(proc.returncode, 2)

    def test_invalid_config_missing_field_is_exit_2(self):
        broken = {k: v for k, v in BASE_CONFIG.items() if k != "license_path"}
        tmp = tempfile.mkdtemp(prefix="hygiene-badcfg-")
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        with open(os.path.join(tmp, "portfolio-manifest.json"), "w", encoding="utf-8") as f:
            json.dump(broken, f)
        proc = subprocess.run(
            [sys.executable, CHECKER, "check", "--repo", tmp,
             "--config", os.path.join(tmp, "portfolio-manifest.json")],
            capture_output=True, text=True, timeout=60)
        self.assertEqual(proc.returncode, 2)

    def test_wrong_schema_version_is_exit_2(self):
        tmp = self.setup_fixture("clean", config_overrides={"schema_version": 99})
        proc = self.run_checker(tmp)
        self.assertEqual(proc.returncode, 2)

    def test_exit_code_propagates_through_wrapper(self):
        """Exit propagation through a shell-style wrapper (CI path)."""
        tmp = self.setup_fixture("bad_paths")
        wrapper = subprocess.run(
            [sys.executable, "-c",
             "import subprocess,sys;"
             f"sys.exit(subprocess.run([sys.executable,{CHECKER!r},'check',"
             f"'--repo',{tmp!r},'--config',{os.path.join(tmp, 'portfolio-manifest.json')!r},"
             "'--head','" + HEAD_A + "']).returncode)"],
            capture_output=True, text=True, timeout=60)
        self.assertEqual(wrapper.returncode, 1)


def _safe_symlink(src: str, dst: str, target_is_directory: bool = False) -> None:
    try:
        os.symlink(src, dst, target_is_directory=target_is_directory)
    except OSError as exc:
        if getattr(exc, "winerror", None) == 1314 or "privilege" in str(exc).lower():
            raise unittest.SkipTest("symlinks require elevated privileges on Windows") from exc
        raise


class CheckoutConfinementTests(FixtureCase):
    """Out-of-checkout targets must never be read, modified, or leaked."""

    def test_evidence_receipt_outside_checkout_is_not_read(self):
        """Negative control: a traversal receipt path must be rejected as an
        escape finding, and the outside file must not be parsed (it is
        deliberately invalid JSON; a 'not valid JSON' finding would mean it
        was read)."""
        tmp = self.setup_fixture("clean", config_overrides={
            "evidence_links": [{"path": "../outside/secret.json", "current": False}],
        })
        outside_dir = os.path.join(os.path.dirname(tmp), "outside")
        os.makedirs(outside_dir, exist_ok=True)
        self.addCleanup(shutil.rmtree, outside_dir, ignore_errors=True)
        with open(os.path.join(outside_dir, "secret.json"), "w") as f:
            f.write("THIS IS NOT JSON{")
        proc = self.run_checker(tmp)
        ids = self.rule_ids(proc)
        self.assertIn("H006", ids)
        payload = json.loads(proc.stdout)
        h006 = [f for f in payload["findings"] if f["rule_id"] == "H006"]
        self.assertTrue(all("escapes" in f["message"] for f in h006))
        out = proc.stdout + proc.stderr
        self.assertNotIn(outside_dir, out, "outside locations must not leak")
        self.assertNotIn("not valid JSON", out, "outside file must not be read")

    def test_evidence_receipt_absolute_path_is_rejected(self):
        tmp = self.setup_fixture("clean", config_overrides={
            "evidence_links": [{"path": "/etc/passwd", "current": False}],
        })
        proc = self.run_checker(tmp)
        ids = self.rule_ids(proc)
        self.assertIn("H006", ids)
        payload = json.loads(proc.stdout)
        h006 = [f for f in payload["findings"] if f["rule_id"] == "H006"]
        self.assertTrue(all("escapes" in f["message"] for f in h006))

    def test_symlinked_artifact_pointing_outside_fails(self):
        tmp = self.setup_fixture("clean", config_overrides={
            "evidence_links": [{"path": "evidence/receipt.json", "current": True}],
        })
        outside_dir = os.path.join(os.path.dirname(tmp), "outside")
        os.makedirs(outside_dir, exist_ok=True)
        self.addCleanup(shutil.rmtree, outside_dir, ignore_errors=True)
        outside_file = os.path.join(outside_dir, "artifact.txt")
        with open(outside_file, "w") as f:
            f.write("outside bytes")
        _safe_symlink(outside_file, os.path.join(tmp, "artifact.txt"))
        receipt = {
            "schema_version": 1, "repository": "fixture/repo",
            "source_sha": HEAD_A, "generated_at_utc": "2026-01-01T00:00:00Z",
            "producer": "test", "exit_code": 0,
            "checks": [{"name": "unit", "state": "PASS"}],
            "artifact_hashes": {"artifact.txt": digest(outside_file)},
            "limitations": [],
        }
        with open(os.path.join(tmp, "evidence", "receipt.json"), "w") as f:
            json.dump(receipt, f)
        proc = self.run_checker(tmp)
        ids = self.rule_ids(proc)
        self.assertIn("H006", ids)
        payload = json.loads(proc.stdout)
        messages = " | ".join(f["message"] for f in payload["findings"] if f["rule_id"] == "H006")
        self.assertIn("escapes", messages)

    def test_public_entrypoint_outside_checkout_is_invalid_config(self):
        outside_dir = os.path.join(tempfile.mkdtemp(prefix="hygiene-out-"), "docs")
        self.addCleanup(shutil.rmtree, os.path.dirname(outside_dir), ignore_errors=True)
        os.makedirs(outside_dir)
        with open(os.path.join(outside_dir, "secret.md"), "w") as f:
            f.write("# Secret\n/home/linuxuser/marker\n")
        tmp = self.setup_fixture("clean")
        config_path = os.path.join(tmp, "portfolio-manifest.json")
        with open(config_path) as f:
            config = json.load(f)
        config["public_entrypoints"] = ["README.md", outside_dir]
        with open(config_path, "w") as f:
            json.dump(config, f)
        proc = self.run_checker(tmp)
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
        self.assertNotIn("Secret", proc.stdout + proc.stderr)

    def test_symlinked_checkout_still_passes(self):
        """A checkout reached through a symlink must not be false-rejected."""
        tmp = self.setup_fixture("clean")
        link = os.path.join(tempfile.mkdtemp(prefix="hygiene-lnk-"), "repo-link")
        self.addCleanup(shutil.rmtree, os.path.dirname(link), ignore_errors=True)
        _safe_symlink(tmp, link, target_is_directory=True)
        config_path = os.path.join(link, "portfolio-manifest.json")
        proc = subprocess.run(
            [sys.executable, CHECKER, "check", "--repo", link,
             "--config", config_path, "--format", "json", "--head", HEAD_A],
            capture_output=True, text=True, timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_approved_command_windows_absolute_token_fails(self):
        tmp = self.setup_fixture("clean", config_overrides={
            "approved_commands": [{
                "id": "run-external", "argv": ["python", "C:\\opt\\tools\\script.py"],
                "cwd": ".", "allowed_env": [], "network": "none",
                "output_artifact": "stdout",
            }],
        })
        ids = self.rule_ids(self.run_checker(tmp))
        self.assertIn("H008", ids)

    def test_approved_command_absolute_file_token_fails(self):
        tmp = self.setup_fixture("clean", config_overrides={
            "approved_commands": [{
                "id": "run-external", "argv": ["python", "/opt/tools/script.py"],
                "cwd": ".", "allowed_env": [], "network": "none",
                "output_artifact": "stdout",
            }],
        })
        ids = self.rule_ids(self.run_checker(tmp))
        self.assertIn("H008", ids)

    def test_approved_command_traversal_file_token_fails(self):
        tmp = self.setup_fixture("clean", config_overrides={
            "approved_commands": [{
                "id": "run-external", "argv": ["python", "../outside/script.py"],
                "cwd": ".", "allowed_env": [], "network": "none",
                "output_artifact": "stdout",
            }],
        })
        ids = self.rule_ids(self.run_checker(tmp))
        self.assertIn("H008", ids)

    def test_approved_command_absolute_cwd_is_invalid_config(self):
        tmp = self.setup_fixture("clean", config_overrides={
            "approved_commands": [{
                "id": "elsewhere", "argv": ["make", "check"],
                "cwd": "/tmp", "allowed_env": [], "network": "none",
                "output_artifact": "stdout",
            }],
        })
        proc = self.run_checker(tmp)
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)

    def test_symlinked_link_target_outside_checkout_is_not_read(self):
        """A symlinked doc target outside the checkout must not have its
        anchors collected; the anchor check reports a finding instead."""
        outside_dir = os.path.join(tempfile.mkdtemp(prefix="hygiene-out2-"), "docs")
        self.addCleanup(shutil.rmtree, os.path.dirname(outside_dir), ignore_errors=True)
        os.makedirs(outside_dir)
        with open(os.path.join(outside_dir, "linked.md"), "w") as f:
            f.write("# Outside Heading\n")
        tmp = self.setup_fixture("clean")
        _safe_symlink(os.path.join(outside_dir, "linked.md"),
                      os.path.join(tmp, "linked.md"))
        with open(os.path.join(tmp, "README.md"), "a") as f:
            f.write("[leak](linked.md#outside-heading)\n")
        proc = self.run_checker(tmp)
        ids = self.rule_ids(proc)
        self.assertIn("H002", ids)
        messages = " | ".join(f["message"] for f in json.loads(proc.stdout)["findings"]
                              if f["rule_id"] == "H002")
        # The anchor must be reported missing because the outside file's
        # headings were never read.
        self.assertIn("anchor not found", messages)


class ReportingSemanticsTests(FixtureCase):
    def test_clean_run_reports_all_rules_as_executed(self):
        """coverage.rules_run means executed rules, not rules with findings."""
        tmp = self.setup_fixture("clean")
        proc = self.run_checker(tmp)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        payload = json.loads(proc.stdout)
        self.assertEqual(
            payload["coverage"]["rules_run"],
            ["H001", "H002", "H003", "H004", "H005", "H006", "H007", "H008", "H009"])

    def test_link_findings_report_original_line_numbers(self):
        """Findings in fence-stripped scans must point at the real file line."""
        tmp = self.setup_fixture("clean")
        with open(os.path.join(tmp, "README.md"), "a") as f:
            f.write("```bash\n[not a link](nope.md)\n```\n")
            f.write("intro line\n\n[bad](nope.md)\n")
        with open(os.path.join(tmp, "README.md")) as f:
            expected_line = next(
                n for n, line in enumerate(f, 1) if "[bad](nope.md)" in line)
        proc = self.run_checker(tmp)
        payload = json.loads(proc.stdout)
        h002 = [f for f in payload["findings"] if f["rule_id"] == "H002"]
        self.assertTrue(h002)
        self.assertTrue(all(f["line"] == expected_line for f in h002), h002)

    def test_missing_declared_security_path_fails(self):
        tmp = self.setup_fixture("clean", config_overrides={
            "require_security_reporting": True,
            "security_reporting_path": "docs/ABSENT-SECURITY.md",
        })
        ids = self.rule_ids(self.run_checker(tmp))
        self.assertIn("H004", ids)


class ShowcaseManifestTests(FixtureCase):
    """Rule H009 tests covering showcase manifest validation."""

    def _create_showcase_fixture(self, manifest_modifications: dict | None = None,
                                 config_overrides: dict | None = None,
                                 create_media: bool = True):
        tmp = self.setup_fixture("clean", config_overrides={
            "showcase_manifest": "docs/showcase-manifest.json",
            **(config_overrides or {})
        })
        media_dir = os.path.join(tmp, "assets", "showcase")
        os.makedirs(media_dir, exist_ok=True)
        if create_media:
            with open(os.path.join(media_dir, "demo.png"), "wb") as f:
                # Minimal valid 1x1 PNG
                f.write(
                    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4"
                    b"\x00\x00\x00\rIDATx\x9cc`\x00\x00\x00\x02\x00\x01Haf\xa4\x00\x00\x00\x00IEND\xaeB`\x82"
                )

        manifest = {
            "schema_version": 1,
            "manifest_name": "showcase-evidence-manifest",
            "generated_at_utc": "2026-11-10T00:00:00Z",
            "account": "gthgomez",
            "flagships": [
                {
                    "id": "babel",
                    "name": "Babel",
                    "repository": "gthgomez/Babel",
                    "source_sha": "1dc598e2a2f1de914591570349708a6f01d66479",
                    "captured_version": "v0.1.0-alpha",
                    "capture_date": "2026-11-09",
                    "demonstration_type": "desktop-ui-capture",
                    "primary_media": "assets/showcase/demo.png",
                    "supporting_media": [],
                    "live_url": "https://example.com",
                    "capture_method": "Screenshot capture on desktop",
                    "test_evidence": "100% tests passed",
                    "known_limitations": "Prototype limitations apply",
                    "verification_status": "CURRENT"
                }
            ]
        }
        if manifest_modifications:
            for k, v in manifest_modifications.items():
                if k == "flagship_0":
                    manifest["flagships"][0].update(v)
                else:
                    manifest[k] = v

        docs_dir = os.path.join(tmp, "docs")
        os.makedirs(docs_dir, exist_ok=True)
        with open(os.path.join(docs_dir, "showcase-manifest.json"), "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)
        return tmp

    def test_valid_showcase_manifest_passes(self):
        tmp = self._create_showcase_fixture()
        proc = self.run_checker(tmp)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_missing_showcase_manifest_file_fails(self):
        tmp = self.setup_fixture("clean", config_overrides={
            "showcase_manifest": "docs/missing-manifest.json"
        })
        proc = self.run_checker(tmp)
        ids = self.rule_ids(proc)
        self.assertIn("H009", ids)

    def test_missing_media_file_fails(self):
        tmp = self._create_showcase_fixture(create_media=False)
        proc = self.run_checker(tmp)
        ids = self.rule_ids(proc)
        self.assertIn("H009", ids)
        findings = json.loads(proc.stdout)["findings"]
        self.assertTrue(any("does not exist" in f["message"] for f in findings if f["rule_id"] == "H009"))

    def test_invalid_sha_format_fails(self):
        tmp = self._create_showcase_fixture(manifest_modifications={
            "flagship_0": {"source_sha": "not-a-valid-git-sha!"}
        })
        proc = self.run_checker(tmp)
        ids = self.rule_ids(proc)
        self.assertIn("H009", ids)
        findings = json.loads(proc.stdout)["findings"]
        self.assertTrue(any("invalid git hex SHA" in f["message"] for f in findings if f["rule_id"] == "H009"))

    def test_empty_limitations_fails(self):
        tmp = self._create_showcase_fixture(manifest_modifications={
            "flagship_0": {"known_limitations": "   "}
        })
        proc = self.run_checker(tmp)
        ids = self.rule_ids(proc)
        self.assertIn("H009", ids)
        findings = json.loads(proc.stdout)["findings"]
        self.assertTrue(any("empty known_limitations" in f["message"] for f in findings if f["rule_id"] == "H009"))

    def test_workstation_path_leak_fails(self):
        tmp = self._create_showcase_fixture(manifest_modifications={
            "flagship_0": {"primary_media": "C:\\Users\\engineer\\secret\\demo.png"}
        })
        proc = self.run_checker(tmp)
        ids = self.rule_ids(proc)
        self.assertIn("H009", ids)
        findings = json.loads(proc.stdout)["findings"]
        self.assertTrue(any("leaks workstation path" in f["message"] for f in findings if f["rule_id"] == "H009"))

    def test_invalid_verification_status_fails(self):
        tmp = self._create_showcase_fixture(manifest_modifications={
            "flagship_0": {"verification_status": "FUTURE_VERSION"}
        })
        proc = self.run_checker(tmp)
        ids = self.rule_ids(proc)
        self.assertIn("H009", ids)
        findings = json.loads(proc.stdout)["findings"]
        self.assertTrue(any("invalid verification_status" in f["message"] for f in findings if f["rule_id"] == "H009"))

    def test_corrupt_png_fails(self):
        tmp = self._create_showcase_fixture()
        with open(os.path.join(tmp, "assets", "showcase", "demo.png"), "wb") as f:
            f.write(b"NOT_A_VALID_PNG_SIGNATURE_HEADER")
        proc = self.run_checker(tmp)
        ids = self.rule_ids(proc)
        self.assertIn("H009", ids)
        findings = json.loads(proc.stdout)["findings"]
        self.assertTrue(any("is not a valid PNG" in f["message"] for f in findings if f["rule_id"] == "H009"))

    def test_oversized_media_fails(self):
        tmp = self._create_showcase_fixture()
        with open(os.path.join(tmp, "assets", "showcase", "demo.png"), "wb") as f:
            f.write(b"\x89PNG\r\n\x1a\n" + b"\x00" * (2 * 1024 * 1024 + 100))
        proc = self.run_checker(tmp)
        ids = self.rule_ids(proc)
        self.assertIn("H009", ids)
        findings = json.loads(proc.stdout)["findings"]
        self.assertTrue(any("exceeds 2MB limit" in f["message"] for f in findings if f["rule_id"] == "H009"))

    def test_unsupported_media_extension_fails(self):
        tmp = self._create_showcase_fixture(manifest_modifications={
            "flagship_0": {"primary_media": "assets/showcase/demo.exe"}
        })
        with open(os.path.join(tmp, "assets", "showcase", "demo.exe"), "wb") as f:
            f.write(b"MZ\x00\x00")
        proc = self.run_checker(tmp)
        ids = self.rule_ids(proc)
        self.assertIn("H009", ids)
        findings = json.loads(proc.stdout)["findings"]
        self.assertTrue(any("has unsupported file extension" in f["message"] for f in findings if f["rule_id"] == "H009"))

    def test_uncataloged_media_fails_for_profile(self):
        # When project_type is profile, all 6 flagships are expected, plus no uncataloged files
        all_flagships = [
            {
                "id": fid,
                "name": fid.title(),
                "repository": f"gthgomez/{fid}",
                "source_sha": "1dc598e2a2f1de914591570349708a6f01d66479",
                "captured_version": "1.0.0",
                "capture_date": "2026-11-10",
                "demonstration_type": "web-ui-capture",
                "primary_media": "assets/showcase/demo.png",
                "supporting_media": [],
                "live_url": "https://example.com",
                "capture_method": "Screenshot",
                "test_evidence": "Passes",
                "known_limitations": "None",
                "verification_status": "CURRENT"
            }
            for fid in ("babel", "monte-carlo-ledger", "prismatix", "gba-emulator", "proofpath", "reliquary")
        ]
        tmp = self._create_showcase_fixture(
            manifest_modifications={"flagships": all_flagships},
            config_overrides={"project_type": "profile"}
        )
        # Create an uncataloged file in assets/showcase
        with open(os.path.join(tmp, "assets", "showcase", "stray.png"), "wb") as f:
            f.write(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4")
        proc = self.run_checker(tmp)
        ids = self.rule_ids(proc)
        self.assertIn("H009", ids)
        findings = json.loads(proc.stdout)["findings"]
        self.assertTrue(any("uncataloged media file on disk" in f["message"] for f in findings if f["rule_id"] == "H009"))


class SameDocumentAnchorTests(FixtureCase):
    def test_broken_same_document_fragment_fails(self):
        tmp = self.setup_fixture("clean")
        with open(os.path.join(tmp, "README.md"), "a") as f:
            f.write("\n## Target Section\n\n[bad](#no-such-anchor)\n[good](#target-section)\n")
        proc = self.run_checker(tmp)
        payload = json.loads(proc.stdout)
        h002 = [f for f in payload["findings"] if f["rule_id"] == "H002"]
        self.assertTrue(any("not found in this document" in f["message"]
                            for f in h002), h002)
        # The valid same-document anchor must not be flagged.
        self.assertEqual(len(h002), 1, h002)

    def test_valid_same_document_fragment_passes(self):
        tmp = self.setup_fixture("clean")
        with open(os.path.join(tmp, "README.md"), "a") as f:
            f.write("\n[good](#clean-fixture)\n")
        proc = self.run_checker(tmp)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    # The headings below are the six flagship headings of this repository's
    # README verbatim. Slugging the raw source (instead of the rendered text)
    # puts the link URL inside the slug and produced six blocking H002 false
    # positives on a document GitHub resolves perfectly. They must pass.
    LINK_HEADINGS = (
        ("### 1. [Babel](https://github.com/gthgomez/Babel) — AI Coding-Agent "
         "Runtime & Evidence Verifier",
         "#1-babel--ai-coding-agent-runtime--evidence-verifier"),
        ("### 2. [MonteCarlo-Ledger](https://github.com/gthgomez/MonteCarlo-Ledger) "
         "— Deterministic Cash-Flow Forecaster & Risk Engine",
         "#2-montecarlo-ledger--deterministic-cash-flow-forecaster--risk-engine"),
        ("### 3. [Prismatix](https://github.com/gthgomez/Prismatix) — Multi-Provider "
         "AI Chat with Cost Governance",
         "#3-prismatix--multi-provider-ai-chat-with-cost-governance"),
        ("### 4. [GBA_Emulator](https://github.com/gthgomez/GBA_Emulator) — C++17 "
         "Emulator Core & Conformance Lab",
         "#4-gba_emulator--c17-emulator-core--conformance-lab"),
        ("### 5. [ProofPath](https://github.com/gthgomez/ProofPath) — Offline-First "
         "Learning System with Verifiable Proofs",
         "#5-proofpath--offline-first-learning-system-with-verifiable-proofs"),
        ("### 6. [reliquary](https://github.com/gthgomez/reliquary) — "
         "Creature-Collecting Web RPG & Engine",
         "#6-reliquary--creature-collecting-web-rpg--engine"),
    )

    def test_link_headings_slug_from_rendered_text(self):
        """Regression: the six README flagships must not false-positive."""
        tmp = self.setup_fixture("clean")
        with open(os.path.join(tmp, "README.md"), "a") as f:
            f.write("\n")
            for heading, _anchor in self.LINK_HEADINGS:
                f.write(heading + "\n\n")
            f.write("## Index\n\n")
            for _heading, anchor in self.LINK_HEADINGS:
                f.write(f"- [jump]({anchor})\n")
        proc = self.run_checker(tmp)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(json.loads(proc.stdout)["findings"], [])

    def test_source_slug_of_link_heading_is_still_broken(self):
        """Negative control: the old, wrong slug must not be accepted."""
        tmp = self.setup_fixture("clean")
        with open(os.path.join(tmp, "README.md"), "a") as f:
            f.write("\n" + self.LINK_HEADINGS[0][0] + "\n\n"
                    "[bad](#1-babelhttpsgithubcomgthgomezbabel--ai-coding-agent-"
                    "runtime--evidence-verifier)\n")
        proc = self.run_checker(tmp)
        payload = json.loads(proc.stdout)
        h002 = [f for f in payload["findings"] if f["rule_id"] == "H002"]
        self.assertEqual(len(h002), 1, h002)
        self.assertIn("not found in this document", h002[0]["message"])

    def test_code_span_heading_slugs_from_its_content(self):
        tmp = self.setup_fixture("clean")
        with open(os.path.join(tmp, "README.md"), "a") as f:
            f.write("\n## `pip install tool`\n\n[good](#pip-install-tool)\n")
        proc = self.run_checker(tmp)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_broken_code_span_anchor_still_fails(self):
        tmp = self.setup_fixture("clean")
        with open(os.path.join(tmp, "README.md"), "a") as f:
            f.write("\n## `pip install tool`\n\n[bad](#pip-install)\n")
        proc = self.run_checker(tmp)
        ids = self.rule_ids(proc)
        self.assertIn("H002", ids)

    def test_image_alt_text_does_not_enter_the_slug(self):
        """Images render as <img>: their alt text is not heading text."""
        tmp = self.setup_fixture("clean")
        with open(os.path.join(tmp, "README.md"), "a") as f:
            f.write("\n## ![Screenshot of foo](assets/foo.png) Setup\n\n"
                    "[good](#setup)\n")
        proc = self.run_checker(tmp)
        findings = json.loads(proc.stdout)["findings"]
        # The image file itself is absent from the fixture, so an H002 for the
        # image target is expected; no fragment finding may be raised.
        fragment_findings = [f for f in findings
                             if f["rule_id"] == "H002" and "#" in f["evidence"]]
        self.assertEqual(fragment_findings, [])

    def test_duplicate_headings_get_numeric_suffixes(self):
        tmp = self.setup_fixture("clean")
        with open(os.path.join(tmp, "README.md"), "a") as f:
            f.write("\n## Release\n\n[one](#release)\n\n## Release\n\n"
                    "[two](#release-1)\n\n## Release\n\n[three](#release-2)\n")
        proc = self.run_checker(tmp)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_duplicate_suffix_beyond_count_fails(self):
        tmp = self.setup_fixture("clean")
        with open(os.path.join(tmp, "README.md"), "a") as f:
            f.write("\n## Release\n\n## Release\n\n[bad](#release-2)\n")
        proc = self.run_checker(tmp)
        ids = self.rule_ids(proc)
        self.assertIn("H002", ids)

    def test_explicit_html_anchor_passes(self):
        """<a name="..."> / id="..." wrappers are valid fragment targets."""
        tmp = self.setup_fixture("clean")
        with open(os.path.join(tmp, "README.md"), "a") as f:
            f.write("\n<a name=\"legacy-anchor\"></a>\n\n[good](#legacy-anchor)\n"
                    "<a id='second-one'></a>\n\n[good](#second-one)\n")
        proc = self.run_checker(tmp)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_uppercase_fragment_passes(self):
        """GitHub resolves fragments case-insensitively."""
        tmp = self.setup_fixture("clean")
        with open(os.path.join(tmp, "README.md"), "a") as f:
            f.write("\n[good](#Usage)\n")
        proc = self.run_checker(tmp)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_percent_encoded_fragment_passes(self):
        """Percent-escapes are decoded before the case-insensitive compare."""
        tmp = self.setup_fixture("clean")
        with open(os.path.join(tmp, "README.md"), "a") as f:
            f.write("\n[good](#%55sage)\n")
        proc = self.run_checker(tmp)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_reference_style_link_heading_slugs_from_label(self):
        tmp = self.setup_fixture("clean")
        with open(os.path.join(tmp, "README.md"), "a") as f:
            f.write("\n## See [the guide][guide] now\n\n"
                    "[guide]: https://example.com\n\n[good](#see-the-guide-now)\n")
        proc = self.run_checker(tmp)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_cross_document_link_heading_anchor_resolves(self):
        """The same rendered-text slug must apply to cross-document links."""
        tmp = self.setup_fixture("clean")
        with open(os.path.join(tmp, "docs", "note.md"), "a") as f:
            f.write("\n## 7. [Babel](https://github.com/gthgomez/Babel) — Runtime\n")
        with open(os.path.join(tmp, "README.md"), "a") as f:
            f.write("\n[good](docs/note.md#7-babel--runtime)\n")
        proc = self.run_checker(tmp)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)


class ConfigValidationTests(FixtureCase):
    def test_missing_public_entrypoint_is_invalid_config(self):
        tmp = self.setup_fixture("clean", config_overrides={
            "public_entrypoints": ["README.md", "docs/MISSING.md"],
        })
        proc = self.run_checker(tmp)
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
        self.assertIn("public entrypoint not found", proc.stderr)

    def test_entrypoint_without_markdown_extension_is_invalid_config(self):
        tmp = self.setup_fixture("clean", config_overrides={
            "public_entrypoints": ["LICENSE"],
        })
        proc = self.run_checker(tmp)
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)

    def test_version_pattern_without_capture_group_is_invalid_config(self):
        tmp = self.setup_fixture("clean", config_overrides={
            "version_checks": [{
                "file": "version.json",
                "pattern": r'"version":\s*"[^"]+"',
                "domain": "core", "status": "released",
                "expected_version": "1.2.3",
            }],
        })
        with open(os.path.join(tmp, "version.json"), "w") as f:
            f.write('{"version": "1.2.3"}')
        proc = self.run_checker(tmp)
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
        self.assertIn("no capture group", proc.stderr)

    def test_version_pattern_with_optional_group_that_did_not_match_is_invalid_config(self):
        """An optional first group can match with ``None``; never traceback.

        ``(v\\d+)?build`` matches ``build`` with ``m.groups() == (None,)``, which
        is truthy, so the group value must be checked before ``.strip()``.
        """
        tmp = self.setup_fixture("clean", config_overrides={
            "version_checks": [{
                "file": "version.json",
                "pattern": r"(v\d+)?build",
                "domain": "core", "status": "unreleased",
            }],
        })
        with open(os.path.join(tmp, "version.json"), "w") as f:
            f.write('{"build": 42}')
        proc = self.run_checker(tmp)
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)
        self.assertIn("ERROR: version_checks pattern", proc.stderr)
        self.assertIn("capture group did not participate", proc.stderr)
        self.assertEqual(proc.stdout.strip(), "")

    def test_version_pattern_matching_nothing_is_a_finding(self):
        tmp = self.setup_fixture("clean", config_overrides={
            "version_checks": [{
                "file": "version.json",
                "pattern": r"no such text (here)",
                "domain": "core", "status": "unreleased",
            }],
        })
        with open(os.path.join(tmp, "version.json"), "w") as f:
            f.write('{"version": "1.2.3"}')
        ids = self.rule_ids(self.run_checker(tmp))
        self.assertIn("H005", ids)
        # Exactly one H005 per non-matching pattern: no follow-on
        # "version value not found" finding for the same pattern.
        self.assertEqual(ids.count("H005"), 1, ids)


if __name__ == "__main__":
    unittest.main()
