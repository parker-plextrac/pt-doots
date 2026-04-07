# edge-case-qa — Performance Log

## 2026-04-06 — Created (sonnet)
- Role: Read-only breaker QA agent — examines every changed function for boundary conditions, null/undefined/empty handling, error paths, race conditions, async edge cases, and data permutations. Returns structured scenarios the test suite should cover.
- Model rationale: Edge case analysis requires reasoning about code behavior under unusual inputs, tracing call paths to verify assumptions, and understanding concurrency and async patterns. Haiku was initially considered but the spec notes it missed a race condition in a simulated scenario (IO-2112). Sonnet provides the reasoning depth needed to catch subtle concurrency issues, TOCTOU gaps, and data flow edge cases. Opus unnecessary — the agent applies a systematic checklist to code it reads, it does not design new systems.
- Effort: high
- Tools: Read Grep Glob (read-only — no file modification)
- disallowedTools: Write Edit Bash
- permissionMode: dontAsk
- maxTurns: 15
- Key design decisions:
  - Comprehensive Breaker Mindset checklist embedded in prompt: seven categories (null/empty, boundaries, error paths, race conditions, async, data permutations, security vectors) ensure systematic coverage rather than ad-hoc intuition.
  - PlexTrac-specific edge case section: Kysely empty arrays, Redis key expiry, BullMQ idempotency, CK Editor HTML, Pydantic validation — these are historically problematic patterns in the codebase that a generic breaker would miss.
  - Explicit "What You Do Not Do" boundaries: no code quality (Code Reviewer), no requirement verification (Acceptance QA), no code writing (Developer/Test Writer). Prevents scope creep.
  - Structured output with risk levels: critical/high/medium/low with clear definitions ensures the Developer can prioritize fixes and the orchestrator can decide merge-readiness.
  - Separate "Untested Scenarios" section: creates a direct handoff to the Test Writer — each scenario can become a test case without reinterpretation.
  - Minimum 3 untested scenarios requirement: forces thoroughness. The spec's success criteria require at least 3, so this is enforced in the prompt.
