#!/usr/bin/env python3
"""Safely link a live pt-doots checkout into a Codex home directory."""

from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence


RunCommand = Callable[..., subprocess.CompletedProcess[str]]


class SetupError(RuntimeError):
    """Raised when setup cannot safely change a Codex home directory."""


@dataclass(frozen=True)
class SetupResult:
    linked: tuple[Path, ...] = ()
    unchanged: tuple[Path, ...] = ()
    removed: tuple[Path, ...] = ()
    preserved: tuple[Path, ...] = ()
    dry_run: bool = False
    manual_command: str = ""


def checkout_root() -> Path:
    """Return the checkout containing this script without user-specific paths."""
    return Path(__file__).resolve().parents[1]


def agent_sources(checkout: Path) -> tuple[Path, ...]:
    """Return the checked-in adapter files after compatibility validation."""
    directory = checkout / "codex" / "agents"
    if not directory.is_dir():
        raise SetupError(f"missing Codex agent adapter directory: {directory}")
    sources = tuple(sorted(path for path in directory.iterdir() if path.suffix == ".toml" and path.is_file()))
    if not sources:
        raise SetupError(f"no Codex agent adapters found: {directory}")
    return sources


def validate_checkout(checkout: Path, runner: RunCommand = subprocess.run) -> None:
    """Fail before mutation unless the checkout's parity contract is valid."""
    command = [
        sys.executable,
        str(checkout / "scripts" / "validate_codex_compat.py"),
        str(checkout),
    ]
    try:
        completed = runner(command, capture_output=True, text=True)
    except OSError as error:
        raise SetupError(f"compatibility preflight could not run: {error}") from error
    if completed.returncode:
        details = "\n".join(
            value.strip() for value in (completed.stdout, completed.stderr) if value and value.strip()
        )
        raise SetupError(f"compatibility preflight failed: {details or 'validator returned nonzero'}")


def marketplace_directory(checkout: Path) -> Path:
    return checkout / ".agents" / "plugins"


def marketplace_command(checkout: Path, codex_binary: str = "codex") -> tuple[str, ...]:
    """Build the supported local-marketplace registration command."""
    return (
        codex_binary,
        "plugin",
        "marketplace",
        "add",
        str(marketplace_directory(checkout)),
    )


def manual_marketplace_command(checkout: Path, codex_binary: str = "codex") -> str:
    return shlex.join(marketplace_command(checkout, codex_binary))


def codex_agent_directory(home: Path) -> Path:
    """Return a non-symlinked Codex agent directory without following redirects."""
    codex_directory = home / ".codex"
    directory = codex_directory / "agents"
    if codex_directory.is_symlink() or directory.is_symlink():
        raise SetupError("refusing to use symlinked Codex agent directory")
    if codex_directory.exists() and not codex_directory.is_dir():
        raise SetupError(f"Codex home path is not a directory: {codex_directory}")
    if directory.exists() and not directory.is_dir():
        raise SetupError(f"Codex agent path is not a directory: {directory}")
    return directory


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def link_points_to_checkout(link: Path, checkout: Path) -> bool:
    """Whether a symlink resolves or lexically points into this checkout."""
    if not link.is_symlink():
        return False
    root_resolved = checkout.resolve()
    try:
        if _is_within(link.resolve(), root_resolved):
            return True
        target = link.readlink()
    except OSError:
        return False
    lexical_target = target if target.is_absolute() else link.parent / target
    normalized_lexical_target = Path(os.path.abspath(os.fspath(lexical_target)))
    return _is_within(normalized_lexical_target, Path(os.path.abspath(os.fspath(checkout))))


def _is_expected_link(destination: Path, source: Path) -> bool:
    if not destination.is_symlink():
        return False
    try:
        return destination.resolve() == source.resolve()
    except OSError:
        return False


