# acceptance-qa — Performance Log

## 2026-04-06 — Created (haiku)
- Role: Read-only product-minded QA agent — verifies implementation meets ticket acceptance criteria, returns per-criterion pass/fail report with evidence
- Model rationale: Task is reading acceptance criteria, finding corresponding code, and classifying pass/fail — the answer is in the text, no deep reasoning or code-tracing needed. Haiku is sufficient for structured verification against a checklist.
- Effort: medium
- Tools: Read Grep Glob (read-only — no file modification)
- disallowedTools: Write Edit Bash
- permissionMode: dontAsk
- maxTurns: 10

## 2026-05-07 — Audit finding: silent maxTurns drift
- Audit finding: maxTurns silently changed from 10 to 20. Same flag as code-reviewer.

## 2026-05-07 — Inline-context investigation (follow-up)
- Investigated `reference/agent-prompts.md` (Acceptance QA Prompt, lines 156-175), `reference/workflow.md` (Step 4c), and `commands/pt-doots.md` (Step 4c table). Acceptance QA spawn prompt passes ticket content plus a `{list from implementation}` plus the plan path — does NOT inline diffs. Reviewer must read files itself.
- Regresses inline-context discipline documented in `.local/team-manager/learned-patterns.md` lines 65-77.
- TODO: roll back maxTurns once spawn prompts are updated to inline diffs.

## 2026-05-07 — Followup
- Followup: rolled back maxTurns 20 → 10 after fixing spawn prompts.
