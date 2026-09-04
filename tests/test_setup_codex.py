"""Tests for safe, checkout-backed Codex onboarding."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from scripts import setup_codex


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


class SetupCodexTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name) / "checkout"
        self.home = Path(self.temporary_directory.name) / "home"
        self.write("codex/agents/alpha.toml", 'name = "alpha"\n')
        self.write(".agents/plugins/marketplace.json", "{}\n")
        self.validator_runner = Mock(
            return_value=subprocess.CompletedProcess([], 0, stdout="ok", stderr="")
        )
        self.cli_runner = Mock(
            return_value=subprocess.CompletedProcess([], 0, stdout="registered", stderr="")
        )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def write(self, relative_path: str, contents: str) -> Path:
        path = self.root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents, encoding="utf-8")
        return path

    def setup(self, **kwargs: object) -> setup_codex.SetupResult:
        return setup_codex.setup_codex(
            checkout=self.root,
            home=self.home,
            validator_runner=self.validator_runner,
            cli_runner=self.cli_runner,
            **kwargs,
        )

    def test_creates_live_agent_links_after_preflight(self) -> None:
        result = self.setup(links_only=True)

        destination = self.home / ".codex" / "agents" / "alpha.toml"
        self.assertTrue(destination.is_symlink())
        self.assertEqual(destination.resolve(), (self.root / "codex/agents/alpha.toml").resolve())
        self.assertEqual(result.linked, (destination,))
        self.assertEqual(
            self.validator_runner.call_args.args[0],
            [
                sys.executable,
                str(self.root.resolve() / "scripts/validate_codex_compat.py"),
                str(self.root.resolve()),
            ],
        )

    def test_correct_owned_link_is_idempotent(self) -> None:
        self.setup(links_only=True)

        result = self.setup(links_only=True)

        self.assertEqual(result.linked, ())
        self.assertEqual(result.unchanged, (self.home / ".codex/agents/alpha.toml",))

    def test_refuses_colliding_files_and_non_owned_links(self) -> None:
        destination = self.home / ".codex" / "agents" / "alpha.toml"
        destination.parent.mkdir(parents=True)
        foreign = self.write("foreign/alpha.toml", 'name = "foreign"\n')

        collisions: dict[str, object] = {
            "real file": lambda: destination.write_text("keep", encoding="utf-8"),
            "broken symlink": lambda: destination.symlink_to(self.root / "missing.toml"),
            "foreign symlink": lambda: destination.symlink_to(foreign),
            "other checkout link": lambda: destination.symlink_to(
                Path(self.temporary_directory.name) / "other/codex/agents/alpha.toml"
            ),
        }
        for label, create in collisions.items():
            with self.subTest(label=label):
                if destination.exists() or destination.is_symlink():
                    destination.unlink()
                if label == "other checkout link":
                    other_source = Path(self.temporary_directory.name) / "other/codex/agents/alpha.toml"
                    other_source.parent.mkdir(parents=True, exist_ok=True)
                    other_source.write_text('name = "other"\n', encoding="utf-8")
                create()
                with self.assertRaisesRegex(setup_codex.SetupError, "refusing to overwrite"):
                    self.setup(links_only=True)

    def test_refuses_a_symlinked_codex_agent_directory(self) -> None:
        external_directory = Path(self.temporary_directory.name) / "external-agents"
        external_directory.mkdir()
        codex_directory = self.home / ".codex"
        codex_directory.mkdir(parents=True)
        (codex_directory / "agents").symlink_to(external_directory, target_is_directory=True)

        with self.assertRaisesRegex(
            setup_codex.SetupError, "refusing to use symlinked Codex agent directory"
        ):
            self.setup(links_only=True)

        self.assertFalse((external_directory / "alpha.toml").exists())

    def test_dry_run_does_not_create_links_or_register_marketplace(self) -> None:
        result = self.setup(dry_run=True)

        self.assertFalse((self.home / ".codex").exists())
        self.assertEqual(result.linked, (self.home / ".codex/agents/alpha.toml",))
        self.assertTrue(result.dry_run)
        self.cli_runner.assert_not_called()
        self.assertIn("codex plugin marketplace add", result.manual_command)

    def test_links_only_skips_registration_and_reports_manual_command(self) -> None:
        result = self.setup(links_only=True)

        self.cli_runner.assert_not_called()
        self.assertIn(str(self.root.resolve()), result.manual_command)

    def test_uninstall_removes_only_owned_links(self) -> None:
        owned = self.home / ".codex" / "agents" / "alpha.toml"
        foreign = self.home / ".codex" / "agents" / "foreign.toml"
        real_file = self.home / ".codex" / "agents" / "note.txt"
        owned.parent.mkdir(parents=True)
        owned.symlink_to(self.root / "codex/agents/alpha.toml")
        foreign_target = Path(self.temporary_directory.name) / "external/foreign.toml"
        foreign_target.parent.mkdir(parents=True)
        foreign_target.write_text('name = "foreign"\n', encoding="utf-8")
        foreign.symlink_to(foreign_target)
        real_file.write_text("keep", encoding="utf-8")

        result = self.setup(uninstall=True)

        self.assertFalse(owned.exists())
        self.assertTrue(foreign.is_symlink())
        self.assertEqual(real_file.read_text(encoding="utf-8"), "keep")
        self.assertEqual(result.removed, (owned,))
        self.assertEqual(result.preserved, (foreign, real_file))
        self.cli_runner.assert_not_called()

    def test_uninstall_preserves_broken_link_lexically_pointing_to_checkout(self) -> None:
        destination = self.home / ".codex" / "agents" / "stale.toml"
        destination.parent.mkdir(parents=True)
        destination.symlink_to(self.root / "codex/agents/removed.toml")

        result = self.setup(uninstall=True)

        self.assertTrue(destination.is_symlink())
        self.assertEqual(result.removed, ())
        self.assertEqual(result.preserved, (destination,))

    def test_uninstall_preserves_same_checkout_links_that_are_not_owned_pairs(self) -> None:
        directory = self.home / ".codex" / "agents"
        directory.mkdir(parents=True)
        non_adapter_target = self.write("reference/notes.md", "keep\n")
        non_adapter = directory / "same-checkout-reference.toml"
        renamed_adapter = directory / "renamed-alpha.toml"
        non_adapter.symlink_to(non_adapter_target)
        renamed_adapter.symlink_to(self.root / "codex/agents/alpha.toml")

        result = self.setup(uninstall=True)

        self.assertTrue(non_adapter.is_symlink())
        self.assertTrue(renamed_adapter.is_symlink())
        self.assertEqual(result.removed, ())
        self.assertEqual(result.preserved, (renamed_adapter, non_adapter))

    def test_preflight_failure_prevents_any_mutation(self) -> None:
        self.validator_runner.return_value = subprocess.CompletedProcess(
            [], 1, stdout="missing adapter", stderr=""
        )

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

    def test_cli_registration_uses_marketplace_directory_source(self) -> None:
        self.setup()

        self.assertEqual(
            self.cli_runner.call_args.args[0],
            [
                "codex",
                "plugin",
                "marketplace",
                "add",
                str(self.root.resolve()),
            ],
        )
        self.assertTrue((Path(self.cli_runner.call_args.args[0][-1]) / ".agents/plugins/marketplace.json").is_file())

    def test_setup_refuses_parent_directory_swap_before_link_creation(self) -> None:
        external_directory = Path(self.temporary_directory.name) / "external-agents"
        external_directory.mkdir()
        agents_directory = self.home / ".codex" / "agents"

        def swap_parent(event: str, destination: Path) -> None:
            if event != "before_link":
                return
            agents_directory.rename(agents_directory.with_name("agents-original"))
            agents_directory.symlink_to(external_directory, target_is_directory=True)

        with self.assertRaisesRegex(setup_codex.SetupError, "Codex agent directory changed"):
            self.setup(links_only=True, mutation_hook=swap_parent)

        self.assertFalse((external_directory / "alpha.toml").exists())
        self.assertFalse((self.home / ".codex/agents-original/alpha.toml").exists())

    def test_uninstall_refuses_destination_swap_before_unlink(self) -> None:
        destination = self.home / ".codex" / "agents" / "alpha.toml"
        destination.parent.mkdir(parents=True)
        destination.symlink_to(self.root / "codex/agents/alpha.toml")

        def replace_destination(event: str, candidate: Path) -> None:
            if event != "before_unlink":
                return
            candidate.unlink()
            candidate.write_text("do not delete", encoding="utf-8")

        with self.assertRaisesRegex(setup_codex.SetupError, "refusing to remove changed agent destination"):
            self.setup(uninstall=True, mutation_hook=replace_destination)

        self.assertEqual(destination.read_text(encoding="utf-8"), "do not delete")

    def test_checkout_root_is_derived_from_script_location(self) -> None:
        self.assertEqual(setup_codex.checkout_root(), REPOSITORY_ROOT)

    def test_repo_marketplace_entry_resolves_to_plugin_checkout_root(self) -> None:
        marketplace_path = REPOSITORY_ROOT / ".agents/plugins/marketplace.json"
        marketplace = json.loads(marketplace_path.read_text(encoding="utf-8"))

        self.assertEqual(marketplace["name"], "pt-doots-local")
        self.assertEqual(marketplace["interface"]["displayName"], "pt-doots local checkout")
        self.assertEqual(len(marketplace["plugins"]), 1)
        entry = marketplace["plugins"][0]
        self.assertEqual(entry["name"], "pt-doots")
        self.assertEqual(entry["source"]["source"], "local")
        self.assertEqual((marketplace_path.parent / entry["source"]["path"]).resolve(), REPOSITORY_ROOT)
        self.assertEqual(entry["policy"], {"installation": "AVAILABLE", "authentication": "ON_INSTALL"})
        self.assertEqual(entry["category"], "Productivity")


if __name__ == "__main__":
    unittest.main()
