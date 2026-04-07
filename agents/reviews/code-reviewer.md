# code-reviewer — Performance Log

## 2026-04-06 — Created (sonnet)
- Role: Read-only standards enforcer — reviews every changed file against CLAUDE.md rules for the target repo, returns structured findings with file, line, severity, and suggested fix
- Model rationale: Code review requires reasoning about code patterns, tracing layer violations, and understanding type system nuances. Haiku would miss subtle violations like `as unknown as T` patterns or repository-service injection. Sonnet provides the reasoning depth needed for accurate findings. Opus unnecessary — the reviewer applies known rules, it does not design new ones.
- Effort: high
- Tools: Read Grep Glob (read-only — no file modification)
- disallowedTools: Write Edit Bash
- permissionMode: dontAsk
- maxTurns: 15
- Key design decisions:
  - Comprehensive standards checklist embedded in prompt: all CLAUDE.md rules extracted and organized by repo so the reviewer does not need to re-read the full workspace CLAUDE.md every spawn, but covers every enforceable rule.
  - Explicit "What You Do Not Do" boundaries: no code fixes (Developer), no requirement checking (Acceptance QA), no edge case hunting (Edge Case QA). Prevents scope creep into adjacent agent roles.
  - Structured output format with severity levels: critical/high/medium/low with clear definitions ensures the Developer can prioritize fixes and the orchestrator can decide whether to block merge.
  - "CLEAN — no findings" explicit requirement: prevents the ambiguity of an empty output being mistaken for a failed or incomplete review.
  - Every finding must trace to a CLAUDE.md rule: prevents subjective style nitpicks that waste Developer time. If it is not in the standards, it is not a finding.
