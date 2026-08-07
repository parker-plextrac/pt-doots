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

## 2026-08-07 — sonnet CONFIRMED, and the IO-2375 record corrected (roster audit; no config change)
- **Record correction first.** The IO-2375 entry attributes this agent's "no output" runs to the
  `haiku` pin. That was wrong. The cause was a harness delivery bug: the agent had completed its work
  and the report was sitting in its JSONL transcript. Recovery by parsing the transcript worked every
  time. A haiku-pinned run had also passed 3/3 on IO-2374 two days earlier, and a non-haiku
  `general-purpose` agent failed identically. Recording this so a future audit does not re-tier an
  agent on a falsified premise.
- **The sonnet bump stands anyway, on different evidence.** On IO-2175 (2026-06-24) at haiku, this
  agent validated against the plan instead of the ticket, returned 6/6 PASS, and a wrong-direction
  encoding defect shipped and was caught by Wilson in QA. That is the most expensive miss in the data
  set, and it was a judgment failure on a discriminating criterion — the tier-sensitive part of the
  job. The same run's flag notes the criterion had to be re-derived from the ticket, which is
  reasoning work, so prompt hardening alone does not close it.
- Counter-evidence weighed: haiku passed 3/3 (IO-2374) and 5/5 (IO-1622), so haiku handles easy
  criteria fine. The bump is insurance on the hard ones and it is cheap — 10 turns, 3 Reads observed.
- `effort: high` → `medium` was raised as a legitimate cost option and **declined**: this is the one
  gate whose miss reached QA.
- Recent quality is high. On PR #19 it verified all 6 stated claims and read one extra file to close
  an ambiguity the diff left rather than guessing, and it corrected the orchestrator's own
  mischaracterisation of the docs/shoulds changes.
