# Metrics and Workflow History Formats

Both files live under the home-anchored state dir `$STATE` = `${HOME}/.claude/pt-doots` (see [`commands/pt-doots.md` § Telemetry](../commands/pt-doots.md#telemetry) for why it is not inside the plugin tree). Paths below are relative to `$STATE`.

## Agent Metrics — `$STATE/.local/team-manager/metrics-summary.md`

```markdown
### {date} — Ticket {TICKET-KEY}
- Workflow: {type} (scrum-master recommendation)
- Execution mode: {standard | tdd}
- researcher ({model}): {duration estimate}, {summary}
- implementer ({model}): {duration estimate}, {verify cycles} verify cycles
- test-writer ({model}): {duration estimate}, {summary}
- code-reviewer ({model}): {duration estimate}, {N} findings
- acceptance-qa ({model}): {duration estimate}, {N}/{N} criteria passed
- edge-case-qa ({model}): {duration estimate}, {N} findings
- documentarian ({model}): {duration estimate}, {summary}
- Agents skipped: {list and why, from workflow plan}
- Quality gate: {summary of parallel agent results}
- Governance issues: {count and summary, or "none"}
- Total verify cycles: {count}
```

**`{model}` = the agent's pinned frontmatter `model:` tier** (haiku for scrum-master, acceptance-qa, documentarian; sonnet for researcher, implementer, test-writer, and the reviewers; opus for team-manager). Frontmatter pins ARE honored at spawn (verified 2026-07-20), so record each agent's pinned tier, NOT the orchestrator's session model. Writing the session model is what produced the discarded "(opus)" annotations a later audit had to throw out.

## Workflow History — `$STATE/.local/scrum-master/workflow-history.md`

```markdown
### {date} — {TICKET-KEY} ({workflow type})
- Ticket type: {description}
- Execution mode: {standard | tdd}
- Agents run: {list}
- Agents skipped: {list and reason}
- QA findings: code-reviewer {N}, acceptance-qa {N}, edge-case-qa {N}
- Fix cycles: {N}
- Outcome: {committed successfully | aborted | etc.}
- Flags: {any notable observations for future workflow decisions}
```
