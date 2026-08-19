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

## 2026-08-07 — Two safety rules added (roster audit; both from real incidents)
- **Never `git restore` / `git checkout <file>` / `git clean` a file it did not create in this
  spawn.** On IO-2375 an agent's `git restore` destroyed an uncommitted human hand-edit,
  unrecoverably. A working tree can hold uncommitted human work and the agent cannot tell by looking.
  If a file needs reverting, report it and let the orchestrator decide. This agent is the only one
  with both Bash and a reason to reach for those commands.
- **"The gate cannot run here" now requires evidence** — the exact command and its verbatim output.
  On IO-2375 two implementers reported the smoke gate unrunnable and the orchestrator relayed it
  twice unchecked. `just smoke` ran fine, and running it found an unhandled 500 on an unknown
  organization id that six static reviewers, a repro-verifier, 188 unit tests and 34 integration
  tests had all missed (integration seeds the org so the FK always satisfies; unit mocks the
  repository so no FK exists). Cost two extra fix rounds and is the sole reason that ticket blew the
  ≤2 fix-cycle target. Same shape as the existing "nothing is pre-existing until proven otherwise"
  rule: an inconvenient claim about the environment needs evidence, not confidence.
- No model, tools, or turn change. This agent remains the strongest on the roster: it pushed back
  correctly on logging raw pydantic errors (they echo caller key names) and refused to fake a green
  gate when asked for two clean runs, reporting the honest failure instead.

## 2026-08-10 — Comment proportion made a write-time rule and a self-audit count
- Trigger: same PR #20 feedback that produced the code-smells-reviewer's Comment Bloat smell. Fixing
  only the reviewer was challenged, correctly: "we are shipping this broken part cause our QA will
  catch it." The producer needed the rule, not just the detector.
- Found: this agent had NOTHING encouraging comments and nothing constraining them. The only prose
  rule was CLAUDE.md leanness, and it ended with "implementation details that belong in code
  comments" — actively routing detail INTO comments. The self-audit had no comment check, so nothing
  caught density at write time.
- Added: a comment-proportion rule in the agent body (its own rule, not just the injected overlay's),
  stating that reasoning belongs in the implementer's REPORT and the commit message rather than the
  source; and two integer counts in the Forbidden-Pattern Audit, which is the existing
  counts-not-adjectives gate: comment blocks longer than the code they explain, and derivations or
  rejected alternatives left in source.
- Reworded the CLAUDE.md leanness rule so it no longer points overflow at code comments.
- Design note: the audit counts are the load-bearing half. A rule the agent reads is advice; a count
  it must report is a gate.

## 2026-08-19 — Premise-checking made standing behavior (Step 2b)
- **Trigger, from a real run on IO-2387.** The orchestrator put a researcher claim — "the single
  chokepoint is X" — into the implementer's brief as established fact. It was false. The implementer
  caught it and stopped, but ONLY because that one spawn prompt had been hand-written to say "confirm
  this yourself and STOP if it fails." The guardrail worked perfectly and worked by luck; without it
  the change would have shipped and reopened the very crash the ticket exists to fix.
- **The gap:** verifying a brief's factual claims was a per-spawn favor, not agent behavior. Nothing
  in the definition told the agent that a fact handed down in a brief is checkable, or that stopping
  is a legitimate outcome rather than a failed spawn.
- **Added `### Step 2b — Verify the Brief's Load-Bearing Facts`**, between Pattern-First Reading and
  Implement: check "only one X" / "only caller" / "unreachable" / "single chokepoint" claims cheaply,
  usually one grep, before building on them. If one is false, STOP and `[GOVERNANCE]` it with the
  refuting search rather than adapting the plan solo.
- **Framing matters here.** Written as the implementer being the last check on the research rather
  than as distrust of the orchestrator, and with stopping named explicitly as the desired outcome —
  otherwise the agent treats a halt as its own failure and pushes through.
- Same shape as the two 2026-08-07 rules and "nothing is pre-existing until proven otherwise": an
  inherited claim needs evidence, not confidence.
