# scrum-master — Performance Log

## 2026-04-06 — Created (haiku)
- Role: Read-only workflow advisor — classifies tickets and recommends workflow type (standard/lightweight/docs-only/custom)
- Model rationale: Task is classification and structured output based on signals in the text — no deep reasoning or code analysis needed. Haiku is sufficient.
- Effort: medium
- Tools: Read Grep Glob (read-only — no file modification)
- disallowedTools: Write Edit Bash
- permissionMode: dontAsk
- maxTurns: 8

## 2026-05-07 — Removed vestigial `disallowedTools` field (CHANGE 5)
- What changed: Frontmatter `disallowedTools: Read Write Edit Bash Grep Glob Agent` removed.
- Why: `learned-patterns.md` lines 42-45 documents that `disallowedTools` is NOT enforced by the agent teams framework. IO-2158 confirmed this 3 times in a single session — the SM had `disallowedTools` set but still made 16 tool calls. The `tools` whitelist (or omitting `tools` entirely with `maxTurns: 1`) is the actual enforcement. The field was misleading and signaled false safety. Other agents have the field stripped via the same audit (re: change 5 batch).

## 2026-05-07 — Logging silent maxTurns drift (CHANGE 4)
- Drift observed: maxTurns 8 → 1 (no prior dated entry). Justified by the IO-2158 tool-strip fix (learned-patterns.md lines 60-63: classifier agents work best at maxTurns: 1) but never logged. Counted as silent drift.
- Action: This entry retroactively documents the change. No rollback — the value is correct.

## 2026-05-07 — Documentarian polarity flip (CHANGE 6)
- What changed: Documentation classifier section rewrote. Default polarity is now "yes"; only set "no" when the ticket has zero documentation surface (pure refactors with no behavior change, test-only changes, etc.). Replaces the prior Confluence-only signaling.
- Why: Roster audit found documentarian was being skipped on tickets that ship behavior changes. Default-yes makes the agent auto-fire for the majority case.
