# Metrics and Workflow History Formats

## Agent Metrics — `.local/team-manager/metrics-summary.md`

```markdown
### {date} — Ticket {TICKET-KEY}
- Workflow: {type} (scrum-master recommendation)
- Execution mode: {standard | tdd}
- researcher ({model}): {duration estimate}, {summary}
- developer ({model}): {duration estimate}, {verify cycles} verify cycles
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

## Workflow History — `.local/scrum-master/workflow-history.md`

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
