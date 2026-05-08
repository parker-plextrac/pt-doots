# researcher — Performance Log

## 2026-04-06 — Created (sonnet)
- Role: Read-only codebase explorer — traces call paths, identifies affected files, documents current behavior, proposes approaches before planning
- Model rationale: Research requires reasoning about code structure, tracing indirect dependencies across multiple repos, and synthesizing findings into actionable approaches. Haiku would miss indirect call paths and produce shallow cross-service analysis. Sonnet balances depth with cost.
- Effort: high
- Tools: Read Grep Glob (read-only — no file modification)
- disallowedTools: Write Edit Bash
- permissionMode: dontAsk
- maxTurns: 25

## 2026-05-07 — Confluence reconnaissance + Related Documentation hand-off (CHANGE 7)
- What changed:
  - Output Format gains a required **Related Documentation** section with two sub-sections: "Helpful context" (background reading the planner/developer benefits from) and "Update candidates" (docs that will go stale once the ticket merges).
  - Researcher uses `mcp__atlassian__searchConfluenceUsingCql` and Grep/Glob across `**/README.md` and nested `CLAUDE.md` files to populate.
  - Empty sub-sections are explicitly marked "none found" — never omitted. Documentarian relies on this contract.
  - Success Criteria updated to require the section.
- Why: Documentarian was cold-walking changed files in Step 4e and missing existing Confluence/READMEs that needed updates. Researcher already explores the codebase deeply — it costs almost nothing to capture the doc surface as it goes, and it gives Documentarian a verified candidate list to work from.
- Risk: turn budget. Confluence search is slow. Researcher already has a 200-turn budget so the marginal cost is acceptable, but watch for runaway searches in the next audit. If turn usage spikes on tickets with broad doc surface, tighten the search scope.
- Open monitoring: does Documentarian actually use the candidate list, or does it re-walk on its own? Track in next audit.
