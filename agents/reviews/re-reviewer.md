# re-reviewer — Performance Log

## 2026-05-07 — Created (sonnet) [backfilled retroactively]
- Role: Read-only verifier that checks whether prior review findings have been addressed in a PR's new commits. Returns one of {Addressed, Partial, Not addressed, Pushback warrants accepting} per finding.
- Model rationale: Verifying whether a fix matches a prior finding requires tracing the new diff against the original concern, understanding intent, and judging when a developer's pushback is reasonable. Sonnet is the right tier — the work is reasoning-heavy but bounded by the prior review document. Haiku would mis-classify partial fixes; opus is overkill for a comparison task.
- Effort: high
- Tools: Read Grep Glob (read-only)
- disallowedTools: Write Edit Bash
- permissionMode: dontAsk
- maxTurns: 15
- Intended use: Spawned by `/prs` when a saved review file shows `status: posted` and the PR's head SHA has advanced since the review was posted. NOT used in the standard `/pt-doots` workflow — re-review is a PR-dashboard concern, not a per-ticket concern.
- Status: File backfilled retroactively.

## 2026-07-20 - maxTurns rollback 50 to 15 (roster audit)
- Set `maxTurns: 50` to `15`, restoring the created value. The 15 to 50 drift was never logged.
- Rationale: re-reviewer works from an orchestrator-provided delta-diff file plus worktree path (context is pre-sliced), so the original 15-turn budget is sufficient. It never fired in the 6-session logged window (it is a /prs-only agent), so the inflated 50 was carrying unvalidated. Restoring to 15 matches the design and caps runaway cost.
