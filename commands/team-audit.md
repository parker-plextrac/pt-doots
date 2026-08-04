---
name: team-audit
description: >
  Run a full agent team audit — reviews roster health, agent performance, and
  workflow effectiveness. Spawns the Team Manager for a comprehensive review.
  Triggers: "team audit", "audit the team", "review agents", "roster check",
  "how are the agents doing", "/team-audit".
---

# Team Audit — Agent Roster Health Check

Full roster audit. Run end-of-day, end-of-sprint, or whenever you want a thorough review of agent health, performance trends, and workflow effectiveness. This is the deep review — distinct from the lightweight roster check that runs at the start of every `/pt-doots` session.

**Two locations this command uses** (resolve both up front):

- **`{PLUGIN}`** — the pt-doots plugin directory, holding the plugin's own CODE (`agents/`, `commands/`, `reference/`); this is what agent edits get committed to. Resolve in order: use `$CLAUDE_PLUGIN_ROOT` if it is set and contains `commands/team-audit.md`; otherwise fall back to `{WORKSPACE}/pt-doots` (with `{WORKSPACE}` = the workspace root that holds the PlexTrac product repos).
- **`$STATE`** — `${HOME}/.claude/pt-doots`, the home-anchored telemetry/state directory. Metrics, workflow history, and learned patterns live under `$STATE/.local/`. It is anchored to `$HOME` so it is always resolvable and survives plugin reinstalls, it lives OUTSIDE the plugin tree, and it is never committed. See `commands/pt-doots.md` § Telemetry for the full rationale.

---

## Pre-flight

1. **Verify Team Manager agent exists:**
   ```bash
   test -f "{PLUGIN}/agents/team-manager.md" && echo "OK" || echo "MISSING"
   ```
   If missing: "Team Manager agent not found. Run `/bootstrap-team` first to create the agent team."

2. **Check `.local/` for metrics data (warning, not blocker):**
   ```bash
   test -f "$STATE/.local/team-manager/metrics-summary.md" && echo "HAS_METRICS" || echo "NO_METRICS"
   test -f "$STATE/.local/scrum-master/workflow-history.md" && echo "HAS_HISTORY" || echo "NO_HISTORY"
   ```
   If either file is missing: print a warning and proceed with a qualitative-only audit:
   > "Metrics files not found — audit will be qualitative-only (agent definitions and review logs, no run-count or fix-cycle data). To get full audit data, ensure pt-doots telemetry is wired (see `commands/pt-doots.md` § Telemetry)."

   The audit still proceeds. Treat any missing files as empty data sets in subsequent steps.

3. **Initialize directories** (in case they exist but are incomplete):
   ```bash
   mkdir -p "$STATE/.local/team-manager" "$STATE/.local/scrum-master"
   ```

---

## Audit Procedure

### Step 1: Gather All Data

Read all available data from the filesystem:

