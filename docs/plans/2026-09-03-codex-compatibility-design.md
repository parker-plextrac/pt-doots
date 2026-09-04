# Dual-Runtime Claude Code and Codex Compatibility Design

## Goal

Make the complete `pt-doots` harness available in both Claude Code and Codex while preserving the existing Claude workflow and keeping the current command, agent, reference, script, telemetry, and ticket-artifact content authoritative.

## Constraints

- Preserve the existing Claude Code behavior and packaging.
- Load Codex directly from the live local checkout; do not require publishing a marketplace release during development.
- Support all six commands and every top-level agent as one atomic compatibility surface.
- Keep shared prompts, references, scripts, overlays, telemetry formats, and progress files in their current locations.
- Do not duplicate the workflow into independently maintained Claude and Codex implementations.
- Preserve unrelated working-tree edits, including the current voice-stylist changes.
- Documentation and automated parity validation are required deliverables.

## Architecture

The existing `commands/*.md`, `agents/*.md`, `reference/`, and `scripts/` content remains the canonical harness. Claude Code continues using `.claude-plugin/` and the current files exactly as it does today.

Codex receives a thin platform adapter in the same repository:

- `.codex-plugin/plugin.json` identifies the checkout as a Codex plugin.
- Codex skills provide entry points corresponding to every command.
- Codex subagent definitions expose every agent using Codex-native metadata and tool names while referring to the canonical agent prompt content. A local onboarding script adds direct `[agents."<name>"]` `config_file` registrations to `~/.codex/config.toml`; the checked-in checkout remains authoritative. Fresh-session canaries prove named instructions, model, and reasoning selection. Per-agent sandbox declarations remain forward-compatible intent metadata because the current runtime does not enforce them independently from the parent session.
- Small compatibility mappings translate runtime-specific concepts such as slash-command arguments, tool identifiers, task dispatch, model selection, and lifecycle behavior.
- Named-agent adapters, shared telemetry, and ticket-scoped artifacts are consumed from the active workspace. Installed plugin Markdown may be cached by Codex and therefore requires a plugin refresh after source changes.

This follows the established Codex orchestration pattern used by projects such as Oh My Codex: workflow skills drive role-based agents, parallel reviewers operate on a shared scope, and durable state lives outside transient conversations. That pattern informs only the Codex adapter; it does not replace or refactor the `pt-doots` workflow.

## Phase 1 Source of Truth

This compatibility work is an experiment. For Phase 1, the existing Claude Code files remain authoritative. Codex adapters read and apply those files rather than moving their bodies into a new neutral hierarchy.

A future platform-neutral core remains a deliberate follow-up design: canonical command and agent bodies would move outside both runtime adapters, with Claude and Codex each receiving thin metadata wrappers and live symlinks. That refactor is explicitly deferred until the Phase 1 integration has produced evidence about the real compatibility boundaries.

## Source-of-Truth Rules

1. Existing command and agent content is authoritative.
2. Codex adapter files contain platform metadata and the minimum required compatibility instructions.
3. Shared business rules must not be copied into adapters.
4. Adding, renaming, or removing a command or agent requires a matching adapter change.
5. A parity validator fails when the two platform inventories diverge or an adapter is invalid.

## Complete Compatibility Surface

The initial change is all-or-nothing:

- Commands: `pt-doots`, `prs`, `bootstrap-team`, `team-audit`, `voice-profile`, and `publish-docs`.
- Agents: every top-level definition currently under `agents/` (15 at design time). Validation derives this inventory from the filesystem rather than relying on a handwritten count.
- Shared dependencies: PlexTrac agent skills, Jira and Confluence REST helpers, GitHub CLI, repository instruction files, hooks, scripts, overlays, telemetry, and progress formats.

No partial installation will be described as supported.

### Model and budget mapping

Claude model tiers map by intent:

- `haiku` → `gpt-5.6-luna`
- `sonnet` → `gpt-5.6-terra`
- `opus` → `gpt-5.6-sol`

Reasoning effort maps directly where supported.

Codex custom-agent configuration does not expose Claude Code's `maxTurns` setting. Phase 1 therefore preserves each declared limit as an explicit agent budget, runs each spawn as one bounded task turn, and requires a blocked or partial report instead of autonomous continuation after the budget is exhausted. The orchestrator alone decides whether to send a follow-up. This is an advisory compatibility boundary rather than a hard runtime counter and must be documented honestly.

## Local Development and Loading

Codex is configured from the checkout root that contains
`.agents/plugins/marketplace.json`; the checked-out working tree is the active
development source. The installer writes direct `config_file` registrations and
uses POSIX directory-descriptor operations to protect configuration updates; it
is verified on macOS, and native Windows is not a supported setup path. Installed
plugin Markdown may be cached, so refresh the local plugin after source changes,
then reload Codex and begin a new thread. Named-agent registrations continue to
point directly at the live checkout.

The installation documentation must distinguish local development loading from any future distribution mechanism.

## Validation

Automated validation will verify:

- Both plugin manifests are structurally valid.
- Every canonical command has exactly one Codex skill entry point.
- Every canonical agent has exactly one Codex subagent definition.
- Adapter references resolve to existing canonical files.
- No adapter copies substantial canonical workflow content.
- Required shared scripts and references exist.
- The Codex plugin can be discovered from the live checkout.
- Representative orchestration paths resolve all required agents and dependencies.

The change is complete only when all six commands, every canonical agent, manifests, and documentation pass validation together.

## Documentation

Update the main README to describe `pt-doots` as a dual-platform harness without weakening the existing Claude Code onboarding.

Documentation will include:

- Separate Claude Code and Codex onboarding sections.
- A platform compatibility and terminology mapping.
- Codex local-checkout installation and reload instructions.
- Supported-host, permissions, hooks, named-agent fail-closed behavior, and the non-enforced per-agent sandbox boundary.
- Prerequisites for plugins, commands, credentials, hooks, permissions, MCP or REST integrations, and repository guidance.
- A contributor guide identifying canonical files and adapter responsibilities.
- The parity-validation command required before committing.
- Troubleshooting for missing skills, missing subagents, stale local-plugin state, authentication, and platform-specific tool names.

Architecture and development documents containing Claude-only assumptions will be updated where those assumptions are no longer accurate.

## Non-Goals

- Rewriting the `pt-doots` workflow around another harness.
- Replacing Claude Code support.
- Publishing a new marketplace release as part of local development setup.
- Maintaining two independent copies of agent prompts or workflow rules.
- Changing current voice-stylist behavior or unrelated user work.

## Acceptance Criteria

- Claude Code continues to load and operate the existing harness.
- Codex loads the same checkout as a local plugin on the documented supported host.
- All six commands are available through Codex skills.
- Every canonical agent has a matching static adapter; fresh-session canaries verify named instructions, model, and reasoning selection and document that child sandbox behavior inherits broader session permissions.
- Shared ticket state and telemetry remain compatible across platforms.
- Parity validation detects missing or stale adapters.
- README onboarding supports a fresh Claude Code or Codex installation.
- Existing unrelated working-tree changes remain intact.
