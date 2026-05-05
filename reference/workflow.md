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

Workflow: standard | lightweight | docs-only | custom
Documentation: yes | no
TDD: yes | no
Rationale: {why this workflow}
```

`Documentation` and `TDD` are orthogonal flags — they apply on top of any workflow type. `docs-only` implies `Documentation: yes`.

Show the recommendation to the user. They can override.

**Save to progress.md**: `Workflow: {type} — {rationale}`

---

## Step 0.7: Fetch Ticket Context (main context)

Run before research. This gathers the full Jira context into the notes folder.

### 1. Fetch ticket details + Bug Description

Use `mcp__atlassian__getJiraIssue` with **two calls**:
- Standard fields (summary, description, status, assignee, etc.)
- Custom fields: `["customfield_10227"]` — this is the **Bug Description** field (Defect issue type). It often contains the real bug details, repro steps, and expected/actual behavior when the standard `description` field is empty.

If `customfield_10227` has content, display it to the user alongside the standard description.

### 2. Download attachments

Check if the ticket has attachments (fetch with `fields: ["attachment"]`). If it does:

```bash
~/bin/jira-attachment {TICKET-KEY} {WORKSPACE}/notes/{TICKET-KEY}
```

This downloads all attachments to the notes folder. Common attachment types:
- `.ptrac` — PlexTrac report export (JSON), useful as test data
- `.docx` — Jinja templates or example exports, useful for OOXML inspection
- `.png`/`.jpg` — Screenshots showing the bug
- `.csv`/`.xml` — Import/export test files

Tell the user what was downloaded. These files are available to sub-agents via the notes folder path.

**If `~/bin/jira-attachment` is not installed**: Tell the user to run `/setup` or create an Atlassian API token at https://id.atlassian.com/manage-profile/security/api-tokens and save credentials to `~/.jira-attlasian-cred`.

**Save to progress.md**: `Ticket context fetched. Bug Description: {present/absent}. Attachments: {count} downloaded to notes/`

---

## Step 1: Research (sub-agent)

**Check notes first**: If `notes/{TICKET-KEY}/research.md` exists, read it and skip to Step 2.

**Otherwise**:
1. Fetch ticket via `/ticket {TICKET-KEY}` in main context (if not already done in Step 0.7)
2. Spawn `pt-doots:researcher` with the ticket content — use the **Researcher Prompt** from [agent-prompts.md](agent-prompts.md). Include Bug Description and list of downloaded attachments in the prompt.
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

**Standard workflow** — spawn all five in parallel:
- `pt-doots:code-reviewer` — PlexTrac CLAUDE.md standards
- `pt-doots:acceptance-qa` — acceptance criteria verification
- `pt-doots:edge-case-qa` — boundary conditions, failure modes
- `pt-doots:code-smells-reviewer` — design quality, coupling, duplication
- `pt-doots:test-reviewer` — test quality (hollow assertions, over-mocking, bloat)

Use the corresponding prompts from [agent-prompts.md](agent-prompts.md).

**Lightweight workflow** — spawn only:
- `pt-doots:code-reviewer` (single reviewer)
- `pt-doots:code-smells-reviewer` (design quality)
- `pt-doots:test-reviewer` (test quality — if changeset includes test files)

**Docs-only workflow** — spawn only:
- `pt-doots:code-reviewer` — verifies the doc changes for accuracy and consistency

**Custom workflow** — follow the reviewer set the scrum-master included in its WORKFLOW PLAN steps.

Consolidate all findings from all reviewers before proceeding.

**Save to progress.md**: `Quality gate complete. Code Review: {N}. Acceptance QA: {pass/fail or skipped}. Edge Case QA: {N or skipped}. Code Smells: {N}. Test Review: {N or skipped}.`

### 4d. Fix Findings (`pt-doots:developer`, fix-cycle mode)

Only if quality gate has actionable findings.

- Spawn with the **Developer Prompt (QA Fixes)** from [agent-prompts.md](agent-prompts.md)
- Pass consolidated findings from all reviewers
- Returns: fixes applied + any deferred
- **Run `/verify`. Fix failures (max 3 cycles).**

**Save to progress.md**: `Findings fixed. {N} applied, {N} deferred. Verification: {pass/fail}`

### 4e. Documentation (`pt-doots:documentarian`)

Only when the scrum-master set `Documentation: yes` in its recommendation, or when the workflow type is `docs-only`.

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
