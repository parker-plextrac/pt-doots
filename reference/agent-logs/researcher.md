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

## 2026-07-20 - Reconciled definition vs. body, removed Write (roster audit)
- Removed `Write` from the tools line (now `Read Grep Glob` plus Confluence MCP). The body already states "You have no Write tool" and the design has the orchestrator save research.md; the 2026-04-06 creation had Write explicitly disallowed. Write was added later with no log entry, so this removes the contradiction.
- Reconciled the turn budget: frontmatter had drifted to `maxTurns: 200` (created value 25) while the body still said "You have 20 turns." Set both frontmatter and body to `50`, a real budget for genuine 4-repo exploration (researcher runs of 4 to 14 min in metrics) without the drifted 200.

## 2026-08-19 — Altitude Check + Confirming a Negative (bundle change, universal practice)
- **Trigger, from a real run on IO-2387.** The ticket's root-cause trace named a crashing dispatch
  site, so the research brief asked "where should the filter live?" — a question that already
  pre-supposed a guard at a dispatch site. Two guard shapes were researched, built, and passed all
  six quality-gate reviewers plus the repro-verifier. Only a third round, spawned to ask whether the
  approach itself was right, challenged the premise and found a 2-line fix at the
  point where the data ENTERS the system: three crashes closed, plus a leak no dispatch-site guard
  could reach and four separately-parked bugs, for fewer lines than the guards it replaced.
- **The gap:** nobody asked what level the fix belonged at. A location named in the brief was
  inherited as a decision instead of read as a symptom report.
- **Added `## Altitude Check`:** every proposed approach names the level it fixes at plus a rejected
  alternative level. For validation / sanitization / normalization / type-dispatch shapes, the
  deciding question is where data enters and how many sites are downstream — N must be established
  before choosing, because an entry-point fix is one place and a dispatch-site fix is one of N.
  Explicitly binding even when the brief names a location.
- **Added `## Confirming a Negative`:** same session, the researcher reported "exactly one place a
  string becomes a parse tree" on the strength of tracing all 7 `parse_markup(` call sites, having
  never grepped the constructor itself. There were 5 live construction sites. Earlier in the same run
  it had named a single chokepoint that was wrong for the same reason, and caught that one only by
  widening on its own. Rule: a clean negative or any "there is only one X" claim needs a second
  search of a DIFFERENT SHAPE before it is reported as settled, and both searches get named.
- **Enforcement:** `Altitude` is now a required field on each approach in the Output Format. A rule
  the agent reads is advice; a field it must fill is a gate.
- **Placed in the bundle, not a user overlay**, per CLAUDE.md rule 5 — this is how research should be
  done, not one user's preference.
