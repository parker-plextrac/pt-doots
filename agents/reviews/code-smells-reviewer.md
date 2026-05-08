# code-smells-reviewer — Performance Log

## 2026-05-07 — Created (sonnet) [backfilled retroactively]
- Role: Read-only reviewer that identifies code smells (long methods, feature envy, data clumps, primitive obsession, excessive coupling, etc. — Fowler catalog) in changed code.
- Model rationale: Smell detection requires reasoning about cohesion, coupling, and abstraction quality across multiple files — pattern recognition over a learned catalog. Sonnet is sufficient: the agent applies a known taxonomy to code it reads, no novel architectural reasoning. Haiku considered but rejected — smells like feature envy and inappropriate intimacy require tracing data flow across class boundaries, which haiku tends to miss.
- Effort: high
- Tools: Read Grep Glob (read-only)
- disallowedTools: Write Edit Bash
- permissionMode: dontAsk
- maxTurns: 15
- Intended use: Spawned at the Step 4c quality gate in parallel with code-reviewer, acceptance-qa, edge-case-qa, and test-reviewer. Complements code-reviewer (standards-focused) by surfacing structural design issues the standards check would not catch.
- Status: File backfilled retroactively. The agent has been active in the workflow but had no review log entry until today.

## 2026-05-08 followup
- Spawn prompt in `reference/agent-prompts.md` updated to inline diffs (`{INLINED_DIFF}` + `{INLINED_FUNCTION_BODIES}` placeholders) and explicitly tell the agent "do NOT use the Read tool"; matches the inline-context discipline fix from yesterday's audit. Brings code-smells-reviewer in line with code-reviewer / acceptance-qa / edge-case-qa.
