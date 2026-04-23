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
