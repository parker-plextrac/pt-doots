# pt-doots v2 Implementation Plan

> **Historical — superseded.** This was the implementation plan for the v2 refactor that produced the current `commands/pt-doots.md` and `reference/workflow.md`. References to a `thorough` workflow type and an ECC second-pass reviewer were dropped during reconciliation; the live workflow types are `standard | lightweight | docs-only | custom` (see `agents/scrum-master.md`).

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor the pt-doots command from a 455-line monolith into a ~120-line orchestrator that references docs, uses pt-doots agents, and routes workflows dynamically.

**Architecture:** The command becomes a thin routing layer. Detailed workflow steps live in `reference/workflow.md`. Agent spawn prompts live in `reference/agent-prompts.md`. The command inlines only trigger detection, mode routing, agent mapping, and gate conditions.

**Tech Stack:** Claude Code plugin skill files (Markdown with YAML frontmatter)

---

## Task 1: Rewrite `commands/pt-doots.md` — Thin Orchestrator

**Files:**
- Rewrite: `commands/pt-doots.md` (455 lines → ~120 lines)

- [ ] **Step 1: Replace the entire file with the new command**

Replace the full contents of `commands/pt-doots.md` with:

~~~markdown
---
name: pt-doots
description: "PlexTrac ticket workflow: tackle a Jira ticket end-to-end with sub-agents, check ticket status from notes, or save progress. Triggers: \"tackle IO-2097\", \"do IO-2097\", \"check on IO-2097\", \"save our work\"."
---

# PlexTrac Work — Orchestrator

You are the **orchestrator**. You manage flow, talk to the user, and delegate heavy work to sub-agents. You do NOT read source code, run tests, or review code yourself — agents do that and return summaries.

**Workspace**: Walk up from cwd until you find a directory containing PlexTrac product repos (`product-core-backend`, `product-core-frontend`, `product-services-export`, `product-services-mcp`). Store as `WORKSPACE`.

## Notes Folder

Each ticket: `{WORKSPACE}/notes/{TICKET-KEY}/` — contains `research.md`, `plan.md`, `progress.md`. See [reference/progress-format.md](../reference/progress-format.md) for log format.

**Persistence rule**: Save to `progress.md` after EVERY step and BEFORE launching any sub-agent (crash recovery).

---

## Mode Detection

Detect intent from the user's message:

| Signal | Mode |
|--------|------|
| "check on {KEY}", "status {KEY}", "where are we on {KEY}" | **Status Check** |
| "save our work", "save progress", "let's save" | **Save Progress** |
| "tackle {KEY}", "do {KEY}", "implement {KEY}", "doots {KEY}" | **Tackle Ticket** |

---

## Status Check Mode

1. Read `notes/{TICKET-KEY}/progress.md` (if missing, say "No notes found for {KEY}")
2. Display last session summary, completed steps, what remains
3. Done — do NOT start the workflow

---

## Save Progress Mode

1. Append to `notes/{TICKET-KEY}/progress.md`: timestamp, session summary, completed steps, key decisions, files changed, current step, what remains, gotchas
2. Update `plan.md` if approach changed during implementation
3. Offer to commit if uncommitted changes exist

---

## Tackle Ticket Mode

Read [reference/workflow.md](../reference/workflow.md) for detailed step instructions. Read [reference/agent-prompts.md](../reference/agent-prompts.md) for spawn prompt templates.

### Flow

```
Step 0:   Load Context        (main — read notes, git state)
Step 0.5: Route Workflow      (pt-doots:scrum-master → workflow recommendation)
Step 1:   Research            (pt-doots:researcher)
Step 2:   Plan                (main — user interaction)
Step 3:   Create Branch       (main)
Step 4a:  Implement           (pt-doots:developer) → /verify
Step 4b:  Write Tests         (pt-doots:test-writer) → /verify
Step 4c:  Quality Gate        (pt-doots:code-reviewer + acceptance-qa + edge-case-qa, parallel)
          If thorough:        (+ ECC language-matched reviewer as second pass)
Step 4d:  Fix Findings        (pt-doots:developer, fix-cycle mode) → /verify
Step 4e:  Documentation       (pt-doots:documentarian — if workflow includes it)
Step 5:   Commit              (main — commit gate)
Step 6:   Handoff             (main — summary, offer /create-pr)
```