1. **Agent definitions** — all `.md` files in `{PLUGIN}/agents/`
2. **Performance logs** — all `.md` files in `{PLUGIN}/reference/agent-logs/`
3. **Metrics summary** — `$STATE/.local/team-manager/metrics-summary.md`
4. **Workflow history** — `$STATE/.local/scrum-master/workflow-history.md`
5. **Learned patterns** — `$STATE/.local/team-manager/learned-patterns.md` (may not exist yet — that's fine)

Read ALL of these files. The Team Manager needs the full picture to make informed recommendations.

### Step 2: Spawn Team Manager for Full Audit

Spawn Team Manager (foreground, `name: "team-manager"`) with task:

```
You are performing a full roster audit for the PlexTrac agent team.

Here is ALL the data you need to analyze:

## Agent Definitions
{paste contents of every agents/*.md file}

## Performance Logs
{paste contents of every reference/agent-logs/*.md file}

## Metrics Summary
{paste contents of $STATE/.local/team-manager/metrics-summary.md}

## Workflow History
{paste contents of $STATE/.local/scrum-master/workflow-history.md}

## Learned Patterns
{paste contents of $STATE/.local/team-manager/learned-patterns.md, or "No patterns file yet — this is the first audit."}

Your task: Full roster audit. Analyze all data and return a structured report with these sections:

### Agent Health
For each agent: name, model, run count (from metrics), any issues or patterns observed.
Flag agents that are underperforming (e.g., consistently missing issues, shallow output).
Flag agents that may be overpowered for their task (e.g., using sonnet for work haiku could handle).

### Proposed Changes
For each proposed change, include:
- What: create / modify / bump model / adjust prompt / retire
- Agent name and current vs proposed state
- Evidence: which tickets or metrics support this change
- Rationale: why this change will improve outcomes

Structure each as a PITCH block:
PITCH: {action} "{agent-name}"
Model: {current} → {proposed} (if changing)
Tools: {changes, if any}
Rationale: {evidence-based reasoning}

### Workflow Notes
- Scrum Master patterns (which workflows chosen, appropriateness)
- Quality gate timing and effectiveness
- Fix cycle counts (target: ≤2 average)
- Any workflow steps that are consistently skipped or problematic

### Cost Summary
- Estimated token usage by model tier (opus, sonnet, haiku)
- Most expensive agent per run
- Opportunities to reduce cost without sacrificing quality

Return "ROSTER CHECK: healthy" with the full report even if no changes are proposed.
Return "ROSTER CHECK: pitch pending" if you have proposed changes.
```

### Step 3: Print the Report

Print the Team Manager's full report to the user. The report should look like:

```
## Team Audit — {date}

### Agent Health
- Scrum Master (haiku): {N} runs, {status}
- Researcher (sonnet): {N} runs, {status}
- Implementer (sonnet): {N} runs, {status}
- Test Writer (sonnet): {N} runs, {status}
- Code Reviewer (sonnet): {N} runs, {status}
- Acceptance QA (haiku): {N} runs, {status}
- Edge Case QA (sonnet): {N} runs, {status}
- Code Smells Reviewer (sonnet): {N} runs, {status}
- Test Reviewer (sonnet): {N} runs, {status}
- Self-Containment Reviewer (sonnet): {N} runs, {status}
- Re-Reviewer (sonnet): {N} runs, {status}
- Repro Verifier (sonnet): {N} runs, {status}
- Documentarian (haiku): {N} runs, {status}
- Voice Stylist (sonnet): {N} runs, {status}
- Team Manager (opus): {N} runs, {status}

### Proposed Changes
{numbered list of pitches, or "None — roster is healthy."}

### Workflow Notes
{summary of workflow patterns and effectiveness}

### Cost Summary
{token breakdown by model tier}
```

### Step 4: Approval Loop for Proposed Changes

If the Team Manager proposed changes:

**For each proposed change:**

1. Print the pitch to the user:
   ```
   Proposed Change {N}/{total}:

   PITCH: {action} "{agent-name}"
   Model: {current} → {proposed}
   Tools: {changes}
   Rationale: {evidence}

   Approve? (yes / no / modify: "change to haiku instead")
   ```

2. **Wait for user approval.** Do not batch — present one at a time so the user can evaluate each independently.

3. If **approved**: queue for execution.
4. If **modified**: note the modifications for execution.
5. If **rejected**: skip and move to the next pitch.

### Step 5: Execute Approved Changes

For each approved change, spawn Team Manager (foreground, `name: "team-manager"`) with task:

```
Execute this approved change to the agent roster:

{paste the approved pitch, including any user modifications}

Instructions:
- If creating a new agent: write the agent file to {PLUGIN}/agents/{agent-name}.md
  and the review log to {PLUGIN}/reference/agent-logs/{agent-name}.md
- If modifying an existing agent: update the agent file and append an entry
  to the review log explaining what changed and why
- If bumping a model: update the frontmatter and append to review log
- If retiring an agent: note it in the review log (do not delete the file —
  add a "RETIRED" note to the frontmatter description)

Return:
AGENT UPDATED: {agent-name}
- File: agents/{agent-name}.md
- Review log: reference/agent-logs/{agent-name}.md
- Change: {summary of what was done}
```

### Step 6: Update Learned Patterns

After all changes are executed (or if no changes were needed), spawn Team Manager one final time (foreground, `name: "team-manager"`) with task:

```
Review all metrics and update learned patterns.

Current metrics:
{paste contents of $STATE/.local/team-manager/metrics-summary.md}

Current workflow history:
{paste contents of $STATE/.local/scrum-master/workflow-history.md}

Current learned patterns:
{paste contents of $STATE/.local/team-manager/learned-patterns.md, or "No patterns file yet."}

Your task:
1. Analyze all metrics for recurring patterns
2. Update $STATE/.local/team-manager/learned-patterns.md with any new or modified patterns
3. Each pattern should include:
   - Category: workflow | agent-performance | codebase
   - Confidence: low (1 observation) | medium (2 observations) | high (3+ observations)
   - Description: what the pattern is
   - Evidence: which tickets support it
   - Action: how agents should respond to this pattern
4. Archive any patterns that are no longer relevant (mark as RETIRED, don't delete)
5. Update the "Last updated" timestamp and "Total tickets analyzed" count

Return a summary of patterns added, modified, or retired.
```

---

## Completion

Print a summary of the audit:

```
## Team Audit Complete

{If changes were made:}
### Changes Applied
{numbered list of changes with agent names}

### Patterns Updated
{summary from Step 6 — new, modified, retired}

Agent definitions were modified. Commit when ready:
  git add {PLUGIN}/agents/ {PLUGIN}/reference/agent-logs/

{If no changes were made:}
No changes — roster is healthy.

{If patterns were updated:}
Learned patterns updated in $STATE/.local/team-manager/learned-patterns.md
(runtime state in ${HOME}/.claude/pt-doots — not committed to git)
```

If agent definitions were modified, suggest committing:
> "Agent definitions were updated. Ready to commit? (yes/no)"

---

## References

- **Agent definitions**: `{PLUGIN}/agents/` — one `.md` file per agent
- **Agent reviews**: `{PLUGIN}/reference/agent-logs/` — performance logs per agent
- **Metrics**: `$STATE/.local/team-manager/metrics-summary.md` — per-run data
- **Workflow history**: `$STATE/.local/scrum-master/workflow-history.md`
- **Learned patterns**: `$STATE/.local/team-manager/learned-patterns.md`
- **Bootstrap**: `/bootstrap-team` — one-time agent roster setup
- **Workflow**: `/pt-doots` — the orchestrator that generates the metrics this audit reviews
