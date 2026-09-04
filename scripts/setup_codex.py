#!/usr/bin/env python3
"""Safely link a live pt-doots checkout into a Codex home directory."""

from __future__ import annotations

import argparse
import errno
import os
import shlex
import stat
import subprocess
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterator, Sequence


RunCommand = Callable[..., subprocess.CompletedProcess[str]]
MutationHook = Callable[[str, Path], None]


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


@dataclass
class AgentDirectoryHandle:
    """Open descriptors for a verified `~/.codex/agents` directory chain."""

    path: Path
    home_fd: int
    codex_fd: int
    agents_fd: int
    codex_identity: tuple[int, int]
    agents_identity: tuple[int, int]

    def verify(self) -> None:
        """Fail if either named directory was replaced after it was opened."""
        try:
            codex_entry = os.stat(".codex", dir_fd=self.home_fd, follow_symlinks=False)
            agents_entry = os.stat("agents", dir_fd=self.codex_fd, follow_symlinks=False)
        except OSError as error:
            raise SetupError(f"Codex agent directory changed during setup: {error}") from error
        if (
            not stat.S_ISDIR(codex_entry.st_mode)
            or not stat.S_ISDIR(agents_entry.st_mode)
            or (codex_entry.st_dev, codex_entry.st_ino) != self.codex_identity
            or (agents_entry.st_dev, agents_entry.st_ino) != self.agents_identity
        ):
            raise SetupError("Codex agent directory changed during setup")

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


def marketplace_command(checkout: Path, codex_binary: str = "codex") -> tuple[str, ...]:
    """Build the supported local-marketplace registration command."""
    return (
        codex_binary,
        "plugin",
        "marketplace",
        "add",
        str(checkout),
    )


def manual_marketplace_command(checkout: Path, codex_binary: str = "codex") -> str:
    return shlex.join(marketplace_command(checkout, codex_binary))


def codex_agent_directory(home: Path) -> Path:
    """Return the expected agent path for dry-run inspection only."""
    codex_directory = home / ".codex"
    directory = codex_directory / "agents"
    if codex_directory.is_symlink() or directory.is_symlink():
        raise SetupError("refusing to use symlinked Codex agent directory")
    if codex_directory.exists() and not codex_directory.is_dir():
        raise SetupError(f"Codex home path is not a directory: {codex_directory}")
    if directory.exists() and not directory.is_dir():
        raise SetupError(f"Codex agent path is not a directory: {directory}")
    return directory


def _require_safe_directory_fd_operations() -> None:
    """Refuse to mutate when the platform cannot make descriptor-relative changes."""
    required_functions = (os.mkdir, os.open, os.readlink, os.stat, os.symlink, os.unlink)
    if (
        not hasattr(os, "O_DIRECTORY")
        or not hasattr(os, "O_NOFOLLOW")
        or any(function not in os.supports_dir_fd for function in required_functions)
    ):
        raise SetupError("safe directory-descriptor operations are unavailable on this platform")


def _open_child_directory(parent_fd: int, name: str, *, create: bool) -> int:
    if create:
        try:
            os.mkdir(name, dir_fd=parent_fd)
        except FileExistsError:
            pass
        except OSError as error:
            raise SetupError(f"could not create Codex directory `{name}`: {error}") from error
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    try:
        return os.open(name, flags, dir_fd=parent_fd)
    except OSError as error:
        if not create and error.errno == errno.ENOENT:
            raise FileNotFoundError(error.errno, error.strerror, name) from error
        raise SetupError(f"refusing to open unsafe Codex directory `{name}`: {error}") from error


@contextmanager
def open_agent_directory(home: Path, *, create: bool) -> Iterator[AgentDirectoryHandle | None]:
    """Open `home/.codex/agents` without following any directory symlink."""
    _require_safe_directory_fd_operations()
    if create:
        try:
            home.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            raise SetupError(f"could not create Codex home directory: {error}") from error
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    try:
        home_fd = os.open(home, flags)
    except FileNotFoundError:
        if not create:
            yield None
            return
        raise SetupError(f"Codex home directory disappeared during setup: {home}")
    except OSError as error:
        raise SetupError(f"refusing to open unsafe Codex home directory: {error}") from error
    codex_fd: int | None = None
    agents_fd: int | None = None
    try:
        try:
            codex_fd = _open_child_directory(home_fd, ".codex", create=create)
        except FileNotFoundError:
            if not create:
                yield None
                return
            raise
        try:
            agents_fd = _open_child_directory(codex_fd, "agents", create=create)
        except FileNotFoundError:
            if not create:
                yield None
                return
            raise
        codex_stat = os.fstat(codex_fd)
        agents_stat = os.fstat(agents_fd)
        if not stat.S_ISDIR(codex_stat.st_mode) or not stat.S_ISDIR(agents_stat.st_mode):
            raise SetupError("refusing to use non-directory Codex agent path")
        yield AgentDirectoryHandle(
            path=home / ".codex" / "agents",
            home_fd=home_fd,
            codex_fd=codex_fd,
            agents_fd=agents_fd,
            codex_identity=(codex_stat.st_dev, codex_stat.st_ino),
            agents_identity=(agents_stat.st_dev, agents_stat.st_ino),
        )
    finally:
        for descriptor in (agents_fd, codex_fd, home_fd):
            if descriptor is not None:
                os.close(descriptor)