### Agent Mapping

| Step | Agent (`subagent_type`) | Notes |
|------|------------------------|-------|
| 0.5 | `pt-doots:scrum-master` | haiku, 1 turn. Returns workflow type + agent plan. |
| 1 | `pt-doots:researcher` | Writes research.md, returns summary. |
| 4a, 4d | `pt-doots:developer` | Worktree isolation. 4d = fix-cycle mode. |
| 4b | `pt-doots:test-writer` | Worktree isolation. |
| 4c | `pt-doots:code-reviewer` | Read-only. PlexTrac standards. |
| 4c | `pt-doots:acceptance-qa` | Read-only. Acceptance criteria. |
| 4c | `pt-doots:edge-case-qa` | Read-only. Boundary conditions. |
| 4c | `everything-claude-code:typescript-reviewer` or `python-reviewer` | Only for "thorough" workflow. |
| 4e | `pt-doots:documentarian` | Only when scrum-master recommends it. |

### Workflow Types (from scrum-master)

| Type | Skip | Review depth |
|------|------|-------------|
| **lightweight** | Research (or minimal), acceptance-qa, edge-case-qa | Single reviewer |
| **standard** | Nothing | Parallel quality gate (3 reviewers) |
| **thorough** | Nothing | Parallel quality gate + ECC second pass + documentation |

User can override the scrum-master's recommendation.

### Verification Loop

After every code change → run `/verify`. Max 3 fix cycles per failure. If still failing after 3 → STOP, ask the user.

### Commit Gate

ALL must be true before committing:
- [ ] Quality gate ran (4c)
- [ ] Findings fixed or explicitly deferred (4d)
- [ ] Verification passed after most recent change
- [ ] All plan steps implemented
- [ ] No outstanding [GOVERNANCE] items unaddressed

Show checklist to user before committing. Never push. Offer `/create-pr`.

### Team Tools (from plextrac plugin)

| Command | Step | Purpose |
|---------|------|---------|
| `/ticket` | 1 | Fetch Jira ticket details |
| `/verify` | 4 (all loops) | Lint, typecheck, tests |
| `/create-pr` | 6 | Push + create PR with template |
| `/logs` | Debug | View service logs |
~~~

- [ ] **Step 2: Verify line count is under 150 lines**

Run: `wc -l commands/pt-doots.md`
Expected: under 150 lines (target ~120)

- [ ] **Step 3: Commit**

```bash
git add commands/pt-doots.md
git commit -m "refactor: rewrite pt-doots command as thin orchestrator"
```

---

## Task 2: Update `reference/workflow.md` — Single Source of Truth

**Files:**
- Rewrite: `reference/workflow.md` (247 lines → ~260 lines, updated content)

- [ ] **Step 1: Replace the entire file with updated workflow**

Replace the full contents of `reference/workflow.md` with:

~~~markdown
# PlexTrac Ticket Workflow

Detailed step-by-step instructions for completing a Jira ticket. The orchestrator (`commands/pt-doots.md`) manages flow and references this doc for step details.

## Architecture

Main conversation = **orchestrator**. It holds the plan, talks to the user, delegates heavy work to sub-agents. Sub-agents return summaries; all file-reading noise stays in their context.

**Context budget**: The orchestrator holds the plan, agent summaries, and user conversation. Everything else lives in sub-agent context.

## Workspace Detection

Walk up from cwd until you find a directory containing PlexTrac product repos (`product-core-backend`, `product-core-frontend`, `product-services-export`, `product-services-mcp`). Store as `{WORKSPACE}`.

## Notes Folder

Each ticket: `{WORKSPACE}/notes/{TICKET-KEY}/` with `research.md`, `plan.md`, `progress.md`.

**Incremental persistence**: `progress.md` updated after EVERY step. See [progress-format.md](progress-format.md) for format.

**Pre-dispatch saves**: Before launching any sub-agent, SYNCHRONOUSLY save to `progress.md` what is about to happen.

---

## Step 0: Load Context (main context)

Run at the start of every session:

