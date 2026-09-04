#!/usr/bin/env python3
"""Validate filesystem parity between canonical pt-doots definitions and Codex adapters."""

from __future__ import annotations

import ast
import json
import sys
import tomllib
from pathlib import Path


MODEL_MAPPING = {
    "haiku": "gpt-5.6-luna",
    "sonnet": "gpt-5.6-terra",
    "opus": "gpt-5.6-sol",
}


class Inventories:
    """Canonical command and agent files discovered from a repository root."""

    def __init__(self, commands: dict[str, Path], agents: dict[str, Path]) -> None:
        self.commands = commands
        self.agents = agents


class ValidationReport:
    """Validation output suitable for programmatic callers and the CLI."""

    def __init__(self, command_count: int, agent_count: int, errors: list[str]) -> None:
        self.command_count = command_count
        self.agent_count = agent_count
        self.errors = errors


def parse_markdown_frontmatter(path: Path) -> dict[str, str]:
    """Parse the small YAML frontmatter subset used by command and skill files."""
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0] != "---":
        raise ValueError(f"frontmatter must start with ---: {path}")

    try:
        end = lines.index("---", 1)
    except ValueError as error:
        raise ValueError(f"frontmatter must end with ---: {path}") from error

    data: dict[str, str] = {}
    index = 1
    while index < end:
        line = lines[index]
        if not line.strip() or line.lstrip().startswith("#"):
            index += 1
            continue
        if line.startswith((" ", "\t")) or ":" not in line:
            raise ValueError(f"invalid frontmatter entry: {path}")
        key, value = line.split(":", 1)
        key, value = key.strip(), value.strip()
        if not key or key in data:
            raise ValueError(f"invalid frontmatter entry: {path}")
        if value in {">", "|"}:
            index += 1
            values: list[str] = []
            while index < end and lines[index].startswith((" ", "\t")):
                values.append(lines[index].strip())
                index += 1
            if not values:
                raise ValueError(f"invalid frontmatter block: {path}")
            data[key] = " ".join(values) if value == ">" else "\n".join(values)
            continue
        data[key] = _parse_scalar(value, path)
        index += 1
    return data


def _parse_scalar(value: str, path: Path) -> str:
    if not value:
        return ""
    if value.startswith(("'", '"')):
        try:
            parsed = ast.literal_eval(value)
        except (SyntaxError, ValueError) as error:
            raise ValueError(f"invalid frontmatter value: {path}") from error
        if not isinstance(parsed, str):
            raise ValueError(f"invalid frontmatter value: {path}")
        return parsed
    return value


def parse_toml(path: Path) -> dict[str, object]:
    """Load an adapter TOML file using Python's standard-library TOML parser."""
    with path.open("rb") as source:
        data = tomllib.load(source)
    if not isinstance(data, dict):
        raise ValueError(f"TOML document must be a table: {path}")
    return data


def validate_relative_reference(root: Path, reference: str) -> str | None:
    """Return an actionable error when a repository-relative reference is unsafe."""
    candidate = Path(reference)
    if candidate.is_absolute():
        return f"reference must be relative: {reference}"

    resolved = resolve_within_root(root, root / candidate)
    if resolved is None:
        return f"relative reference escapes repository: {reference}"
    if not resolved.is_file():
        return f"relative reference does not exist: {reference}"
    return None


def resolve_within_root(root: Path, path: Path) -> Path | None:
    """Resolve a path only when its final target remains inside ``root``."""
    root = root.resolve()
    try:
        resolved = path.resolve()
        resolved.relative_to(root)
    except (OSError, ValueError):
        return None
    return resolved


def discover_inventories(root: Path) -> Inventories:
    """Discover only top-level canonical Markdown definitions."""
    return Inventories(
        commands=_top_level_markdown(root / "commands"),
        agents=_top_level_markdown(root / "agents"),
    )


def _top_level_markdown(directory: Path) -> dict[str, Path]:
    if not directory.is_dir():
        return {}
    return {path.stem: path for path in sorted(directory.glob("*.md")) if path.is_file()}