def _lstat_at(handle: AgentDirectoryHandle, name: str) -> os.stat_result | None:
    try:
        return os.stat(name, dir_fd=handle.agents_fd, follow_symlinks=False)
    except FileNotFoundError:
        return None
    except OSError as error:
        raise SetupError(f"could not inspect agent destination `{name}`: {error}") from error


def _is_expected_link(destination: Path, source: Path) -> bool:
    if not destination.is_symlink():
        return False
    try:
        return destination.resolve() == source.resolve()
    except OSError:
        return False


def _is_expected_link_at(handle: AgentDirectoryHandle, name: str, source: Path) -> bool:
    entry = _lstat_at(handle, name)
    if entry is None or not stat.S_ISLNK(entry.st_mode):
        return False
    try:
        target = Path(os.readlink(name, dir_fd=handle.agents_fd))
    except OSError:
        return False
    target_path = target if target.is_absolute() else handle.path / target
    try:
        return target_path.resolve() == source.resolve()
    except OSError:
        return False


def _is_owned_adapter_link(destination: Path, sources: tuple[Path, ...]) -> bool:
    """Match only the exact destination filename and adapter target we install."""
    expected_sources = {source.name: source for source in sources}
    expected_source = expected_sources.get(destination.name)
    return expected_source is not None and _is_expected_link(destination, expected_source)


def _is_owned_adapter_link_at(
    handle: AgentDirectoryHandle, name: str, expected_sources: dict[str, Path]
) -> bool:
    expected_source = expected_sources.get(name)
    return expected_source is not None and _is_expected_link_at(handle, name, expected_source)


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


def _uninstall_links(
    checkout: Path,
    home: Path,
    *,
    dry_run: bool,
    mutation_hook: MutationHook | None,
) -> SetupResult:
    sources = agent_sources(checkout)
    if dry_run:
        directory = codex_agent_directory(home)
        if not directory.is_dir():
            return SetupResult(dry_run=True)
        removed = tuple(
            destination
            for destination in sorted(directory.iterdir())
            if destination.is_symlink() and _is_owned_adapter_link(destination, sources)
        )
        preserved = tuple(destination for destination in sorted(directory.iterdir()) if destination not in removed)
        return SetupResult(removed=removed, preserved=preserved, dry_run=True)

    with open_agent_directory(home, create=False) as handle:
        if handle is None:
            return SetupResult()
        expected_sources = {source.name: source for source in sources}
        destination_names = sorted(os.listdir(handle.agents_fd))
        removed: list[Path] = []
        preserved: list[Path] = []
        for name in destination_names:
            destination = handle.path / name
            handle.verify()
            if not _is_owned_adapter_link_at(handle, name, expected_sources):
                preserved.append(destination)
                continue
            if mutation_hook:
                mutation_hook("before_unlink", destination)
            handle.verify()
            if not _is_owned_adapter_link_at(handle, name, expected_sources):
                raise SetupError(f"refusing to remove changed agent destination: {destination}")
            try:
                os.unlink(name, dir_fd=handle.agents_fd)
            except OSError as error:
                raise SetupError(f"could not remove agent destination `{destination}`: {error}") from error
            removed.append(destination)
        return SetupResult(removed=tuple(removed), preserved=tuple(preserved))


def _link_agents(
    home: Path,
    sources: tuple[Path, ...],
    *,
    mutation_hook: MutationHook | None,
) -> tuple[tuple[Path, ...], tuple[Path, ...]]:
    """Create missing links through an opened directory descriptor only."""
    with open_agent_directory(home, create=True) as handle:
        if handle is None:
            raise SetupError("Codex agent directory disappeared during setup")
        linked: list[Path] = []
        unchanged: list[Path] = []
        for source in sources:
            destination = handle.path / source.name
            handle.verify()
            entry = _lstat_at(handle, source.name)
            if _is_expected_link_at(handle, source.name, source):
                unchanged.append(destination)
            elif entry is not None:
                raise SetupError(f"refusing to overwrite existing agent destination: {destination}")
            else:
                linked.append(destination)
        for destination in linked:
            source = next(source for source in sources if source.name == destination.name)
            handle.verify()
            if mutation_hook:
                mutation_hook("before_link", destination)
            handle.verify()
            if _lstat_at(handle, destination.name) is not None:
                raise SetupError(f"refusing to overwrite existing agent destination: {destination}")
            try:
                os.symlink(str(source), destination.name, dir_fd=handle.agents_fd)
            except OSError as error:
                raise SetupError(f"could not create agent link `{destination}`: {error}") from error
        return tuple(linked), tuple(unchanged)


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
    mutation_hook: MutationHook | None = None,
) -> SetupResult:
    """Validate then link adapters, optionally registering the local marketplace."""
    checkout = (checkout or checkout_root()).resolve()
    home = home or Path.home()
    validate_checkout(checkout, validator_runner)
    if uninstall:
        return _uninstall_links(
            checkout, home, dry_run=dry_run, mutation_hook=mutation_hook
        )

    sources = agent_sources(checkout)
    directory = codex_agent_directory(home)
    if dry_run:
        linked = []
        unchanged = []
        for source in sources:
            destination = directory / source.name
            if _is_expected_link(destination, source):
                unchanged.append(destination)
            elif destination.exists() or destination.is_symlink():
                raise SetupError(f"refusing to overwrite existing agent destination: {destination}")
            else:
                linked.append(destination)
    else:
        linked, unchanged = _link_agents(home, sources, mutation_hook=mutation_hook)

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
