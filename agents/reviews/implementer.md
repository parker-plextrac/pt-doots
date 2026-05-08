# implementer — Performance Log

## 2026-04-29 — Created (sonnet)

- Role: Disciplined implementer — executes plan steps within a locked file surface, audits its own diff against the plan, and reports every deviation honestly. Replaces `developer` for tickets where plan-fidelity matters.
- Model rationale: Implementation requires reasoning about code structure, following patterns, and producing production-quality TS/Python. Sonnet is sufficient. The agent's failure mode is process discipline, not pattern recognition — a stronger model would not have prevented the silent re-architecting on IO-2204. The fix is structural (locked surface, mandatory audits), not a model bump.
- Effort: high
- Tools: Read Write Edit Bash Glob Grep (no Agent tool — implementer does not spawn sub-agents)
- isolation: worktree
- permissionMode: default (not set)
- maxTurns: 200
- Key design decisions:
  - **Renamed from `developer`** to signal a fresh contract. `developer.md` retained as fallback; retire after one successful ticket on `implementer`.
  - **Plan Surface Lock (Step 1)**: agent extracts file list from plan into a scratchpad block before any edits. File-level granularity. Out-of-surface writes require `[SCOPE-EXPANSION]` flag and stop. No removing existing exported symbols from in-surface files without explicit plan authority.
  - **Test-vs-Plan Conflict Protocol**: explicit named protocol. When a RED test contradicts the plan, agent stops, does NOT modify the test, does NOT rewrite the implementation, emits `[PLAN-TEST-CONFLICT]` with both quotes and waits for orchestrator. Directly targets the IO-2204 Site 2 streaming-hash failure mode.
  - **Forbidden-Pattern Audit (mandatory, counts not adjectives)**: pre-report grep counts for `as any`, `as unknown as`, `as Buffer`, test assertion counts, unwrapped external I/O. "All clean" is not acceptable phrasing — integers only. Hollow tests (zero assertions) are forbidden.
  - **Plan-Diff Audit (mandatory)**: required `## Deviations from Plan` section with `RECOMMEND ACCEPT` / `RECOMMEND PUSH BACK` self-rating per deviation. Empty section is a claim under audit, not an exemption. Lying about it costs more trust than honest deviations.
  - **Test Modifications section (mandatory)**: any edit to existing tests must be reported with rationale and "required by plan?" yes/no.
  - **Values framing over incident framing**: per Parker, the operating philosophy is "Speed isn't important. Clean implementations and following best practices is important." No inline IO-2204 incident — failure modes described abstractly in protocols.
  - **No new sub-agent**: a `plan-checker` would either rubber-stamp or duplicate the audit. Visibility (mandatory audit sections in the report) is the deterrent — orchestrator and Parker enforce.
  - **Audit is required content, not a hard block**: agent reports, Parker decides. Blocking inside the agent risked turn-budget overruns.
- Migration plan: side-by-side with `developer.md`. Orchestrator calls `implementer` for next IO-2204 cycle. Retire `developer.md` after one full successful ticket.
- Open monitoring questions for next reviews:
  - Does the audit catch deviations the agent would have hidden? (compare report against actual diff)
  - Does `[PLAN-TEST-CONFLICT]` actually fire when warranted, or does the agent still rewrite around tests?
  - Does the locked surface hold under fix-cycle pressure, or does scope creep return when findings demand cross-cutting changes?

## 2026-05-07 — Status change

Status change: promoted to default implementation agent for standard/medium workflows. Original migration plan (retire `developer.md` after one successful ticket) was modified — `developer` stays available for engineers who prefer the looser flow. Implementer remains canonical for strict plan-fidelity work.
