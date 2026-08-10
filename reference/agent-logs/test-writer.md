# test-writer — Performance Log

## 2026-04-06 — Created (sonnet)
- Role: Writes tests for newly implemented code across all PlexTrac repos — follows each repo's test framework, patterns, and conventions. Co-locates test files per convention. Runs targeted tests to verify they pass before returning.
- Model rationale: Test writing requires reasoning about code behavior, understanding function contracts, choosing meaningful test cases, and writing correct assertions with proper mocking. Haiku would produce shallow tests that miss error paths and boundary conditions. Sonnet balances test quality with cost.
- Effort: high
- Tools: Read Write Edit Bash Glob Grep (needs write access for test files, Bash for running tests)
- isolation: worktree (writes test files in parallel with other agents)
- permissionMode: default (not set — Bash commands need standard permission flow)
- maxTurns: 30
- Key design decisions:
  - Explicit scope boundary with Edge Case QA to prevent overlap and scope creep
  - Pattern absorption rule (must read existing test before writing) to ensure consistency
  - Per-repo test pattern sections pulled directly from CLAUDE.md standards
  - Does NOT modify production code — reports bugs as [GOVERNANCE] instead
  - Does NOT run full /verify — orchestrator handles that post-return

## 2026-08-07 — maxTurns 30 → 60 (roster audit; acted on a flag raised 2026-07-21 and never actioned)
- On IO-1622 this agent stalled twice at maxTurns 30 authoring e2e export tests. One resume
  delivered only the original RED tests plus a fixture, a fourth spawn added nothing, and the heavy
  test work was rerouted to implementer (200 turns). The 2026-07-21 session flagged "consider
  bumping" and it was never bumped and never logged.
- Scoped deliberately: 30 was sufficient on ES1-1676, ES1-1677, IO-2374 (2 spawns) and IO-2375
  (12 files). The stall is specific to Python e2e authoring in `product-services-export`.
- 60 is still well under implementer's 200, and one stall already costs a duplicate spawn plus a
  resume plus a wasted fourth spawn, which exceeds the raised cap. This is a net saving.

## 2026-08-10 — Concision pass (comment bloat + PR size)
- Trigger: a human reviewer called the workspace's PRs "a bit out of control" and asked to "fix
  comments and shit." Root cause was a rule interaction, not a missing rule: the overlays said
  comments must explain a non-obvious why, which every bloated comment passed, while separate
  no-size-caps guidance was being read across from code to prose. Fixed across the overlays, the
  implementer (write-time rule + audit counts), the orchestrator's planning step and commit gate,
  and the reviewers.
- This agent's share of that pass is recorded in the same commit. The shared test, used verbatim
  everywhere so it stays one idea: **would omitting this line let someone make a wrong change?**
  If not, it is commentary, not documentation.
- The other half is scope: PR size is decided at planning, not at review, so the planning step now
  estimates the file surface out loud and offers a split, and the commit gate asks whether every
  commit traces to the ticket in the branch name.