1. Check `notes/{TICKET-KEY}/` for existing files (progress.md, plan.md, research.md)
2. Check git state (branch, uncommitted changes, commits ahead of main)
3. Check for stale "in progress" state from crashed sessions
4. Show status summary to user:
   ```
   ## {TICKET-KEY} — Session Restore

   **Branch**: `{branch}` ({N} commits ahead of main)
   **Last session**: {date from progress.md}
   **Completed**: {list completed steps}
   **Next**: {what comes next}
   **Uncommitted changes**: {yes/no}
   ```
5. Save session start to progress.md

If no notes exist, this is a new ticket — proceed to Step 0.5.

---

## Step 0.5: Route Workflow (sub-agent)

Spawn `pt-doots:scrum-master` with the ticket summary (title, description, acceptance criteria).

It returns a structured recommendation:
```
WORKFLOW RECOMMENDATION

Workflow: standard | lightweight | thorough
Review depth: standard | thorough
Documentation: yes | no
TDD: yes | no
Rationale: {why this workflow}
```

Show the recommendation to the user. They can override.

**Save to progress.md**: `Workflow: {type} — {rationale}`

---

## Step 1: Research (sub-agent)

**Check notes first**: If `notes/{TICKET-KEY}/research.md` exists, read it and skip to Step 2.

**Otherwise**:
1. Fetch ticket via `/ticket {TICKET-KEY}` in main context
2. Spawn `pt-doots:researcher` with the ticket content — use the **Researcher Prompt** from [agent-prompts.md](agent-prompts.md)
3. Researcher explores codebase, writes `research.md`, returns 2-3 paragraph summary
4. Main context receives only the summary

**Save to progress.md**: `Research complete. Summary: {1-2 sentences}`

---

## Step 2: Plan with user (main context)

Stays in main because it requires user interaction.

1. From research summary, propose approach and steps
2. Each plan step should be **self-contained enough for a sub-agent**:
   - Exact file path(s)
   - What to change (code snippets or clear description)
   - "Done when" condition
3. User confirms or adjusts
4. Write approved plan to `plan.md`

**Save to progress.md**: `Plan approved. {N} steps. Approach: {1 sentence}`

---

## Step 3: Create Branch (main context)

- Format: `{issue-key}-{short-kebab-description}` — see [branch-naming.md](branch-naming.md)
- Branch from default (e.g. `main`). Confirm name if ambiguous.

**Save to progress.md**: `Branch created: {branch-name}`

---

## Step 4: Execute (sub-agents)

### Verification Loop

After every code change → run `/verify`. Max 3 fix cycles per failure. If still failing after 3 → STOP, ask the user.

```
Implement → Verify → Test → Verify → Review → Fix → Verify → Commit
            ▲ fail              ▲ fail           ▲ fail
            └─ fix ─┘           └─ fix ─┘        └─ fix ─┘
           (max 3x)            (max 3x)          (max 3x)
```

### 4a. Implementation (`pt-doots:developer`)

- Spawn with the **Developer Prompt (Implementation)** from [agent-prompts.md](agent-prompts.md)
- One agent per logical chunk, or one for the whole plan if small
- Returns: files changed + descriptions + any [GOVERNANCE] items
- If it has questions → orchestrator asks the user → spawns new agent with answers
- **Run `/verify`. Fix failures (max 3 cycles).**

**Parallel opportunity**: If plan has independent chunks (different files/modules), launch implementation agents in parallel.

**Save to progress.md**: `Implementation complete. Files: {list}. Verification: {pass/fail}`

### 4b. Tests (`pt-doots:test-writer`)

- Spawn with the **Test Writer Prompt** from [agent-prompts.md](agent-prompts.md) (standard or TDD mode per scrum-master recommendation)
- Returns: test files created + pass/fail status
- **Run `/verify`. Fix failures (max 3 cycles).**

**Save to progress.md**: `Tests written. Files: {list}. Verification: {pass/fail}`

### 4c. Quality Gate — MANDATORY

**GATE: Never skip this step, even for small changes, any repo, or when resuming a session.**

