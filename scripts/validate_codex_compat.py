#!/usr/bin/env python3
"""Validate filesystem parity between canonical pt-doots definitions and Codex adapters."""

from __future__ import annotations

import ast
import sys
import tomllib
from pathlib import Path
from typing import Any


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


def parse_toml(path: Path) -> dict[str, Any]:
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

    root = root.resolve()
    resolved = (root / candidate).resolve()
    try:
        resolved.relative_to(root)
    except ValueError:
        return f"relative reference escapes repository: {reference}"
    if not resolved.is_file():
        return f"relative reference does not exist: {reference}"
    return None


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

    for kind, definitions in (("command", inventories.commands), ("agent", inventories.agents)):
        for name, path in definitions.items():
            try:
                parse_markdown_frontmatter(path)
            except (OSError, ValueError) as error:
                errors.append(f"malformed canonical {kind}: {path.relative_to(root)} ({error})")

    skill_paths = _skill_paths(root)
    for name in inventories.commands:
        expected = root / "skills" / name / "SKILL.md"
        if not expected.is_file():
            errors.append(f"missing command adapter: skills/{name}/SKILL.md")
    for path in skill_paths:
        relative = path.relative_to(root)
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
        if path.stem not in inventories.agents:
            errors.append(f"unexpected agent adapter: {relative}")
        try:
            parse_toml(path)
        except (OSError, tomllib.TOMLDecodeError, ValueError):
            errors.append(f"malformed agent adapter: {relative}")

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


def main(argv: list[str] | None = None) -> int:
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
