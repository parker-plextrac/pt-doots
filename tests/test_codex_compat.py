"""Contracts for the thin Codex compatibility surface."""

from __future__ import annotations

import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = REPOSITORY_ROOT / "scripts" / "validate_codex_compat.py"


def load_validator():
    spec = importlib.util.spec_from_file_location("validate_codex_compat", VALIDATOR_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CodexCompatibilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.validator = load_validator()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def write(self, relative_path: str, content: str) -> Path:
        path = self.root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def canonical_command(self, name: str) -> None:
        self.write(
            f"commands/{name}.md",
            f"---\nname: {name}\ndescription: command\n---\n# {name}\n",
        )

    def canonical_agent(self, name: str) -> None:
        self.write(
            f"agents/{name}.md",
            f"---\nname: {name}\ndescription: agent\n---\n# {name}\n",
        )

    def skill(self, name: str) -> None:
        self.write(
            f"skills/{name}/SKILL.md",
            f"---\nname: {name}\ndescription: skill\n---\n# {name}\n",
        )

    def agent_adapter(self, name: str) -> None:
        self.write(f"codex/agents/{name}.toml", f'name = "{name}"\n')

    def test_discovers_only_top_level_canonical_definitions(self) -> None:
        self.canonical_command("ship")
        self.canonical_agent("reviewer")
        self.write("agents/reviewer/profile.md", "not an agent definition\n")

        inventories = self.validator.discover_inventories(self.root)

        self.assertEqual(inventories.commands, {"ship": self.root / "commands/ship.md"})
        self.assertEqual(inventories.agents, {"reviewer": self.root / "agents/reviewer.md"})

    def test_parses_markdown_frontmatter_and_rejects_malformed_input(self) -> None:
        good = self.write(
            "commands/ship.md",
            "---\nname: ship\ndescription: >\n  ship a release\n---\n# Ship\n",
        )
        bad = self.write("commands/bad.md", "name: bad\n# Bad\n")

        self.assertEqual(
            self.validator.parse_markdown_frontmatter(good),
            {"name": "ship", "description": "ship a release"},
        )
        with self.assertRaisesRegex(ValueError, "frontmatter"):
            self.validator.parse_markdown_frontmatter(bad)

    def test_parses_toml_adapter(self) -> None:
        adapter = self.write('codex/agents/reviewer.toml', 'name = "reviewer"\n')

        self.assertEqual(self.validator.parse_toml(adapter), {"name": "reviewer"})

    def test_validates_relative_references_without_escaping_repository(self) -> None:
        target = self.write("commands/ship.md", "content\n")

        self.assertIsNone(
            self.validator.validate_relative_reference(self.root, "commands/ship.md")
        )
        self.assertEqual(
            self.validator.validate_relative_reference(self.root, "../outside.md"),
            "relative reference escapes repository: ../outside.md",
        )
        self.assertEqual(
            self.validator.validate_relative_reference(self.root, str(target)),
            f"reference must be relative: {target}",
        )
        self.assertEqual(
            self.validator.validate_relative_reference(self.root, "commands/missing.md"),
            "relative reference does not exist: commands/missing.md",
        )

    def test_reports_missing_and_malformed_adapters(self) -> None:
        self.canonical_command("ship")
        self.canonical_agent("reviewer")
        self.write("skills/broken/SKILL.md", "not frontmatter\n")
        self.write("codex/agents/reviewer.toml", "name = [\n")

        report = self.validator.validate_repository(self.root)

        self.assertIn("missing command adapter: skills/ship/SKILL.md", report.errors)
        self.assertIn("malformed command adapter: skills/broken/SKILL.md", report.errors)
        self.assertIn("malformed agent adapter: codex/agents/reviewer.toml", report.errors)

    def test_reports_stale_adapters_that_break_exact_parity(self) -> None:
        self.canonical_command("ship")
        self.canonical_agent("reviewer")
        self.skill("ship")
        self.agent_adapter("reviewer")
        self.skill("retired-command")
        self.agent_adapter("retired-agent")

        report = self.validator.validate_repository(self.root)

        self.assertIn(
            "unexpected command adapter: skills/retired-command/SKILL.md", report.errors
        )
        self.assertIn(
            "unexpected agent adapter: codex/agents/retired-agent.toml", report.errors
        )

    def test_valid_fixture_has_adapter_parity(self) -> None:
        self.canonical_command("ship")
        self.canonical_agent("reviewer")
        self.skill("ship")
        self.agent_adapter("reviewer")

        report = self.validator.validate_repository(self.root)

        self.assertEqual(report.errors, [])
        self.assertEqual(report.command_count, 1)
        self.assertEqual(report.agent_count, 1)

    def test_current_repository_parity_fails_until_later_adapters_exist(self) -> None:
        completed = subprocess.run(
            ["python3", str(VALIDATOR_PATH), str(REPOSITORY_ROOT)],
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("Diagnostic: canonical commands=6", completed.stdout)
        self.assertIn("Diagnostic: canonical agents=15", completed.stdout)
        self.assertIn("missing command adapter: skills/pt-doots/SKILL.md", completed.stdout)
        self.assertIn("missing agent adapter: codex/agents/implementer.toml", completed.stdout)


if __name__ == "__main__":
    unittest.main()