**Standard workflow** — spawn all three in parallel:
- `pt-doots:code-reviewer` — PlexTrac CLAUDE.md standards
- `pt-doots:acceptance-qa` — acceptance criteria verification
- `pt-doots:edge-case-qa` — boundary conditions, failure modes

Use the corresponding prompts from [agent-prompts.md](agent-prompts.md).

**Thorough workflow** — after the parallel gate, also spawn:
- `everything-claude-code:typescript-reviewer` (for TS repos) or `everything-claude-code:python-reviewer` (for Python repos)
- This provides broader industry-pattern review on top of PlexTrac-specific standards

**Lightweight workflow** — spawn only:
- `pt-doots:code-reviewer` (single reviewer)

Consolidate all findings from all reviewers before proceeding.

**Save to progress.md**: `Quality gate complete. Code Review: {N}. Acceptance QA: {pass/fail}. Edge Case QA: {N}. [ECC: {N} if thorough]`

### 4d. Fix Findings (`pt-doots:developer`, fix-cycle mode)

Only if quality gate has actionable findings.

- Spawn with the **Developer Prompt (QA Fixes)** from [agent-prompts.md](agent-prompts.md)
- Pass consolidated findings from all reviewers
- Returns: fixes applied + any deferred
- **Run `/verify`. Fix failures (max 3 cycles).**

**Save to progress.md**: `Findings fixed. {N} applied, {N} deferred. Verification: {pass/fail}`

### 4e. Documentation (`pt-doots:documentarian`)

Only when the scrum-master recommended it (typically "thorough" workflow).

- Spawn with the **Documentarian Prompt** from [agent-prompts.md](agent-prompts.md)
- Returns: files updated + any Confluence suggestions
- Present Confluence suggestions to user for approval before acting

**Save to progress.md**: `Documentation updated. Files: {list}`

---

## Step 5: Commit (main context)

### Commit Gate — ALL must be true:
- [ ] Quality gate ran (4c)
- [ ] Findings fixed or deferred (4d)
- [ ] Verification passed after most recent code change
- [ ] All plan steps implemented
- [ ] No outstanding [GOVERNANCE] items unaddressed

Show checklist to user before committing:
```
## Commit Gate — {TICKET-KEY}

- [x] Quality gate: ran, {N} total findings → {N} fixed, {N} deferred
- [x] Verification: lint ✓, typecheck ✓, tests ✓
- [x] Plan steps: {N}/{N} complete
- [x] Governance: clear

Ready to commit: `{TICKET-KEY}: {short description}`
```

Stage relevant files, commit: `{TICKET-KEY}: short description`. **Never push.** Remind user to push.

**Save to progress.md**: `Committed: {hash} — {TICKET-KEY}: {description}`

---

## Step 6: Handoff (main context)

Present summary:
```
## {TICKET-KEY} — Complete

**Branch**: `{branch-name}`
**Commit**: `{hash}` — {message}
**Files changed**: {count}
{brief list}

**Tests**: {count} added/modified
**Quality gate**: {summary}
**Verification**: All passing
```

Ask: **"Ready to create a PR? I can use `/create-pr` to push and open a PR with the repo's template."**

**Save to progress.md**: `Handoff complete.` (or `PR created: {url}`)

---

## Sub-agent Sequencing

**Can parallelize:**
- Independent plan step implementations (different files/modules)
- Quality gate reviewers (code-reviewer + acceptance-qa + edge-case-qa)

**Must be sequential:**
- Research → Plan → Branch → Implement → Verify → Test → Verify → Review → Fix → Verify → Commit

---

## References

- Branch naming: [branch-naming.md](branch-naming.md)
- Agent spawn prompts: [agent-prompts.md](agent-prompts.md)
- Progress log format: [progress-format.md](progress-format.md)
~~~

- [ ] **Step 2: Commit**

```bash
git add reference/workflow.md
git commit -m "refactor: update workflow.md as single source of truth for pt-doots v2"
```

---

## Task 3: Update `reference/agent-prompts.md` — Remove Aspirational Patterns

**Files:**
- Modify: `reference/agent-prompts.md`

- [ ] **Step 1: Remove all `learned-patterns` blocks**

In every prompt template, remove these lines:
```
Learned patterns:
{paste from .local/team-manager/learned-patterns.md if it exists}
```

