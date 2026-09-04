# Codex onboarding (Phase 1 experiment)

This is the Codex path for the live `pt-doots` checkout. Claude Code remains
the canonical harness and its existing onboarding is unchanged. Codex supplies
thin skills and agent metadata; it does not own a second copy of the workflow.

## Supported host and prerequisites

The setup script is verified on macOS and updates the Codex TOML configuration
with direct named-agent registrations. It fails closed on malformed TOML and
conflicting agent names. Native Windows is not supported: do not substitute
PowerShell configuration edits or treat a file copy as an installation. Use a
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

From the repository root, validate before registering named agents:

```bash
python3 scripts/validate_codex_compat.py .
python3 scripts/setup_codex.py --dry-run
```

On macOS or another supported POSIX host, register the live named agents,
register the repo-local marketplace, and install the plugin:

```bash
python3 scripts/setup_codex.py
```

That creates direct `[agents."<name>"]` `config_file` registrations in
`~/.codex/config.toml` targeting the checked-in `codex/agents/*.toml` files,
registers the checkout root containing `.agents/plugins/marketplace.json`, and
installs `pt-doots@pt-doots-local`. The installer refuses name collisions and
removes only its marker-owned registrations. To perform only named-agent
registration, use `--agents-only`; it prints the two skipped plugin commands.

```bash
codex plugin marketplace list
codex plugin list --marketplace pt-doots-local --available --json
```

The `.` path in `.agents/plugins/marketplace.json` is relative to the
marketplace root passed to `codex plugin marketplace add`, so it resolves to
this checkout, where `.codex-plugin/plugin.json` lives.

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

Fresh-session runtime canaries prove that requesting a registered named agent
selects its developer instructions, model, and reasoning effort. If the named
agent is unavailable or not selected, STOP and report the blocked dispatch;
never fall back to a generic or prompt-only agent.

Per-agent `sandbox_mode` is currently advisory metadata, not an enforced
security boundary. A live `read-only` canary could write with the parent
session's broader permissions. Keep the declarations for forward compatibility,
but scope the parent session safely and enforce each canonical agent's read/write
contract through instructions and review.

The runtime mapping also retains the canonical REST helper preference whenever
pt-doots prohibits the Atlassian MCP. Do not replace it with an MCP call.

## Live checkout reload behavior

The `~/.codex/config.toml` entries use absolute `config_file` paths to this
live checkout, so adapter edits load directly from it. After changing an
adapter, reload Codex and start a new Codex thread.
Installed plugin skills and their bundled canonical files are versioned cache
copies, not symlinks. After changing a skill, command, agent, or shared
reference, update `.codex-plugin/plugin.json` with Codex's standard cachebuster
helper, rerun `python3 scripts/setup_codex.py`, and start a new thread. Existing
threads may retain their earlier prompt, skill, or agent state; do not use them
as evidence that a change loaded.

Plugin marketplace registration and named-agent registration are separate. If
plugin registration was skipped, rerun the two `codex plugin` commands above
from the checkout root. If an agent name is already configured for another
file, the installer refuses to overwrite it; inspect that configuration rather
than editing it blindly.

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
adapter it reports. Setup does not mutate configuration after a failed
preflight.

**Codex cannot see the plugin.** Confirm the marketplace root with `codex
plugin marketplace list`, then run `codex plugin marketplace add "$(pwd)"` and
`codex plugin add pt-doots@pt-doots-local` again. Start a new Codex thread.

**A named agent is unavailable.** Treat this as BLOCKED. Do not use a generic
agent as a substitute. Registered profile, model, and reasoning selection are
runtime-verified; per-agent sandbox isolation is not currently enforced.

**Permission or hook failures.** Follow the repository's existing permissions,
approval gates, and hooks. The Codex adapter does not grant write access or
replace product hooks. Re-run the PlexTrac agent-skills setup if `gh`, REST
credentials, or the Jira attachment helper are absent.

**The installer refuses the host or an agent registration.** Native Windows is
unsupported. On a supported POSIX host, keep the existing configuration in
place, inspect it, and use `--dry-run --agents-only` before retrying.
