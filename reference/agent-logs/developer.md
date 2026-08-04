# developer — Performance Log

## 2026-04-06 — Created (sonnet)
- Role: Expert developer — implements plan steps, follows CLAUDE.md standards, creates nested CLAUDE.md files, handles fix cycles from QA findings
- Model rationale: Implementation requires reasoning about code structure, following patterns across files, and writing production-quality TypeScript/Python. Haiku would miss subtle pattern mismatches and produce code that violates layer rules. Sonnet balances code quality with cost. Opus unnecessary — the developer follows plans, it does not design systems.
- Effort: high
- Tools: Read Write Edit Bash Glob Grep (no Agent tool — developer does not spawn sub-agents)
- isolation: worktree
- permissionMode: default (not set)
- maxTurns: 50
- Key design decisions:
  - No Agent tool: developer focuses on implementation, not orchestration. Messaging teammates is done via SendMessage (part of agent teams), not by spawning sub-agents.
  - Worktree isolation: developer edits files in parallel with other agents without git conflicts.
  - Nested CLAUDE.md creation: developer is the only agent that both writes code and has full codebase context, making it the natural owner of local documentation.
  - Fix cycle mode: explicit section for handling re-spawns with QA findings, preventing wasteful re-implementation.
  - PlexTrac standards quick reference: embedded in prompt so the developer does not need to re-read the full workspace CLAUDE.md every spawn, but is instructed to read the full version for the target repo.

## 2026-05-07 — Status change

Status change: kept active as opt-in alternative to `implementer`. Orchestrator now defaults to `implementer`; `developer` fires for `lightweight` workflows or when `PT_DOOTS_DEV_MODE=loose`. Description updated to reflect the new role.

## 2026-07-20 - RETIRED (roster audit)
- Retired. 0 spawns across all 6 logged sessions (IO-2175 x3, ES1-1676, ES1-1677, IO-2349). The 2026-05-07 coexistence pattern set the condition "monitor whether loose mode gets used; if not, retire developer." Loose mode was never used.
- Duplicated `implementer`; silently drifted maxTurns 50 to 200 while unused (never logged until now).
- Actions: frontmatter `description` tagged RETIRED; `commands/pt-doots.md` Implementation Agent Selection collapsed both former routing branches (`PT_DOOTS_DEV_MODE=loose`, `lightweight`) to `implementer` so no branch spawns a retired agent; Agent Mapping row and Step 4a flow line updated. File retained (not deleted) for history.

## 2026-07-22 - Live-doc references repointed to implementer (retirement follow-up)
- Completed the retirement across the live reference docs: `reference/agent-prompts.md` (both implementation prompt templates renamed to their Implementer equivalents, spawn tags repointed to `pt-doots:implementer`, and the Test Writer template references to the old agent updated), `reference/workflow.md` (the 4a and 4d spawn headings and template references), and the implementation-agent example lines in `reference/metrics-format.md` and `reference/progress-format.md`.
- Also normalized two em dashes on lines we already owned: the `agents/developer.md` RETIRED prefix (now a colon) and the `commands/pt-doots.md` Hard Rules delegate line (now a semicolon).
- Left untouched: frozen `reference/v2-design.md` and `reference/v2-plan.md` (self-labeled historical/superseded), the illustrative SendMessage `to: "developer"` examples in other agent bodies, and the README developer-modes section. Those are out of this pass's scope and flagged for a follow-up.
