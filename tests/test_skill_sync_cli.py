from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "skill_sync.py"


def write_skill(root: Path, name: str, payload: str) -> Path:
    skill_dir = root / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: fixture\n---\n\n# {name}\n",
        encoding="utf-8",
    )
    (skill_dir / "payload.txt").write_text(payload, encoding="utf-8")
    return skill_dir


def write_hermes_skill(root: Path, category: str, name: str, payload: str) -> Path:
    category_dir = root / category
    category_dir.mkdir(parents=True, exist_ok=True)
    (category_dir / "DESCRIPTION.md").write_text(
        f"# {category}\n",
        encoding="utf-8",
    )
    return write_skill(category_dir, name, payload)


class SkillSyncCliTests(unittest.TestCase):
    def run_cli(self, machine_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env.update(
            {
                "HOME": str(machine_root),
                "SKILL_SYNC_AGENTS_ROOT": str(machine_root / "agents"),
                "SKILL_SYNC_CODEX_ROOT": str(machine_root / "codex"),
                "SKILL_SYNC_CLAUDE_ROOT": str(machine_root / "claude"),
                "SKILL_SYNC_HERMES_ROOT": str(machine_root / "hermes"),
                "SKILL_SYNC_OPENCODE_ROOT": str(machine_root / "opencode"),
                "SKILL_SYNC_OPENCLAW_ROOT": str(machine_root / "openclaw"),
                "SKILL_SYNC_BACKUP_ROOT": str(machine_root / "backups"),
                "SKILL_SYNC_BASELINE_STORE": str(machine_root / "baselines.json"),
            }
        )
        return subprocess.run(
            [sys.executable, str(SCRIPT_PATH), *args],
            cwd=str(REPO_ROOT),
            env=env,
            text=True,
            capture_output=True,
            check=True,
        )

    def test_export_import_apply_restore_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            machine_a = temp_root / "machine-a"
            machine_b = temp_root / "machine-b"
            manifest_path = temp_root / "agent-layout.json"

            for machine_root in (machine_a, machine_b):
                for root_name in ("agents", "codex", "backups"):
                    (machine_root / root_name).mkdir(parents=True, exist_ok=True)

            write_skill(machine_a / "agents", "demo-skill", "canonical\n")
            write_skill(machine_a / "codex", "demo-skill", "canonical\n")

            export_result = self.run_cli(
                machine_a,
                "--adopt-root",
                "agents",
                "--export-manifest",
                str(manifest_path),
                "--format",
                "json",
            )
            exported = json.loads(export_result.stdout)
            self.assertEqual(exported["kind"], "skill-sync-layout")
            self.assertEqual(exported["summary"]["importable_skills"], 1)
            self.assertEqual(exported["skills"][0]["canonical"]["platform"], "agents")
            self.assertEqual(
                exported["skills"][0]["desired_platforms"],
                ["agents", "codex"],
            )

            write_skill(machine_b / "agents", "demo-skill", "canonical\n")
            write_skill(machine_b / "codex", "demo-skill", "legacy-copy\n")

            preview_result = self.run_cli(
                machine_b,
                "--import-manifest",
                str(manifest_path),
                "--format",
                "json",
            )
            preview = json.loads(preview_result.stdout)
            self.assertEqual(len(preview["operations"]), 1)
            self.assertEqual(preview["operations"][0]["action"], "replace_with_symlink")

            apply_result = self.run_cli(
                machine_b,
                "--import-manifest",
                str(manifest_path),
                "--apply",
                "--format",
                "json",
            )
            applied = json.loads(apply_result.stdout)
            run_id = applied["run"]["run_id"]
            codex_skill = machine_b / "codex" / "demo-skill"
            self.assertTrue(codex_skill.is_symlink())
            self.assertEqual(
                codex_skill.resolve(),
                (machine_b / "agents" / "demo-skill").resolve(),
            )
            self.assertTrue((machine_b / "backups" / run_id / "manifest.json").is_file())
            self.assertTrue((machine_b / "backups" / "latest").is_symlink())

            restore_result = self.run_cli(
                machine_b,
                "--restore",
                "latest",
                "--apply",
                "--format",
                "json",
            )
            restored = json.loads(restore_result.stdout)
            self.assertEqual(restored["run_id"], run_id)
            self.assertFalse(codex_skill.is_symlink())
            self.assertEqual((codex_skill / "payload.txt").read_text(encoding="utf-8"), "legacy-copy\n")

    def test_hermes_nested_skills_are_discovered_and_syncable(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            machine_root = Path(temp_dir)
            for root_name in ("codex", "hermes"):
                (machine_root / root_name).mkdir(parents=True, exist_ok=True)

            write_skill(machine_root / "hermes", "office-hours", "portable\n")
            write_hermes_skill(
                machine_root / "hermes",
                "apple",
                "apple-reminders",
                "portable\n",
            )

            result = self.run_cli(
                machine_root,
                "--format",
                "json",
            )
            report = json.loads(result.stdout)
            roots = {(root["platform"], root["path"]) for root in report["roots"]}
            self.assertIn(("hermes", str(machine_root / "hermes")), roots)

            groups = {group["name"]: group for group in report["groups"]}
            self.assertIn("office-hours", groups)
            self.assertIn("apple-reminders", groups)
            self.assertNotIn("apple", groups)

            planned_links = {item["name"]: item for item in report["planned_links"]}
            self.assertIn("office-hours", planned_links)
            self.assertIn("apple-reminders", planned_links)
            self.assertIn(
                str(machine_root / "codex" / "office-hours"),
                {destination["path"] for destination in planned_links["office-hours"]["destinations"]},
            )
            self.assertIn(
                str(machine_root / "codex" / "apple-reminders"),
                {
                    destination["path"]
                    for destination in planned_links["apple-reminders"]["destinations"]
                },
            )

    def test_drift_states_pristine_dirty_local_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            machine_root = Path(temp_dir)
            for root_name in ("agents", "codex"):
                (machine_root / root_name).mkdir(parents=True, exist_ok=True)

            write_skill(machine_root / "agents", "alpha", "upstream\n")
            write_skill(machine_root / "codex", "alpha", "upstream\n")
            write_skill(machine_root / "agents", "gamma", "upstream\n")

            record_result = self.run_cli(machine_root, "--record-baseline", "--format", "json")
            recorded = json.loads(record_result.stdout)
            self.assertEqual(recorded["updated"], ["alpha", "gamma"])
            self.assertTrue((machine_root / "baselines.json").is_file())

            (machine_root / "codex" / "alpha" / "payload.txt").write_text(
                "customized\n", encoding="utf-8"
            )
            write_skill(machine_root / "codex", "beta", "born-local\n")

            drift_result = self.run_cli(machine_root, "--check-drift", "--format", "json")
            drift = json.loads(drift_result.stdout)
            states = {skill["name"]: skill["state"] for skill in drift["skills"]}
            self.assertEqual(states["alpha"], "dirty")
            self.assertEqual(states["beta"], "local-only")
            self.assertEqual(states["gamma"], "pristine")
            self.assertEqual(drift["summary"]["dirty"], 1)
            alpha = next(skill for skill in drift["skills"] if skill["name"] == "alpha")
            self.assertIn(str(machine_root / "codex" / "alpha"), alpha["dirty_paths"])

    def test_dedupe_protects_dirty_copies_unless_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            machine_root = Path(temp_dir)
            for root_name in ("agents", "codex"):
                (machine_root / root_name).mkdir(parents=True, exist_ok=True)

            agents_alpha = write_skill(machine_root / "agents", "alpha", "upstream\n")
            codex_alpha = write_skill(machine_root / "codex", "alpha", "upstream\n")

            self.run_cli(machine_root, "--record-baseline", "--format", "json")

            # The user customizes the codex copy, then a fresh upstream
            # reinstall lands in agents with a newer mtime.
            (codex_alpha / "payload.txt").write_text("customized\n", encoding="utf-8")
            (agents_alpha / "payload.txt").write_text("upstream-v2\n", encoding="utf-8")
            old = 1_600_000_000
            new = 1_700_000_000
            for skill_dir, stamp in ((codex_alpha, old), (agents_alpha, new)):
                for item in [skill_dir, *skill_dir.rglob("*")]:
                    os.utime(item, (stamp, stamp))

            preview = json.loads(
                self.run_cli(
                    machine_root,
                    "--dedupe",
                    "--strategy",
                    "prefer-latest",
                    "--format",
                    "json",
                ).stdout
            )
            plan = next(item for item in preview["dedupe_plan"] if item["name"] == "alpha")
            self.assertEqual(plan["replacements"], [])
            self.assertEqual(len(plan["skipped_dirty"]), 1)
            self.assertEqual(plan["skipped_dirty"][0]["path"], str(codex_alpha))
            self.assertEqual(preview["summary"]["planned_dedupe_replacements"], 0)
            self.assertEqual(preview["summary"]["dedupe_skipped_dirty"], 1)

            allowed = json.loads(
                self.run_cli(
                    machine_root,
                    "--dedupe",
                    "--strategy",
                    "prefer-latest",
                    "--allow-dirty",
                    "--format",
                    "json",
                ).stdout
            )
            plan = next(item for item in allowed["dedupe_plan"] if item["name"] == "alpha")
            self.assertEqual(len(plan["replacements"]), 1)
            self.assertEqual(plan["skipped_dirty"], [])


if __name__ == "__main__":
    unittest.main()
