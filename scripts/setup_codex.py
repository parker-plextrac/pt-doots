#!/usr/bin/env python3
"""Register a live pt-doots checkout in a Codex home directory."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import shlex
import subprocess
import sys
import tomllib
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterator, Sequence
from contextlib import contextmanager, suppress

RunCommand = Callable[..., subprocess.CompletedProcess[str]]
MANAGED_BLOCK_START = "# BEGIN pt-doots managed named agents"
MANAGED_BLOCK_END = "# END pt-doots managed named agents"


class SetupError(RuntimeError):
    """Raised when setup cannot safely change a Codex home directory."""


@dataclass(frozen=True)
class SetupResult:
    """Describe named-agent registration changes made by setup."""

    registered: tuple[str, ...] = ()
    unchanged: tuple[str, ...] = ()
    removed: tuple[str, ...] = ()
    dry_run: bool = False
    manual_command: str = ""


def checkout_root() -> Path:
    """Return the checkout containing this script without user-specific paths."""
    return Path(__file__).resolve().parents[1]


def agent_sources(checkout: Path) -> tuple[Path, ...]:
    """Return checked-in adapter files after the compatibility preflight."""
    directory = checkout / "codex" / "agents"
    if not directory.is_dir():
        raise SetupError(f"missing Codex agent adapter directory: {directory}")
    sources = tuple(sorted(path.resolve() for path in directory.glob("*.toml") if path.is_file()))
    if not sources:
        raise SetupError(f"no Codex agent adapters found: {directory}")
    return sources


def validate_checkout(checkout: Path, runner: RunCommand = subprocess.run) -> None:
    """Fail before mutation unless the checkout's parity contract is valid."""
    command = [sys.executable, str(checkout / "scripts" / "validate_codex_compat.py"), str(checkout)]
    try:
        completed = runner(command, capture_output=True, text=True)
    except OSError as error:
        raise SetupError(f"compatibility preflight could not run: {error}") from error
    if completed.returncode:
        details = "\n".join(value.strip() for value in (completed.stdout, completed.stderr) if value and value.strip())
        raise SetupError(f"compatibility preflight failed: {details or 'validator returned nonzero'}")


def marketplace_command(checkout: Path, codex_binary: str = "codex") -> tuple[str, ...]:
    """Build the command that registers the live checkout marketplace."""
    return (codex_binary, "plugin", "marketplace", "add", str(checkout))


def plugin_install_command(codex_binary: str = "codex") -> tuple[str, ...]:
    """Build the command that installs pt-doots from its local marketplace."""
    return (codex_binary, "plugin", "add", "pt-doots@pt-doots-local")


def manual_marketplace_command(checkout: Path, codex_binary: str = "codex") -> str:
    """Return the shell command for manual marketplace registration."""
    return " && ".join(shlex.join(command) for command in (marketplace_command(checkout, codex_binary), plugin_install_command(codex_binary)))


def codex_config_path(home: Path) -> Path:
    """Return a safe direct config path without following an installer target link."""
    codex_directory = home / ".codex"
    path = codex_directory / "config.toml"
    if codex_directory.is_symlink():
        raise SetupError("refusing to use symlinked Codex configuration directory")
    if codex_directory.exists() and not codex_directory.is_dir():
        raise SetupError(f"Codex home path is not a directory: {codex_directory}")
    if path.is_symlink():
        raise SetupError("refusing to modify symlinked Codex configuration")
    if path.exists() and not path.is_file():
        raise SetupError(f"Codex configuration path is not a file: {path}")
    return path


@contextmanager
def _config_lock(home: Path) -> Iterator[int]:
    """Serialize pt-doots config updates and recheck symlink safety under lock."""
    codex_directory = home / ".codex"
    if codex_directory.is_symlink():
        raise SetupError("refusing to use symlinked Codex configuration directory")
    codex_directory.mkdir(parents=True, exist_ok=True)
    if codex_directory.is_symlink() or not codex_directory.is_dir():
        raise SetupError("refusing to use replaced Codex configuration directory")
    directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        directory_descriptor = os.open(codex_directory, directory_flags)
        lock_descriptor = os.open(
            ".pt-doots-setup.lock",
            os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0),
            0o600,
            dir_fd=directory_descriptor,
        )
    except OSError as error:
        raise SetupError(f"could not lock Codex configuration: {error}") from error
    try:
        with os.fdopen(lock_descriptor, "w") as lock_file:
            fcntl.flock(lock_file, fcntl.LOCK_EX)
            yield directory_descriptor
    except OSError as error:
        raise SetupError(f"could not lock Codex configuration: {error}") from error
    finally:
        os.close(directory_descriptor)


