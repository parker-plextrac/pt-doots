"""Tests for direct, checkout-backed Codex named-agent onboarding."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest.mock import create_autospec

from scripts import setup_codex


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


class SetupCodexTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name) / "checkout"
        self.home = Path(self.temporary_directory.name) / "home"
        self.write("codex/agents/alpha.toml", 'name = "alpha"\n')
        self.write("codex/agents/beta.toml", 'name = "beta"\n')
        self.write(".codex-plugin/plugin.json", '{"name": "pt-doots"}\n')
        self.write(".agents/plugins/marketplace.json", '{"name": "pt-doots-local"}\n')
        self.validator_runner = create_autospec(
            subprocess.run,
            return_value=subprocess.CompletedProcess([], 0, stdout="ok", stderr=""),
        )
        self.cli_runner = create_autospec(
            subprocess.run,
            return_value=subprocess.CompletedProcess([], 0, stdout="registered", stderr=""),
        )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def write(self, relative_path: str, contents: str) -> Path:
        path = self.root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents, encoding="utf-8")
        return path

    def setup(self, **kwargs: object) -> setup_codex.SetupResult:
        return setup_codex.setup_codex(checkout=self.root, home=self.home, validator_runner=self.validator_runner, cli_runner=self.cli_runner, **kwargs)

    @property
    def config_path(self) -> Path:
        return self.home / ".codex" / "config.toml"

    def test_registers_direct_config_files_for_every_adapter_after_preflight(self) -> None:
        result = self.setup(links_only=True)

        config = tomllib.loads(self.config_path.read_text(encoding="utf-8"))
        self.assertEqual(config["agents"]["alpha"]["config_file"], str((self.root / "codex/agents/alpha.toml").resolve()))
        self.assertEqual(config["agents"]["beta"]["config_file"], str((self.root / "codex/agents/beta.toml").resolve()))
        self.assertEqual(result.registered, ("alpha", "beta"))
        self.assertFalse((self.home / ".codex" / "agents").exists())
        self.assertEqual(self.validator_runner.call_args.args[0], [sys.executable, str(self.root.resolve() / "scripts/validate_codex_compat.py"), str(self.root.resolve())])

    def test_correct_direct_registrations_are_idempotent(self) -> None:
        self.setup(links_only=True)

        result = self.setup(links_only=True)

        self.assertEqual(result.registered, ())
        self.assertEqual(result.unchanged, ("alpha", "beta"))
        self.assertEqual(self.config_path.read_text(encoding="utf-8").count(setup_codex.MANAGED_BLOCK_START), 1)

    def test_preserves_unrelated_config_and_unrelated_named_agents(self) -> None:
        original = 'model = "gpt-5.6"\n\n[agents."foreign"]\nconfig_file = "/tmp/foreign.toml"\n'
        self.config_path.parent.mkdir(parents=True)
        self.config_path.write_text(original, encoding="utf-8")

        self.setup(links_only=True)

        contents = self.config_path.read_text(encoding="utf-8")
        config = tomllib.loads(contents)
        self.assertIn(original.rstrip(), contents)
        self.assertEqual(config["model"], "gpt-5.6")
        self.assertEqual(config["agents"]["foreign"]["config_file"], "/tmp/foreign.toml")

    def test_matching_unmanaged_registration_is_preserved_and_idempotent(self) -> None:
        self.config_path.parent.mkdir(parents=True)
        self.config_path.write_text(f'[agents."alpha"]\nconfig_file = {json.dumps(str((self.root / "codex/agents/alpha.toml").resolve()))}\n', encoding="utf-8")

        result = self.setup(links_only=True)

        self.assertEqual(result.registered, ("beta",))
        self.assertEqual(result.unchanged, ("alpha",))

    def test_refuses_foreign_registration_collision_without_mutating_config(self) -> None:
        original = '[agents."alpha"]\nconfig_file = "/tmp/foreign.toml"\n'
        self.config_path.parent.mkdir(parents=True)
        self.config_path.write_text(original, encoding="utf-8")

        with self.assertRaisesRegex(setup_codex.SetupError, "refusing to overwrite existing named-agent registration: alpha"):
            self.setup(links_only=True)

        self.assertEqual(self.config_path.read_text(encoding="utf-8"), original)

    def test_full_setup_detects_collision_before_cli_registration(self) -> None:
        original = '[agents."alpha"]\nconfig_file = "/tmp/foreign.toml"\n'
        self.config_path.parent.mkdir(parents=True)
        self.config_path.write_text(original, encoding="utf-8")

        with self.assertRaisesRegex(
            setup_codex.SetupError,
            "refusing to overwrite existing named-agent registration: alpha",
        ):
            self.setup()

        self.cli_runner.assert_not_called()
        self.assertEqual(self.config_path.read_text(encoding="utf-8"), original)

    def test_dry_run_does_not_create_config_or_register_marketplace(self) -> None:
        result = self.setup(dry_run=True)

        self.assertFalse(self.config_path.exists())
        self.assertEqual(result.registered, ("alpha", "beta"))
        self.assertTrue(result.dry_run)
        self.cli_runner.assert_not_called()
        self.assertIn("codex plugin marketplace add", result.manual_command)

    def test_agents_only_skips_registration_and_reports_manual_command(self) -> None:
        result = self.setup(links_only=True)

        self.cli_runner.assert_not_called()
        self.assertIn(str(self.root.resolve()), result.manual_command)

    def test_uninstall_removes_only_installer_owned_registrations(self) -> None:
        self.config_path.parent.mkdir(parents=True)
        self.config_path.write_text('model = "gpt-5.6"\n\n[agents."foreign"]\nconfig_file = "/tmp/foreign.toml"\n', encoding="utf-8")
        self.setup(links_only=True)

        result = self.setup(uninstall=True)

        config = tomllib.loads(self.config_path.read_text(encoding="utf-8"))
        self.assertEqual(config["model"], "gpt-5.6")
        self.assertEqual(config["agents"], {"foreign": {"config_file": "/tmp/foreign.toml"}})
        self.assertEqual(result.removed, ("alpha", "beta"))
        self.cli_runner.assert_not_called()

    def test_uninstall_preserves_unmanaged_matching_registration(self) -> None:
        self.config_path.parent.mkdir(parents=True)
        self.config_path.write_text(f'[agents."alpha"]\nconfig_file = {json.dumps(str((self.root / "codex/agents/alpha.toml").resolve()))}\n', encoding="utf-8")
        self.setup(links_only=True)

        self.setup(uninstall=True)

        config = tomllib.loads(self.config_path.read_text(encoding="utf-8"))
        self.assertIn("alpha", config["agents"])
        self.assertNotIn("beta", config["agents"])

    def test_uninstall_removes_retired_agent_from_owned_block(self) -> None:
        self.setup(links_only=True)
        (self.root / "codex/agents/beta.toml").unlink()

        result = self.setup(uninstall=True)

        self.assertEqual(result.removed, ("alpha", "beta"))
        self.assertEqual(self.config_path.read_text(encoding="utf-8"), "")

    def test_uninstall_preserves_edited_managed_agent_entry(self) -> None:
        self.setup(links_only=True)
        contents = self.config_path.read_text(encoding="utf-8").replace(
            f'config_file = {json.dumps(str((self.root / "codex/agents/alpha.toml").resolve()))}',
            f'config_file = {json.dumps(str((self.root / "codex/agents/alpha.toml").resolve()))}\nuser_added = "retain-me"',
        )
        self.config_path.write_text(contents, encoding="utf-8")

        self.setup(uninstall=True)

        config = tomllib.loads(self.config_path.read_text(encoding="utf-8"))
        self.assertEqual(config["agents"]["alpha"]["user_added"], "retain-me")
        self.assertNotIn("beta", config["agents"])

    def test_uninstall_preserves_unrelated_table_after_owned_entry(self) -> None:
        self.setup(links_only=True)
        contents = self.config_path.read_text(encoding="utf-8").replace(
            f'[agents.{json.dumps("beta")}]',
            '[custom]\nvalue = "retain-me"\n\n'
            f'[agents.{json.dumps("beta")}]',
        )
        self.config_path.write_text(contents, encoding="utf-8")

        self.setup(uninstall=True)

        config = tomllib.loads(self.config_path.read_text(encoding="utf-8"))
        self.assertEqual(config["custom"]["value"], "retain-me")

    def test_preflight_failure_prevents_any_mutation(self) -> None:
        self.validator_runner.return_value = subprocess.CompletedProcess([], 1, stdout="missing adapter", stderr="")

        with self.assertRaisesRegex(setup_codex.SetupError, "compatibility preflight failed"):
            self.setup(links_only=True)

        self.assertFalse(self.home.exists())
        self.cli_runner.assert_not_called()

    def test_unavailable_preflight_fails_closed_before_any_mutation(self) -> None:
        self.validator_runner.side_effect = OSError("validator unavailable")

        with self.assertRaisesRegex(setup_codex.SetupError, "compatibility preflight could not run"):
            self.setup(links_only=True)

        self.assertFalse(self.home.exists())
        self.cli_runner.assert_not_called()

    def test_symlinked_config_path_fails_closed(self) -> None:
        self.config_path.parent.mkdir(parents=True)
        target = self.root / "foreign-config.toml"
        target.write_text("", encoding="utf-8")
        self.config_path.symlink_to(target)

        with self.assertRaisesRegex(setup_codex.SetupError, "refusing to modify symlinked Codex configuration"):
            self.setup(links_only=True)

    def test_cli_setup_registers_marketplace_and_installs_plugin(self) -> None:
        self.setup()

        self.assertEqual([call.args[0] for call in self.cli_runner.call_args_list], [["codex", "plugin", "marketplace", "add", str(self.root.resolve())], ["codex", "plugin", "add", "pt-doots@pt-doots-local"]])

    def test_cli_failure_is_nonzero_and_does_not_mutate_config(self) -> None:
        self.cli_runner.return_value = subprocess.CompletedProcess(
            [], 1, stdout="", stderr="plugin rejected"
        )

        with self.assertRaisesRegex(setup_codex.SetupError, "plugin rejected"):
            self.setup()

        self.assertFalse(self.config_path.exists())

    def test_unavailable_cli_is_nonzero_and_does_not_mutate_config(self) -> None:
        self.cli_runner.side_effect = OSError("codex unavailable")

        with self.assertRaisesRegex(setup_codex.SetupError, "codex unavailable"):
            self.setup()

        self.assertFalse(self.config_path.exists())

    def test_checkout_root_is_derived_from_script_location(self) -> None:
        self.assertEqual(setup_codex.checkout_root(), REPOSITORY_ROOT)

    def test_repo_marketplace_entry_resolves_to_plugin_checkout_root(self) -> None:
        marketplace = json.loads((REPOSITORY_ROOT / ".agents/plugins/marketplace.json").read_text(encoding="utf-8"))
        entry = marketplace["plugins"][0]
        self.assertEqual(marketplace["name"], "pt-doots-local")
        self.assertEqual(marketplace["interface"]["displayName"], "pt-doots local checkout")
        self.assertEqual(entry["name"], "pt-doots")
        self.assertEqual(entry["source"]["source"], "local")
        self.assertEqual(entry["source"]["path"], ".")
        self.assertEqual((REPOSITORY_ROOT / entry["source"]["path"]).resolve(), REPOSITORY_ROOT)
        self.assertEqual(entry["policy"], {"installation": "AVAILABLE", "authentication": "ON_INSTALL"})
        self.assertEqual(entry["category"], "Productivity")


if __name__ == "__main__":
    unittest.main()
