# researcher — Performance Log

## 2026-04-06 — Created (sonnet)
- Role: Read-only codebase explorer — traces call paths, identifies affected files, documents current behavior, proposes approaches before planning
- Model rationale: Research requires reasoning about code structure, tracing indirect dependencies across multiple repos, and synthesizing findings into actionable approaches. Haiku would miss indirect call paths and produce shallow cross-service analysis. Sonnet balances depth with cost.
- Effort: high
- Tools: Read Grep Glob (read-only — no file modification)
- disallowedTools: Write Edit Bash
- permissionMode: dontAsk
- maxTurns: 25