These reference a file that doesn't exist yet. Re-add when the team-manager actually produces it.

Affected prompts: Researcher, Developer (Implementation), Test Writer (Standard), Test Writer (TDD), Code Reviewer, Edge Case QA.

- [ ] **Step 2: Remove SendMessage references from prompts**

Since we're using basic sub-agents (not agent teams), remove these lines from the Code Reviewer, Acceptance QA, and Edge Case QA prompts:

From Code Reviewer:
```
You can message other active teammates (acceptance-qa, edge-case-qa) via SendMessage for cross-validation.
```

From Acceptance QA:
```
You can message other active teammates (code-reviewer, edge-case-qa) via SendMessage.
```

From Edge Case QA:
```
You can message other active teammates (code-reviewer, acceptance-qa) via SendMessage.
```

Note: The agents' own definition files (`agents/*.md`) still have SendMessage rules — that's fine. Those are dormant until agent teams mode is enabled. We only remove them from the spawn prompt templates to avoid confusion.

- [ ] **Step 3: Add agent type annotations to each prompt section header**

Update each section header to include the `subagent_type` so the orchestrator knows exactly what to spawn:

- `## Researcher Prompt` → `## Researcher Prompt (pt-doots:researcher)`
- `## Developer Prompt (Implementation)` → `## Developer Prompt — Implementation (pt-doots:developer)`
- `## Developer Prompt (QA Fixes)` → `## Developer Prompt — QA Fixes (pt-doots:developer)`
- `## Test Writer Prompt (Standard Mode — after implementation)` → `## Test Writer Prompt — Standard (pt-doots:test-writer)`
- `## Test Writer Prompt (TDD Mode — before implementation)` → `## Test Writer Prompt — TDD (pt-doots:test-writer)`
- `## Code Reviewer Prompt` → `## Code Reviewer Prompt (pt-doots:code-reviewer)`
- `## Acceptance QA Prompt` → `## Acceptance QA Prompt (pt-doots:acceptance-qa)`
- `## Edge Case QA Prompt` → `## Edge Case QA Prompt (pt-doots:edge-case-qa)`
- `## Documentarian Prompt` → `## Documentarian Prompt (pt-doots:documentarian)`

- [ ] **Step 4: Commit**

```bash
git add reference/agent-prompts.md
git commit -m "refactor: clean up agent-prompts.md for pt-doots v2"
```

---

## Task 4: Update `reference/progress-format.md` — Minor Additions

**Files:**
- Modify: `reference/progress-format.md`

- [ ] **Step 1: Remove aspirational fields, keep what's real**

In the template, make these changes:

Remove (not implemented):
```
- Roster check: healthy (or: pitch approved — {summary})
```

Remove (not implemented):
```
- Metrics written to .local/team-manager/metrics-summary.md
```

The `Workflow:` and `Execution mode:` fields stay — those ARE implemented by the scrum-master in v2.

- [ ] **Step 2: Commit**

```bash
git add reference/progress-format.md
git commit -m "refactor: remove aspirational fields from progress-format.md"
```

---

## Task 5: Verify and Final Commit

- [ ] **Step 1: Verify no duplication between command and workflow**

Read `commands/pt-doots.md` and `reference/workflow.md` side by side. Confirm:
- Command has no inline prompt templates (those are in agent-prompts.md)
- Command has no detailed step instructions (those are in workflow.md)
- Command has no progress format (that's in progress-format.md)
- Workflow has no mode detection logic (that's in the command)

- [ ] **Step 2: Verify command references are correct**

Confirm these relative links in the command resolve correctly:
- `[reference/workflow.md](../reference/workflow.md)` — exists
- `[reference/agent-prompts.md](../reference/agent-prompts.md)` — exists
- `[reference/progress-format.md](../reference/progress-format.md)` — exists

- [ ] **Step 3: Verify line count**

Run: `wc -l commands/pt-doots.md`
Expected: under 150 lines

- [ ] **Step 4: Review the full changeset**

Run: `git diff HEAD~4 --stat` to see all changed files and line counts.
Confirm: net line reduction (old command was 455 lines).