def _read_config_at(directory_descriptor: int, display_path: Path) -> tuple[str, dict[str, object]]:
    """Read config without re-resolving the checked Codex directory path."""
    try:
        descriptor = os.open(
            "config.toml",
            os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=directory_descriptor,
        )
    except FileNotFoundError:
        return "", {}
    except OSError as error:
        raise SetupError(f"could not read Codex configuration `{display_path}`: {error}") from error
    try:
        with os.fdopen(descriptor, encoding="utf-8") as source:
            contents = source.read()
        parsed = tomllib.loads(contents)
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise SetupError(f"could not parse Codex configuration `{display_path}`: {error}") from error
    return contents, parsed


def _read_config(path: Path) -> tuple[str, dict[str, object]]:
    if not path.exists():
        return "", {}
    try:
        contents = path.read_text(encoding="utf-8")
        parsed = tomllib.loads(contents)
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise SetupError(f"could not parse Codex configuration `{path}`: {error}") from error
    if not isinstance(parsed, dict):
        raise SetupError(f"Codex configuration is not a TOML table: {path}")
    return contents, parsed


def _expected_agent_configs(sources: tuple[Path, ...]) -> dict[str, str]:
    return {source.stem: str(source) for source in sources}


def _classify_entries(parsed: dict[str, object], expected: dict[str, str]) -> tuple[tuple[str, ...], tuple[str, ...]]:
    agents = parsed.get("agents", {})
    if not isinstance(agents, dict):
        raise SetupError("Codex configuration `[agents]` entry is not a table")
    registered: list[str] = []
    unchanged: list[str] = []
    for name, config_file in expected.items():
        entry = agents.get(name)
        if entry is None:
            registered.append(name)
        elif not isinstance(entry, dict) or entry.get("config_file") != config_file:
            raise SetupError(f"refusing to overwrite existing named-agent registration: {name}")
        else:
            unchanged.append(name)
    return tuple(registered), tuple(unchanged)


def _managed_block(entries: tuple[str, ...], expected: dict[str, str]) -> str:
    if not entries:
        return ""
    lines = [MANAGED_BLOCK_START]
    for name in entries:
        lines.extend((f'[agents.{json.dumps(name)}]', f'config_file = {json.dumps(expected[name])}', ""))
    lines.append(MANAGED_BLOCK_END)
    return "\n".join(lines) + "\n"


def _append_block(contents: str, block: str) -> str:
    return block if not contents else contents.rstrip() + "\n\n" + block


def _managed_blocks(contents: str, expected: dict[str, str]) -> tuple[tuple[int, int], ...]:
    """Find marker-delimited blocks that contain at least one owned entry."""
    blocks: list[tuple[int, int]] = []
    cursor = 0
    while True:
        start = contents.find(MANAGED_BLOCK_START, cursor)
        if start < 0:
            return tuple(blocks)
        end_marker = contents.find(MANAGED_BLOCK_END, start)
        if end_marker < 0:
            return tuple(blocks)
        end = end_marker + len(MANAGED_BLOCK_END)
        if end < len(contents) and contents[end] == "\n":
            end += 1
        blocks.append((start, end))
        cursor = end


def _remove_managed_blocks(contents: str, expected: dict[str, str]) -> tuple[str, tuple[str, ...]]:
    removed: list[str] = []
    for start, end in reversed(_managed_blocks(contents, expected)):
        block = contents[start:end]
        lines = block.splitlines(keepends=True)
        segments: list[list[str]] = []
        current: list[str] | None = None
        for line in lines[1:-1]:
            if line.startswith("[agents."):
                if current:
                    segments.append(current)
                current = [line]
            elif current is not None:
                current.append(line)
        if current:
            segments.append(current)
        adapter_directories = {str(Path(value).parent) for value in expected.values()}
        kept: list[str] = []
        for segment in segments:
            text = "".join(segment)
            try:
                parsed_segment = tomllib.loads(text)
                agents = parsed_segment.get("agents", {})
            except tomllib.TOMLDecodeError:
                kept.append(text)
                continue
            if set(parsed_segment) != {"agents"} or not isinstance(agents, dict) or len(agents) != 1:
                kept.append(text)
                continue
            name, value = next(iter(agents.items()))
            owned = (
                isinstance(value, dict)
                and set(value) == {"config_file"}
                and isinstance(value.get("config_file"), str)
                and str(Path(value["config_file"]).parent) in adapter_directories
                and Path(value["config_file"]).stem == name
            )
            if owned:
                removed.append(name)
            else:
                kept.append(text)
        replacement = ""
        if kept:
            replacement = MANAGED_BLOCK_START + "\n" + "".join(kept).rstrip() + "\n" + MANAGED_BLOCK_END + "\n"
        contents = contents[:start] + replacement + contents[end:]
    updated = contents.rstrip() + ("\n" if contents.strip() else "")
    return updated, tuple(sorted(set(removed)))


