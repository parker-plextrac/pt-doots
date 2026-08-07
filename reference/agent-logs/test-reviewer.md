# test-reviewer — Performance Log

## 2026-04-22 — Created (sonnet)
- Role: Read-only reviewer that examines test code quality — catches hollow assertions, over-mocking, bloated permutation tests, ignored existing infrastructure, and AI-generated test smells
- Model rationale: Test review requires reasoning about what assertions actually verify, whether mocking strategies are sound, and judging if a test would fail on a real code change. Haiku would miss subtle issues like tests that assert mock return values rather than computed behavior. Sonnet provides the reasoning depth needed. Opus unnecessary — the reviewer applies a known catalog of test smells, it does not design new systems.
- Effort: high
- Tools: Read Grep Glob (read-only — no file modification)
- permissionMode: dontAsk
- maxTurns: 15
- Key design decisions:
  - Requires reading production code alongside test code: you cannot judge test quality without understanding what the test should verify. This is the core differentiator from other reviewers.
  - "Existing Infrastructure Found" section in output: forces the agent to search for repo test utilities before flagging tests that reinvent them. Prevents false positives where infrastructure genuinely does not exist.
  - Five smell categories cover the user's specific concerns: Hollow Assertions (tests must test something real), Over-Mocking (tests must fail when code changes), Bloat (no exhaustive permutations), Ignoring Existing Infrastructure (use what the repo provides), AI-Generated Test Smells (overly verbose, mirror-structure tests).
  - Framework Misuse category covers repo-specific anti-patterns: top-level before() for DI, Readable.from() instead of createMockStream, shared mutable state.
  - Explicit "Does NOT" boundaries: no production code review (Code Reviewer), no edge case hunting (Edge Case QA), no test writing (Test Writer). Prevents overlap with the 4 existing reviewers.
  - High severity reserved for false-confidence tests — tests that pass regardless of production correctness. This aligns severity with real risk rather than style preference.

## 2026-05-08 followup
- Spawn prompt in `reference/agent-prompts.md` updated to inline diffs (`{INLINED_DIFF}` + `{INLINED_FUNCTION_BODIES}` placeholders) and explicitly tell the agent "do NOT use the Read tool"; matches the inline-context discipline fix from yesterday's audit. test-reviewer's inline diff explicitly includes both test files AND their corresponding production files since the reviewer cannot judge assertion quality without seeing the production code under test.

## 2026-07-20 - maxTurns rollback 50 to 15 (roster audit)
- Set `maxTurns: 50` to `15`. Reconciles silent drift: created value was 15, drifted to 50 with no dated entry.
- Rationale: the 50 cap was a pre-inline-context band-aid. test-reviewer now receives fully-inlined diffs (test files and their production files) and is told not to Read, finishing in 0 to 7 tool calls. Same rollback applied to code-reviewer, acceptance-qa, and edge-case-qa on 2026-05-07 but never applied here.

## 2026-08-07 — Non-fix ban + trap-check added (roster audit)
- Same origin as the code-smells change: Jacob's "points at things, but doesn't really say what
  should be done." Added as cheap insurance rather than to fix an observed failure — this agent
  already asks for "a concrete suggestion" and has the best exemplars of the three ("Use
  `it.each(['active'])` ... 2 tests instead of 5", "Import and use the existing `createMockActor`").
  Its natural failure shape would be "consider asserting on X", which the ban now disqualifies.
- Also added the trap-check rule (verify your own suggestion; flag when the obvious fix no-ops).
- Performance remains strong. On PR #19 it found the self-fulfilling subject constants: two test
  constants byte-identical to the production defaults, so the tests passed whether or not the router
  forwarded its injected subject. A mutation test later confirmed it — all 59 tests in those two
  files stayed green with the routers ignoring the injected value. On IO-2375 it caught a hollow
  assertion and a tautology, and correctly overruled code-smells on injecting `handle_job` by citing
  the repo's own inject-at-the-edges rule, which remains the best single judgment call in the data.
