# Codex Runtime Compatibility Mapping

Phase 1 keeps `commands/*.md` and `agents/*.md` canonical. A Codex skill reads
its complete canonical command file first, then this mapping; the canonical file wins on every behavior conflict. This document translates runtime mechanics only.

## Dispatch and agent lifecycle

Checked-in `codex/agents/*.toml` definitions are registered as direct
`[agents."<name>"]` `config_file` entries in `~/.codex/config.toml`, targeting
the live checkout. Named-agent dispatch must request the registered custom
agent name through the collaboration runtime; do not treat `task_name` alone or
a generic `spawn_agent` call as profile selection.
If the named agent is unavailable, not selected, or its selection cannot be
confirmed, STOP and report the blocked dispatch. It must not fall back to a generic or prompt-only agent.
Fresh-session runtime canaries prove that registered named-agent selection
applies the adapter's developer instructions, model, and reasoning effort.
The same canaries prove that this Codex runtime does **not** enforce an
adapter's `sandbox_mode`: a child declared `read-only` could still write under
the parent's broader session permissions. Keep `read-only` and
`workspace-write` declarations as forward-compatible intent metadata, but do
not treat them as security isolation. Child tool access inherits the parent or
broader session behavior, so the orchestrator must enforce every canonical
read/write boundary in the prompt and review the resulting actions.

After confirmed named-agent selection, the orchestrator may use `spawn_agent`,
`followup_task`, and `wait_agent` for that agent's lifecycle. It passes inline complete context: ticket,
workspace/repository, branch, plan constraints, file surface, prior reports, and
the exact requested outcome. The CLI has no direct named-agent flag; selection
is performed by requesting the registered name through collaboration dispatch.

Treat a completed turn as a report, not completion proof. Use `wait_agent` for a
real agent result before dependent work, and apply a completion barrier before
summarizing a phase. Only the orchestrator may call `followup_task`, after a
PARTIAL or BLOCKED report; it supplies the refreshed complete context.

Claude `maxTurns` has no Codex hard counterpart. The adapters preserve it as an
advisory interaction/tool-call budget: `haiku → gpt-5.6-luna`,
`sonnet → gpt-5.6-terra`, and `opus → gpt-5.6-sol`, with the original reasoning
effort. The expected lifecycle is one task turn and the PARTIAL/BLOCKED contract;
this is not a hard runtime limit.

## State, decisions, and isolation

Save `progress.md` synchronously before dispatch and after each step/report that
changes durable state. On ambiguity, make one decision at a time: flag-and-wait
with options and a recommendation rather than guessing or continuing that item.

Preserve canonical worktree isolation. Codex does not make a harness worktree
automatically: pass the exact repository and branch to writer agents, which then
follow the canonical worktree procedure. Keep all dispatches scoped to that
isolated worktree.

## Tool-name and service translation

The tool-name mapping is: Claude `Read`/`Grep`/`Glob` become Codex filesystem
read/search tools; `Bash` becomes `exec_command`; `Write`/`Edit` become
`apply_patch`; and, after verified named-agent selection, Task dispatch uses
`spawn_agent` while SendMessage continuation uses `followup_task` plus
`wait_agent`. These names do not relax canonical tool or approval boundaries.

Phase 1 shares telemetry at `${HOME}/.claude/pt-doots`; do not move it into the
plugin or invent a Codex-only state format. Where a canonical command prohibits
the Atlassian MCP, retain its canonical REST helper preference rather than
substituting an MCP integration.

## Canonical harness rules retained by reference

Read these rules from the loaded canonical command or agent instead of copying
their workflow here: the orchestrator never reads or writes product source; the
parallel quality gate; mandatory repro-verifier; and the mechanical documentation gate. The mapping preserves those contracts while translating only the runtime
mechanics above.
