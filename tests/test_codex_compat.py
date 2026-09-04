"""Contracts for the thin Codex compatibility surface."""

from __future__ import annotations

import importlib.util
import json
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
        self.external_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.external_dir.cleanup()
        self.temp_dir.cleanup()

    def write(self, relative_path: str, content: str) -> Path:
        path = self.root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def symlink(self, relative_path: str, target: Path) -> Path:
        path = self.root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.symlink_to(target)
        return path

    def canonical_command(self, name: str) -> None:
        self.write(
            f"commands/{name}.md",
            f"---\nname: {name}\ndescription: command\n---\n# {name}\n",
        )

    def canonical_agent(self, name: str) -> None:
        self.write(
            f"agents/{name}.md",
            "---\n"
            f"name: {name}\n"
            "description: agent\n"
            "model: sonnet\n"
            "effort: high\n"
            "maxTurns: 10\n"
            "tools: Read Grep Glob\n"
            "---\n"
            f"# {name}\n",
        )

    def skill(self, name: str) -> None:
        self.write(
            f"skills/{name}/SKILL.md",
            f"---\nname: {name}\ndescription: skill\n---\n# {name}\n",
        )

    def agent_adapter(self, name: str) -> None:
        self.write(
            f"codex/agents/{name}.toml",
            f'''name = "{name}"
description = "agent"
model = "gpt-5.6-terra"
model_reasoning_effort = "high"
sandbox_mode = "read-only"
developer_instructions = """Locate the PlexTrac workspace by walking upward for product-core-backend, product-core-frontend, product-services-export, and product-services-mcp. Load the complete canonical agent file at pt-doots/agents/{name}.md before work; the canonical file wins on behavior.

Treat the original maxTurns 10 as an interaction/tool-call budget. Run one task turn only. If exhausted, return the required canonical output marked PARTIAL or BLOCKED; only the orchestrator may follow up."""
''',
        )

    def test_discovers_only_top_level_canonical_definitions(self) -> None:
        self.canonical_command("ship")
        self.canonical_agent("reviewer")
        self.write("agents/reviewer/profile.md", "not an agent definition\n")

        inventories = self.validator.discover_inventories(self.root)

        self.assertEqual(inventories.commands, {"ship": self.root / "commands/ship.md"})
        self.assertEqual(inventories.agents, {"reviewer": self.root / "agents/reviewer.md"})

    def test_tests_directory_is_an_importable_package(self) -> None:
        self.assertTrue((REPOSITORY_ROOT / "tests" / "__init__.py").is_file())

    def test_codex_manifest_reuses_plugin_identity_and_declares_skills(self) -> None:
        codex_manifest_path = REPOSITORY_ROOT / ".codex-plugin" / "plugin.json"
        claude_manifest_path = REPOSITORY_ROOT / ".claude-plugin" / "plugin.json"
        if not codex_manifest_path.is_file():
            self.fail("Codex plugin manifest is missing")

        codex_manifest = json.loads(codex_manifest_path.read_text(encoding="utf-8"))
        claude_manifest = json.loads(claude_manifest_path.read_text(encoding="utf-8"))

        self.assertEqual(codex_manifest["name"], claude_manifest["name"])
        self.assertEqual(codex_manifest["version"], claude_manifest["version"])
        self.assertEqual(codex_manifest["skills"], "./skills/")
        self.assertNotIn("mcpServers", codex_manifest)

    def test_command_skill_wrappers_have_exact_thin_canonical_mapping(self) -> None:
        command_names = set(self.validator.discover_inventories(REPOSITORY_ROOT).commands)
        skill_paths = sorted((REPOSITORY_ROOT / "skills").glob("*/SKILL.md"))
        self.assertEqual({path.parent.name for path in skill_paths}, command_names)

        for name in command_names:
            path = REPOSITORY_ROOT / "skills" / name / "SKILL.md"
            if not path.is_file():
                self.fail(f"Codex skill wrapper is missing: {path}")
            contents = path.read_text(encoding="utf-8")
            frontmatter = self.validator.parse_markdown_frontmatter(path)
            body = contents.split("\n---\n", 1)[1]

            self.assertEqual(frontmatter["name"], name)
            self.assertTrue(frontmatter.get("description", "").strip())
            self.assertEqual(body.count(f"commands/{name}.md"), 1)
            self.assertIn("PLUGIN_ROOT", body)
            self.assertIn("complete canonical command file", body)
            self.assertIn("reference/codex-compatibility.md", body)
            self.assertIn("runtime translation", body)
            self.assertIn("argument semantics and approval gates", body)
            self.assertLessEqual(len(body), 800)
            self.assertNotIn("```", body)

    def test_runtime_mapping_covers_phase_one_translation_contract(self) -> None:
        mapping_path = REPOSITORY_ROOT / "reference" / "codex-compatibility.md"
        if not mapping_path.is_file():
            self.fail("Codex runtime compatibility mapping is missing")
        mapping = mapping_path.read_text(encoding="utf-8")

        required_topics = (
            "Named-agent dispatch",
            "haiku → gpt-5.6-luna",
            "sonnet → gpt-5.6-terra",
            "opus → gpt-5.6-sol",
            "advisory",
            "maxTurns",
            "canonical file wins",
            "inline complete context",
            "progress.md",
            "before dispatch",
            "after each step",
            "one decision at a time",
            "flag-and-wait",
            "completion barrier",
            "real agent result",
            "worktree isolation",
            "tool-name",
            "${HOME}/.claude/pt-doots",
            "REST helper",
            "Atlassian MCP",
            "never reads or writes product source",
            "parallel quality gate",
            "repro-verifier",
            "documentation gate",
            "~/.codex/agents",
            "symlink",
            "spawn_agent",
            "followup_task",
            "wait_agent",
            "read-only",
            "workspace-write",
            "one task turn",
            "not a hard runtime limit",
        )
        for topic in required_topics:
            self.assertIn(topic, mapping)
        self.assertLessEqual(len(mapping), 6000)

    def test_runtime_mapping_fails_closed_when_named_agent_dispatch_is_unavailable(self) -> None:
        mapping = (
            REPOSITORY_ROOT / "reference" / "codex-compatibility.md"
        ).read_text(encoding="utf-8")
        normalized_mapping = " ".join(mapping.split())

        required_guardrails = (
            "registered custom agent name",
            "not selected",
            "STOP",
            "must not fall back to a generic or prompt-only agent",
            "Task 7",
            "fresh-session integration gate",
            "Successful named-agent selection",
            "model, sandbox, and developer instructions",
            "Only after the runtime confirms named-agent selection",
        )
        for guardrail in required_guardrails:
            self.assertIn(guardrail, normalized_mapping)
        self.assertNotIn("sandbox_mode is inherited by that task", mapping)
        self.assertNotIn("adapter selects the minimum mode", mapping)

    def test_command_skills_read_canonical_command_before_runtime_mapping(self) -> None:
        command_names = self.validator.discover_inventories(REPOSITORY_ROOT).commands
        for name in command_names:
            contents = (REPOSITORY_ROOT / "skills" / name / "SKILL.md").read_text(
                encoding="utf-8"
            )
            self.assertLess(
                contents.index(f"commands/{name}.md"),
                contents.index("reference/codex-compatibility.md"),
            )
            self.assertIn("If it conflicts with the canonical command", contents)

    def test_agent_adapters_match_canonical_metadata_and_runtime_contract(self) -> None:
        canonical_agents = self.validator.discover_inventories(REPOSITORY_ROOT).agents
        adapter_paths = sorted((REPOSITORY_ROOT / "codex" / "agents").glob("*.toml"))
        adapter_names = {path.stem for path in adapter_paths}
        if adapter_names != set(canonical_agents):
            self.fail("Codex agent adapters must exactly match top-level canonical agents")

        model_mapping = {
            "haiku": "gpt-5.6-luna",
            "sonnet": "gpt-5.6-terra",
            "opus": "gpt-5.6-sol",
        }
        writers = {
            "implementer",
            "test-writer",
            "team-manager",
            "documentarian",
            "repro-verifier",
        }
        for name, canonical_path in canonical_agents.items():
            canonical = self.validator.parse_markdown_frontmatter(canonical_path)
            adapter = self.validator.parse_toml(
                REPOSITORY_ROOT / "codex" / "agents" / f"{name}.toml"
            )
            instructions = adapter["developer_instructions"]
            canonical_tools = canonical.get("tools", "").split()

            self.assertEqual(adapter["name"], canonical["name"])
            self.assertEqual(adapter["description"], canonical["description"])
            self.assertEqual(adapter["model"], model_mapping[canonical["model"]])
            self.assertEqual(adapter["model_reasoning_effort"], canonical["effort"])
            expected_sandbox = "workspace-write" if name in writers else "read-only"
            self.assertEqual(adapter["sandbox_mode"], expected_sandbox)
            self.assertEqual("Write" in canonical_tools, name in writers)
            self.assertIsInstance(instructions, str)
            self.assertIn("walking upward", instructions)
            self.assertIn("product-core-backend", instructions)
            self.assertIn(f"pt-doots/agents/{name}.md", instructions)
            self.assertIn("complete canonical agent file", instructions)
            self.assertIn("canonical file wins", instructions)
            self.assertIn(canonical["maxTurns"], instructions)
            self.assertIn("interaction/tool-call budget", instructions)
            self.assertIn("one task turn only", instructions)
            self.assertIn("PARTIAL", instructions)
            self.assertIn("BLOCKED", instructions)
            self.assertIn("only the orchestrator may follow up", instructions)
            self.assertLessEqual(len(instructions), 1400)
            self.assertNotIn("##", instructions)

        repro_instructions = self.validator.parse_toml(
            REPOSITORY_ROOT / "codex" / "agents" / "repro-verifier.toml"
        )["developer_instructions"]
        self.assertIn("must not write application code", repro_instructions)

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

    def test_rejects_semantically_invalid_agent_adapters(self) -> None:
        self.canonical_agent("reviewer")
        valid = (self.root / "codex" / "agents" / "reviewer.toml")
        self.agent_adapter("reviewer")
        valid_contents = valid.read_text(encoding="utf-8")
        cases = {
            "wrong name": valid_contents.replace('name = "reviewer"', 'name = "other"'),
            "missing fields": 'name = "reviewer"\n',
            "invalid model": valid_contents.replace("gpt-5.6-terra", "not-a-model"),
            "invalid reasoning": valid_contents.replace('model_reasoning_effort = "high"', 'model_reasoning_effort = "low"'),
            "invalid sandbox": valid_contents.replace('sandbox_mode = "read-only"', 'sandbox_mode = "workspace-write"'),
            "unsafe prompt reference": valid_contents.replace(
                "pt-doots/agents/reviewer.md", "../agents/reviewer.md"
            ),
        }

        for label, contents in cases.items():
            with self.subTest(label=label):
                valid.write_text(contents, encoding="utf-8")
                report = self.validator.validate_repository(self.root)
                self.assertTrue(
                    any(
                        error.startswith(
                            "invalid agent adapter: codex/agents/reviewer.toml"
                        )
                        for error in report.errors
                    )
                )

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

    def test_rejects_external_skill_adapter_symlink(self) -> None:
        self.canonical_command("ship")
        self.canonical_agent("reviewer")
        self.agent_adapter("reviewer")
        external_skill = Path(self.external_dir.name) / "SKILL.md"
        external_skill.write_text("---\nname: ship\n---\n# Ship\n", encoding="utf-8")
        self.symlink("skills/ship/SKILL.md", external_skill)

        report = self.validator.validate_repository(self.root)

        self.assertIn("escaped command adapter: skills/ship/SKILL.md", report.errors)

    def test_rejects_external_agent_adapter_symlink(self) -> None:
        self.canonical_command("ship")
        self.canonical_agent("reviewer")
        self.skill("ship")
        external_adapter = Path(self.external_dir.name) / "reviewer.toml"
        external_adapter.write_text('name = "reviewer"\n', encoding="utf-8")
        self.symlink("codex/agents/reviewer.toml", external_adapter)

        report = self.validator.validate_repository(self.root)

        self.assertIn("escaped agent adapter: codex/agents/reviewer.toml", report.errors)

    def test_valid_fixture_has_adapter_parity(self) -> None:
        self.canonical_command("ship")
        self.canonical_agent("reviewer")
        self.skill("ship")
        self.agent_adapter("reviewer")

        report = self.validator.validate_repository(self.root)

        self.assertEqual(report.errors, [])
        self.assertEqual(report.command_count, 1)
        self.assertEqual(report.agent_count, 1)

    def test_current_repository_parity_passes_with_complete_adapters(self) -> None:
        completed = subprocess.run(
            ["python3", str(VALIDATOR_PATH), str(REPOSITORY_ROOT)],
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 0)
        self.assertIn("Diagnostic: canonical commands=6", completed.stdout)
        self.assertIn("Diagnostic: canonical agents=15", completed.stdout)
        self.assertNotIn("missing command adapter:", completed.stdout)
        self.assertNotIn("missing agent adapter:", completed.stdout)


if __name__ == "__main__":
    unittest.main()
