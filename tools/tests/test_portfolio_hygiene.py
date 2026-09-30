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


if __name__ == "__main__":
    unittest.main()
