# Codex onboarding (Phase 1 experiment)

This is the Codex path for the live `pt-doots` checkout. Claude Code remains
the canonical harness and its existing onboarding is unchanged. Codex supplies
thin skills and agent metadata; it does not own a second copy of the workflow.

## Supported host and prerequisites

The setup script is verified on macOS and requires POSIX directory-descriptor
operations for safe symlink handling. It fails closed when those operations are
unavailable. Native Windows is not supported: do not substitute PowerShell
symlink commands or treat a successful file copy as an installation. Use a
supported POSIX host instead.

You will need:

- A live checkout of this repository and `python3`.
- The Codex CLI, signed in.
- The PlexTrac agent-skills setup already required by the Claude workflow:
  `gh`, Jira/Confluence REST credentials, and `~/bin/jira-attachment`.
- The normal repository instruction files, permissions, and hooks for the
  product workspace. This plugin does not loosen approval or permission rules.

No Codex hooks are bundled in Phase 1. Keep Claude hooks and the product
repository's existing hook policy in place.

## Install from the checkout

From the repository root, validate before creating any links:

```bash
python3 scripts/validate_codex_compat.py .
python3 scripts/setup_codex.py --dry-run --links-only
```

On macOS or another supported POSIX host, create only the live agent links:

```bash
python3 scripts/setup_codex.py --links-only
```

That links the checked-in `codex/agents/*.toml` files into
`~/.codex/agents`. The installer refuses collisions and removes only the exact
links it owns. For the repo-local plugin marketplace, pass the checkout root
(the directory that contains `.agents/plugins/marketplace.json`):

```bash
codex plugin marketplace add "$(pwd)"
codex plugin add pt-doots@pt-doots-local
```

Confirm what Codex sees:

```bash
codex plugin marketplace list
codex plugin list --marketplace pt-doots-local --available
```

The `../..` path in `.agents/plugins/marketplace.json` is intentional: it is
relative to `.agents/plugins/` and resolves back to this checkout, where
`.codex-plugin/plugin.json` lives.

## What is shared, and what is translated

`commands/*.md` and `agents/*.md` remain the canonical behavior. Skills read
the full canonical command first and then `reference/codex-compatibility.md`;
adapters load the canonical agent prompt. Claude Code remains canonical for
workflow ownership, packaged Claude behavior, and user-memory overlays.

Codex covers all six command skills and derives its 15 agent adapters from the
top-level inventory. Keep parity before committing:

```bash
python3 scripts/validate_codex_compat.py .
python3 -m unittest discover -s tests -v
```

The model translation is deliberately small:

- `haiku → gpt-5.6-luna`
- `sonnet → gpt-5.6-terra`
- `opus → gpt-5.6-sol`

Reasoning effort is preserved where Codex supports it. Claude `maxTurns` is an
advisory interaction/tool-call budget in the adapter, not a hard runtime limit.
Each task is one task turn; it must return PARTIAL or BLOCKED when its budget is
exhausted, and only the orchestrator may follow up.

Named-agent selection is not a proven Phase 1 capability. Ask for the
registered named agent; if it is unavailable or not selected, STOP and report
the blocked dispatch. Never fall back to a generic or prompt-only agent.
Successful named agent selection and application of its model, sandbox, and
developer instructions remain a Task 7 fresh-session integration check.

The runtime mapping also retains the canonical REST helper preference whenever
pt-doots prohibits the Atlassian MCP. Do not replace it with an MCP call.

## Live checkout reload behavior

The `~/.codex/agents` entries are symlinks, so adapter edits target this live
checkout. After changing an adapter, skill, canonical command, or canonical
agent, reload Codex and start a new Codex thread. Existing threads may retain
their earlier prompt, skill, or agent state; do not use them as evidence that a
change loaded.

Plugin marketplace registration and agent links are separate. If registration
was skipped, rerun the two `codex plugin` commands above from the checkout
root. If a link already exists but is not the exact expected adapter target,
the installer refuses to overwrite it; inspect it rather than deleting it by
hand.

## Maintenance boundaries

- Change workflow behavior in canonical `commands/*.md` and `agents/*.md`, not
  by copying it into a Codex wrapper.
- Keep Codex-specific metadata in `skills/` and `codex/agents/`.
- Keep preference overlays in the Claude user-memory locations documented in
  `OVERLAYS.md`; they are not a Codex configuration mechanism.
- Preserve shared `${HOME}/.claude/pt-doots` telemetry and ticket artifacts.
- Run parity validation after adding, renaming, or removing a command or agent.

A platform-neutral core is deliberately deferred. Phase 1 must first provide
evidence about actual runtime compatibility boundaries; do not move canonical
prompt bodies into a new shared layer yet.

## Troubleshooting

**Parity preflight fails.** Run `python3 scripts/validate_codex_compat.py .`
from the checkout root and fix the missing, stale, malformed, or escaped
adapter it reports. Setup does not mutate links after a failed preflight.

**Codex cannot see the plugin.** Confirm the marketplace root with `codex
plugin marketplace list`, then run `codex plugin marketplace add "$(pwd)"` and
`codex plugin add pt-doots@pt-doots-local` again. Start a new Codex thread.

**A named agent is unavailable.** Treat this as BLOCKED. Do not use a generic
agent as a substitute; named-agent enforcement is checked in Task 7.

**Permission or hook failures.** Follow the repository's existing permissions,
approval gates, and hooks. The Codex adapter does not grant write access or
replace product hooks. Re-run the PlexTrac agent-skills setup if `gh`, REST
credentials, or the Jira attachment helper are absent.

**The installer refuses the host or a link.** Native Windows is unsupported.
On a supported POSIX host, keep the existing file or foreign/broken link in
place, inspect it, and use `--dry-run --links-only` before retrying.