def _write_config_at(directory_descriptor: int, path: Path, contents: str) -> None:
    """Atomically write config relative to a checked, retained directory handle."""
    temporary_name = f".pt-doots-config-{uuid.uuid4().hex}.tmp"
    try:
        descriptor = os.open(
            temporary_name,
            os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0),
            0o600,
            dir_fd=directory_descriptor,
        )
        with os.fdopen(descriptor, "w", encoding="utf-8") as temporary:
            temporary.write(contents)
        os.replace(
            temporary_name,
            "config.toml",
            src_dir_fd=directory_descriptor,
            dst_dir_fd=directory_descriptor,
        )
    except OSError as error:
        raise SetupError(f"could not write Codex configuration `{path}`: {error}") from error
    finally:
        with suppress(FileNotFoundError):
            os.unlink(temporary_name, dir_fd=directory_descriptor)


def _register_marketplace(checkout: Path, *, codex_binary: str, runner: RunCommand) -> str:
    for command in (marketplace_command(checkout, codex_binary), plugin_install_command(codex_binary)):
        try:
            completed = runner(list(command), capture_output=True, text=True)
        except OSError as error:
            raise SetupError(f"Codex plugin setup failed ({error}). Run: {manual_marketplace_command(checkout, codex_binary)}") from error
        if completed.returncode:
            details = "\n".join(value.strip() for value in (completed.stdout, completed.stderr) if value and value.strip())
            suffix = f" ({details})" if details else ""
            raise SetupError(f"Codex plugin setup failed{suffix}. Run: {manual_marketplace_command(checkout, codex_binary)}")
    return ""


def setup_codex(*, checkout: Path | None = None, home: Path | None = None, dry_run: bool = False, links_only: bool = False, uninstall: bool = False, codex_binary: str = "codex", validator_runner: RunCommand = subprocess.run, cli_runner: RunCommand = subprocess.run) -> SetupResult:
    """Validate then register direct named-agent configs and the local plugin."""
    checkout = (checkout or checkout_root()).resolve()
    home = home or Path.home()
    validate_checkout(checkout, validator_runner)
    expected = _expected_agent_configs(agent_sources(checkout))
    config_path = codex_config_path(home)
    if dry_run:
        contents, parsed = _read_config(config_path)
        if uninstall:
            updated, removed = _remove_managed_blocks(contents, expected)
            return SetupResult(removed=removed, dry_run=True)
        registered, unchanged = _classify_entries(parsed, expected)
        reason = "dry run" if dry_run else "--links-only"
        manual_command = f"Codex marketplace registration skipped by {reason}. Run: {manual_marketplace_command(checkout, codex_binary)}"
        return SetupResult(registered=registered, unchanged=unchanged, dry_run=True, manual_command=manual_command)

    with _config_lock(home) as directory_descriptor:
        contents, parsed = _read_config_at(directory_descriptor, config_path)
        if uninstall:
            updated, removed = _remove_managed_blocks(contents, expected)
            if updated != contents:
                _write_config_at(directory_descriptor, config_path, updated)
            return SetupResult(removed=removed)
        registered, unchanged = _classify_entries(parsed, expected)
        if not links_only:
            _register_marketplace(checkout, codex_binary=codex_binary, runner=cli_runner)
        if registered:
            _write_config_at(directory_descriptor, config_path, _append_block(contents, _managed_block(registered, expected)))

    manual_command = ""
    if links_only:
        manual_command = f"Codex marketplace registration skipped by --links-only. Run: {manual_marketplace_command(checkout, codex_binary)}"
    return SetupResult(registered=registered, unchanged=unchanged, dry_run=dry_run, manual_command=manual_command)


def parse_args(arguments: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments for live-checkout setup."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="report changes without mutating")
    parser.add_argument(
        "--agents-only",
        "--links-only",
        dest="links_only",
        action="store_true",
        help="skip marketplace registration and print its command",
    )
    parser.add_argument("--uninstall", action="store_true", help="remove only installer-owned named-agent registrations")
    parser.add_argument("--codex-binary", default="codex", help="Codex CLI executable for registration")
    return parser.parse_args(arguments)


def main(arguments: Sequence[str] | None = None) -> int:
    """Run setup and return a process exit status."""
    args = parse_args(arguments)
    try:
        result = setup_codex(dry_run=args.dry_run, links_only=args.links_only, uninstall=args.uninstall, codex_binary=args.codex_binary)
    except SetupError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    for name in result.registered:
        print(f"{'would register' if result.dry_run else 'registered'}: {name}")
    for name in result.unchanged:
        print(f"unchanged: {name}")
    for name in result.removed:
        print(f"{'would remove' if result.dry_run else 'removed'}: {name}")
    if result.manual_command:
        print(result.manual_command)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
