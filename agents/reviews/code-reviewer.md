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

## 2026-05-07 — Audit finding: silent maxTurns drift
- Audit finding: maxTurns silently changed from 15 to 50 between original log entry and current file. No review log entry recorded the change. Rationale at audit time was unclear — possibly to enable Verify-Before-Flag phase reads. Flagged for re-evaluation pending the inline-context investigation in Step 2 of CHANGE 4.

## 2026-05-07 — Inline-context investigation (follow-up)
- Investigated `reference/agent-prompts.md` (Code Reviewer Prompt, lines 132-152), `reference/workflow.md` (Step 4c quality gate), and `commands/pt-doots.md` (Step 4c table). Reviewer spawn prompts pass file lists (`{list from implementation}`) and plan paths (`{WORKSPACE}/notes/{TICKET-KEY}/plan.md`) — they do NOT inline diffs or file contents. Reviewers must Read files themselves to perform the review.
- This regresses the inline-context discipline documented in `.local/team-manager/learned-patterns.md` lines 65-77, which prescribes inlining all relevant code diffs in the prompt and instructing agents not to read files.
- TODO: roll back maxTurns once spawn prompts are updated to inline diffs.

## 2026-05-07 — Followup
- Followup: rolled back maxTurns 50 → 15 after fixing reviewer spawn prompts in reference/agent-prompts.md to inline diffs (per learned-patterns inline-context discipline). The 50-turn cap was a band-aid for the prompt regression, not a real requirement.