def _register_marketplace(
    checkout: Path, *, codex_binary: str, runner: RunCommand
) -> str:
    command = marketplace_command(checkout, codex_binary)
    try:
        completed = runner(list(command), capture_output=True, text=True)
    except OSError as error:
        return f"Codex marketplace registration was skipped ({error}). Run: {manual_marketplace_command(checkout, codex_binary)}"
    if completed.returncode:
        details = "\n".join(
            value.strip() for value in (completed.stdout, completed.stderr) if value and value.strip()
        )
        suffix = f" ({details})" if details else ""
        return f"Codex marketplace registration was skipped{suffix}. Run: {manual_marketplace_command(checkout, codex_binary)}"
    return ""


def _uninstall_links(checkout: Path, home: Path, *, dry_run: bool) -> SetupResult:
    directory = codex_agent_directory(home)
    if not directory.is_dir():
        return SetupResult(dry_run=dry_run)
    removed: list[Path] = []
    preserved: list[Path] = []
    for destination in sorted(directory.iterdir()):
        if destination.is_symlink() and link_points_to_checkout(destination, checkout):
            removed.append(destination)
            if not dry_run:
                destination.unlink()
        else:
            preserved.append(destination)
    return SetupResult(
        removed=tuple(removed), preserved=tuple(preserved), dry_run=dry_run
    )


def setup_codex(
    *,
    checkout: Path | None = None,
    home: Path | None = None,
    dry_run: bool = False,
    links_only: bool = False,
    uninstall: bool = False,
    codex_binary: str = "codex",
    validator_runner: RunCommand = subprocess.run,
    cli_runner: RunCommand = subprocess.run,
) -> SetupResult:
    """Validate then link adapters, optionally registering the local marketplace."""
    checkout = (checkout or checkout_root()).resolve()
    home = home or Path.home()
    validate_checkout(checkout, validator_runner)
    if uninstall:
        return _uninstall_links(checkout, home, dry_run=dry_run)

    sources = agent_sources(checkout)
    directory = codex_agent_directory(home)
    linked: list[Path] = []
    unchanged: list[Path] = []
    for source in sources:
        destination = directory / source.name
        if _is_expected_link(destination, source):
            unchanged.append(destination)
            continue
        if destination.exists() or destination.is_symlink():
            raise SetupError(f"refusing to overwrite existing agent destination: {destination}")
        linked.append(destination)

    if not dry_run:
        directory.mkdir(parents=True, exist_ok=True)
        for destination in linked:
            source = checkout / "codex" / "agents" / destination.name
            destination.symlink_to(source)

    if dry_run or links_only:
        reason = "dry run" if dry_run else "--links-only"
        manual_command = (
            f"Codex marketplace registration skipped by {reason}. Run: "
            f"{manual_marketplace_command(checkout, codex_binary)}"
        )
    else:
        manual_command = _register_marketplace(
            checkout, codex_binary=codex_binary, runner=cli_runner
        )
    return SetupResult(
        linked=tuple(linked),
        unchanged=tuple(unchanged),
        dry_run=dry_run,
        manual_command=manual_command,
    )


def parse_args(arguments: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="report changes without mutating")
    parser.add_argument(
        "--links-only", action="store_true", help="skip marketplace registration and print its command"
    )
    parser.add_argument("--uninstall", action="store_true", help="remove only links owned by this checkout")
    parser.add_argument("--codex-binary", default="codex", help="Codex CLI executable for registration")
    return parser.parse_args(arguments)


def main(arguments: Sequence[str] | None = None) -> int:
    args = parse_args(arguments)
    try:
        result = setup_codex(
            dry_run=args.dry_run,
            links_only=args.links_only,
            uninstall=args.uninstall,
            codex_binary=args.codex_binary,
        )
    except SetupError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    for path in result.linked:
        print(f"{'would link' if result.dry_run else 'linked'}: {path}")
    for path in result.unchanged:
        print(f"unchanged: {path}")
    for path in result.removed:
        print(f"{'would remove' if result.dry_run else 'removed'}: {path}")
    for path in result.preserved:
        print(f"preserved: {path}")
    if result.manual_command:
        print(result.manual_command)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