def validate_repository(root: Path) -> ValidationReport:
    """Return all parity and syntax errors without modifying the repository."""
    root = root.resolve()
    inventories = discover_inventories(root)
    errors: list[str] = []

    for relative in (Path(".codex-plugin/plugin.json"), Path(".agents/plugins/marketplace.json")):
        path = root / relative
        if not path.is_file() or resolve_within_root(root, path) is None:
            errors.append(f"missing or escaped Codex manifest: {relative}")
            continue
        try:
            manifest = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            errors.append(f"malformed Codex manifest: {relative}")
            continue
        if not isinstance(manifest, dict):
            errors.append(f"malformed Codex manifest: {relative}")

    for kind, definitions in (("command", inventories.commands), ("agent", inventories.agents)):
        for name, path in definitions.items():
            relative = path.relative_to(root)
            if resolve_within_root(root, path) is None:
                errors.append(f"escaped canonical {kind}: {relative}")
                continue
            try:
                parse_markdown_frontmatter(path)
            except (OSError, ValueError) as error:
                errors.append(f"malformed canonical {kind}: {relative} ({error})")

    skill_paths = _skill_paths(root)
    for name in inventories.commands:
        expected = root / "skills" / name / "SKILL.md"
        if not expected.is_file():
            errors.append(f"missing command adapter: skills/{name}/SKILL.md")
    for path in skill_paths:
        relative = path.relative_to(root)
        if resolve_within_root(root, path) is None:
            errors.append(f"escaped command adapter: {relative}")
            continue
        if path.parent.name not in inventories.commands:
            errors.append(f"unexpected command adapter: {relative}")
        try:
            parse_markdown_frontmatter(path)
        except (OSError, ValueError):
            errors.append(f"malformed command adapter: {relative}")

    agent_paths = _agent_adapter_paths(root)
    for name in inventories.agents:
        expected = root / "codex" / "agents" / f"{name}.toml"
        if not expected.is_file():
            errors.append(f"missing agent adapter: codex/agents/{name}.toml")
    for path in agent_paths:
        relative = path.relative_to(root)
        if resolve_within_root(root, path) is None:
            errors.append(f"escaped agent adapter: {relative}")
            continue
        if path.stem not in inventories.agents:
            errors.append(f"unexpected agent adapter: {relative}")
        try:
            adapter = parse_toml(path)
        except (OSError, tomllib.TOMLDecodeError, ValueError):
            errors.append(f"malformed agent adapter: {relative}")
            continue

        canonical_path = inventories.agents.get(path.stem)
        if canonical_path is None:
            continue
        try:
            canonical = parse_markdown_frontmatter(canonical_path)
        except (OSError, ValueError):
            continue
        for detail in validate_agent_adapter(path.stem, canonical, adapter):
            errors.append(f"invalid agent adapter: {relative} ({detail})")

    return ValidationReport(
        command_count=len(inventories.commands),
        agent_count=len(inventories.agents),
        errors=sorted(errors),
    )


def _skill_paths(root: Path) -> list[Path]:
    skills = root / "skills"
    return sorted(path for path in skills.glob("*/SKILL.md") if path.is_file()) if skills.is_dir() else []


def _agent_adapter_paths(root: Path) -> list[Path]:
    agents = root / "codex" / "agents"
    return sorted(path for path in agents.glob("*.toml") if path.is_file()) if agents.is_dir() else []


def validate_agent_adapter(
    name: str,
    canonical: dict[str, str],
    adapter: dict[str, object],
) -> list[str]:
    """Return semantic compatibility errors for one canonical-agent adapter pair."""
    errors: list[str] = []
    expected_model = MODEL_MAPPING.get(canonical.get("model"))
    expected_sandbox = (
        "workspace-write" if "Write" in canonical.get("tools", "").split() else "read-only"
    )
    expected_values = {
        "name": canonical.get("name"),
        "description": canonical.get("description"),
        "model": expected_model,
        "model_reasoning_effort": canonical.get("effort"),
        "sandbox_mode": expected_sandbox,
    }
    for field, expected in expected_values.items():
        actual = adapter.get(field)
        if not isinstance(actual, str) or not actual.strip():
            errors.append(f"missing required field `{field}`")
        elif actual != expected:
            errors.append(f"field `{field}` must be `{expected}`")

    instructions = adapter.get("developer_instructions")
    if not isinstance(instructions, str) or not instructions.strip():
        errors.append("missing required field `developer_instructions`")
        return errors

    prompt_reference = f"pt-doots/agents/{name}.md"
    required_markers = (
        "walking upward",
        "product-core-backend",
        "product-core-frontend",
        "product-services-export",
        "product-services-mcp",
        prompt_reference,
        "complete canonical agent file",
        "canonical file wins",
        f"maxTurns {canonical.get('maxTurns', '')}",
        "interaction/tool-call budget",
        "one task turn only",
        "PARTIAL",
        "BLOCKED",
        "only the orchestrator may follow up",
    )
    for marker in required_markers:
        if not marker or marker not in instructions:
            errors.append(f"developer_instructions must include `{marker}`")
    if "../" in instructions or prompt_reference not in instructions:
        errors.append("developer_instructions must use the safe canonical prompt reference")
    return errors


def main(argv: list[str] | None = None) -> int:
    """Validate one repository and return a process exit status."""
    arguments = sys.argv[1:] if argv is None else argv
    if len(arguments) > 1:
        print("usage: validate_codex_compat.py [repository-root]", file=sys.stderr)
        return 2

    root = Path(arguments[0]) if arguments else Path(__file__).resolve().parents[1]
    report = validate_repository(root)
    print(f"Diagnostic: canonical commands={report.command_count} (baseline=6)")
    print(f"Diagnostic: canonical agents={report.agent_count} (baseline=15)")
    for error in report.errors:
        print(error)
    return 1 if report.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
