# scrum-master — Performance Log

## 2026-04-06 — Created (haiku)
- Role: Read-only workflow advisor — classifies tickets and recommends workflow type (standard/lightweight/docs-only/custom)
- Model rationale: Task is classification and structured output based on signals in the text — no deep reasoning or code analysis needed. Haiku is sufficient.
- Effort: medium
- Tools: Read Grep Glob (read-only — no file modification)
- disallowedTools: Write Edit Bash
- permissionMode: dontAsk
- maxTurns: 8
