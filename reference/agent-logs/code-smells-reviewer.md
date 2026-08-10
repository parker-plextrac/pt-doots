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

## 2026-07-20 - maxTurns rollback 50 to 15 (roster audit)
- Set `maxTurns: 50` to `15`. Reconciles silent drift: the log-of-record created value was 15, drifted to 50 with no dated entry.
- Rationale: the 50 cap was a pre-inline-context band-aid. code-smells-reviewer now receives fully-inlined diffs (`{INLINED_DIFF}` plus `{INLINED_FUNCTION_BODIES}`) and is told not to Read, finishing in 0 to 7 tool calls. Same rollback applied to code-reviewer, acceptance-qa, and edge-case-qa on 2026-05-07 but never applied here.

## 2026-08-07 — Non-fix ban + trap-check added (roster audit)
- Origin: Jacob Fjermestad (repo owner) on the PR #19 review — "it's kind of giving JQ right now.
  It points at things, but doesn't really say what should be done."
- Added: a suggestion must name a change. "Worth documenting", "consider extracting X", "might be
  worth revisiting", and the smell restated as a command are all rejected. If no concrete change can
  be named, the smell is not understood well enough to report.
- Added: check your own suggestion before proposing it, and say so when the obvious fix silently does
  nothing or breaks an invariant elsewhere.
- Why this agent needed it most of the three that already asked for "a concrete suggestion": smell
  findings degrade to "consider extracting" more readily than rule findings, and the IO-2374 log
  records "5 findings (3 real; most kept-with-rationale)", which is acknowledged-but-not-actioned.
  Medium confidence — kept-with-rationale can also be a healthy conscious decline.
- Quality is otherwise good: correctly identified the dual-meaning `job_id` as root cause on
  IO-2375, and on PR #19 it converged independently with acceptance-qa on the same `job_type`
  weakness while correctly declining to flag long-but-cohesive code in a repo that rejects size caps.

## 2026-08-10 — Added Comment Bloat, and closed the no-size-caps loophole
- Trigger: a human reviewer on zenith-inbound PR #20 said the PRs were "a bit out of control" and
  "we're gonna have to fix comments and shit." The diff carried an 18-line comment deriving a
  `mem_limit`, a 13-line note on an aiobotocore bug, and a 5-line comment on a one-line constant.
  None of them had been flagged by any agent.
- Root cause, and it was a rule interaction rather than a missing rule: the Python overlay already
  said "comments explain the non-obvious why, not the what." Every one of those comments PASSED that
  test, because a derivation of a memory cap genuinely is a non-obvious why. The rule filtered
  unjustified comments and said nothing about justified-but-enormous ones. Meanwhile this agent was
  told three separate times not to flag anything as "too long" in a repo that rejects size caps, and
  zenith-inbound was named as such a repo. So the one reviewer positioned to catch it had been
  explicitly stood down.
- Added: **Comment Bloat** under Structural Smells, plus an explicit statement in the Conventions
  Source section that a no-size-caps repo exempts CODE and never PROSE, so the exemption is not read
  across. Paired with a proportion rule and a derivations-do-not-belong-in-source rule added to
  `reference/python-conventions.md`.
- The load-bearing sentence is the one that pre-empts the old escape hatch: do not clear a comment
  just because it states a real why, since that test passes for an essay.
- Note for a future audit: no agent owned comment density before this. self-containment-reviewer
  checks comments for leaked private context, documentarian checks them for accuracy, test-reviewer
  flags verbose setup but only in tests. The gap was structural, not a calibration miss.
