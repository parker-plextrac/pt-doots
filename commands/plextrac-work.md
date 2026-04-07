---
name: plextrac-work
description: PlexTrac ticket workflow: fetch a Jira ticket, research codebase, plan with the user how to tackle it, create a branch, run sub-agents to implement and review, then commit (never push). Use when working in a PlexTrac workspace on a Jira ticket—e.g. "tackle IO-2097", "tackle PROJ-123", "implement this ticket", "do IO-2097", "complete this ticket", "run the plextrac workflow for PT-456". Also handles "save our work" / "save progress" by updating notes/progress file.
---

# PlexTrac Work

Complete a Jira ticket in a **PlexTrac workspace** using **sub-agents to preserve main context**. The main conversation is an **orchestrator** — it holds the plan, delegates heavy work to sub-agents, and gets back summaries. All file-reading noise, test output, and review details stay in sub-agent context.

**Workspace**: Detect the workspace root from cwd — walk up until you find a directory containing PlexTrac product repos (`product-core-backend`, `product-core-frontend`, `product-services-export`, `product-services-mcp`). Store as `WORKSPACE`. If not inside a PlexTrac workspace, ask.

## Notes Folder — Source of Truth

Each ticket gets a folder at `{WORKSPACE}/notes/{TICKET-KEY}/`:

| File | Purpose | Updated when |
|------|---------|--------------|
| `research.md` | Codebase exploration findings | Step 1 (research sub-agent) |
| `plan.md` | Agreed implementation plan with steps | Step 2 (main context, with user) |
| `progress.md` | Running session log — crash recovery | **After every step completion** (incremental) |

**Incremental persistence rule**: `progress.md` is updated after EVERY step completion, not just on "save our work". This is crash recovery — if the session dies, the next session can resume from the last saved state.

### Progress log format

Each entry in `progress.md` follows this structure so future sessions can parse it:

```markdown
# {TICKET-KEY} Progress Log

## Session: {YYYY-MM-DD HH:MM}

### Step 0: Load Context
- Status: complete
- Resumed from: {previous session date, or "new ticket"}
- Branch: `{branch-name}` ({N} commits ahead of main)

### Step 1: Research
- Status: complete
- Summary: {1-2 sentence summary of findings}

### Step 2: Plan
- Status: complete
- Approach: {1 sentence}
- Steps: {N} implementation steps

### Dispatching: Implementation agent
- Plan steps: {which steps}
- Files in scope: {list}

### Step 4a: Implementation
- Status: complete
- Files changed: {list with one-line descriptions}
- Verification: pass (or: fail → fixed in {N} cycles)

### Step 4b: Tests
- Status: complete
- Test files: {list}
- Verification: pass

### Step 4c: Code Review
- Status: complete
- Agent: everything-claude-code:{language}-reviewer
- Findings: {N} actionable (or: clean)

### Step 4d: Fix Review Findings
- Status: complete
- Fixed: {N}, Deferred: {N}
- Verification: pass

### Step 5: Commit
- Status: complete
- Hash: `{short-hash}`
- Message: {TICKET-KEY}: {description}

### Step 6: Handoff
- Status: complete
- Branch ready for push and PR
```

**Rules:**
- Always append, never overwrite previous entries
- New sessions get a new `## Session:` header
- Pre-dispatch entries use `### Dispatching:` prefix
- Keep each entry concise — this is a log, not documentation

## When this skill applies

- Current workspace is under **the PlexTrac workspace**
- User provides a **Jira ticket** (key like `PT-1234`, `IO-2097`, link, or pasted content) and wants to **tackle**, **implement**, or **do** it
- User says **"save our work"**, **"save progress"**, **"let's save"** → save flow
- **Triggers**: "tackle IO-2097", "tackle this ticket", "implement PROJ-123", "do IO-2097", "complete PROJ-123", "run the plextrac workflow for PT-456"

---

## Sub-Agent Architecture

Main conversation = **orchestrator**. It manages flow, holds the plan, talks to the user. Heavy work is delegated to sub-agents.

| Agent | Type | Reads | Writes | Returns to main |
|-------|------|-------|--------|-----------------|
| **Research** | read-only | Jira ticket, codebase files | `research.md` | Summary of findings (2-3 paragraphs) |
| **Implement** | writes code | `plan.md`, source files | Source code changes | List of files changed + brief description |
| **Test** | writes code | Changed files, existing tests | Test files | List of tests added + pass/fail status |
| **Review** | read-only | All changed files, `plan.md` | Nothing | List of findings (actionable items only) |
| **Fix** | writes code | Review findings, source files | Source code fixes | List of fixes applied |
| **Verify** | read-only | Changed files | Nothing | Pass/fail for lint, typecheck, tests |

### Rules for sub-agents
- Each sub-agent gets a **self-contained prompt** with everything it needs — file paths, plan steps, standards to follow
- Sub-agents **do not talk to the user** — only the orchestrator talks to the user
- If a sub-agent encounters ambiguity, it returns the question to the orchestrator, which asks the user
- Launch **parallel sub-agents** when steps are independent
- Use `subagent_type: "general-purpose"` for implementation/fix, `subagent_type: "Explore"` for research, `subagent_type: "everything-claude-code:{language}-reviewer"` for review (see 4c for mapping)

---

## Step 0: Load Context (main context)

**Run this at the start of every session — even new tickets.**

1. **Check notes folder**: Read `notes/{TICKET-KEY}/` if it exists:
   - `progress.md` → restore where we left off (show last entry to user)
   - `plan.md` → restore the plan
   - `research.md` → restore research context
2. **Check git state**: What branch are we on? Any uncommitted changes? Any existing commits on this branch?
3. **Check for stale state**: If progress.md shows steps were "in progress" from a previous session, note them — they may need to be re-run
4. **Show status to user**:
   ```
   ## {TICKET-KEY} — Session Restore

   **Branch**: `{branch}` ({N} commits ahead of main)
   **Last session**: {date from progress.md}
   **Completed**: {list completed steps}
   **Next**: {what comes next}
   **Uncommitted changes**: {yes/no}
   ```

If no notes exist, this is a new ticket — proceed to Step 1.

**→ Save to progress.md**: `Session started. Loaded context from notes.` (or `New ticket — starting fresh.`)

---

## Step 1: Research (sub-agent)

- **FIRST — check notes folder**: If `notes/{TICKET-KEY}/research.md` exists, read it — skip to Step 2.
- **Otherwise**: Use the `/ticket` command to fetch and display the ticket details, then launch a **Research sub-agent** with the ticket content.

### Research sub-agent prompt template
```
You are researching Jira ticket {TICKET-KEY} for the PlexTrac workspace.

Ticket content:
{paste ticket details from /ticket output — title, description, acceptance criteria}

Your job:
1. Explore the codebase under {WORKSPACE}/{repo} to understand the affected areas
2. Read affected files, trace call paths, understand current behavior
3. Identify touch points, risks, and potential approaches with tradeoffs
4. Write your findings to {WORKSPACE}/notes/{TICKET-KEY}/research.md with:
   - Ticket summary (title, goal, acceptance criteria)
   - Affected areas (files, modules, services) with brief description
   - How relevant code currently works
   - Potential approaches with tradeoffs
   - Open questions or unknowns
5. Return a 2-3 paragraph summary of your findings to me
```

**→ Save to progress.md**: `Research complete. Findings in research.md. Summary: {1-2 sentences}`

---

## Step 2: Plan with user (main context)

Planning **stays in main context** because it requires user interaction.

- **If `notes/{TICKET-KEY}/plan.md` already exists**: read it, summarize to user, confirm whether to proceed or revise.
- **Otherwise**: From `research.md` summary, **suggest**:
  - **Approach**: What to build or fix, and in which repo/area
  - **Steps**: Ordered implementation steps, each specific enough for a sub-agent
- **User confirms** or adjusts before proceeding.
- Write the approved plan to `{WORKSPACE}/notes/{TICKET-KEY}/plan.md`:
  - Chosen approach and rationale
  - Ordered implementation steps, each with:
    - **Exact file path(s)** for each change
    - **Code snippets** showing the before/after or the specific lines to add/modify
    - A clear "done when" condition
  - Acceptance criteria checklist
  - Any deferred ideas or out-of-scope notes

**→ Save to progress.md**: `Plan approved. {N} implementation steps. Approach: {1 sentence}`

---

## Step 3: Create branch (main context)

- **Standard**: `{issue-key}-{short-kebab-description}` (e.g. `IO-2097-add-usage-metrics`). Details in [reference/branch-naming.md](../reference/branch-naming.md).
- Branch from default (e.g. `main`). Confirm the branch name with the user if ambiguous.

**→ Save to progress.md**: `Branch created: {branch-name}`

---

## Step 4: Execute (sub-agents)

### Verification Loop — CRITICAL

**Every time code changes — after implementation, after tests, after fixes — run verification before proceeding.** Use the `/verify` skill which auto-detects the repo type.

**Max 3 fix cycles per verification failure.** If still failing after 3 attempts, STOP and ask the user. Do not loop forever.

```
Implement → Verify → Test → Verify → Review → Fix → Verify → Commit
            ▲ fail              ▲ fail           ▲ fail
            └─ fix ─┘           └─ fix ─┘        └─ fix ─┘
           (max 3x)            (max 3x)          (max 3x)
```

### Pre-dispatch save — MANDATORY

**Before launching ANY sub-agent, SYNCHRONOUSLY save to progress.md.** This is a crash recovery point. If the session dies during a sub-agent run, the next session knows exactly where things stopped.

```
## {timestamp}
Dispatching: {agent type} for {description}
Plan steps: {which steps}
Files in scope: {list}
```

### 4a. Implementation sub-agent(s)

Launch one sub-agent per logical chunk of the plan (or one for the whole plan if small).

```
You are implementing ticket {TICKET-KEY} in {WORKSPACE}/{repo} on branch {branch}.

Plan:
{paste relevant plan steps from plan.md}

Standards:
- Follow CLAUDE.md rules for {repo} (read it first)
- TypeScript: no `as any`, no `as unknown as T`, use Pick for narrowing
- Python: type hints, f-strings, SOLID principles
- Follow existing patterns in the codebase

Implement the changes described in the plan. When done, return:
- List of files changed with a one-line description of each change
- Any questions or ambiguities you encountered
```

**→ Run verification. Fix failures (max 3 cycles).**
**→ Save to progress.md**: `Implementation complete. Files changed: {list}. Verification: {pass/fail}`

### 4b. Test sub-agent

```
You are writing tests for ticket {TICKET-KEY} in {WORKSPACE}/{repo} on branch {branch}.

Files changed:
{list from implementation agent}

Plan:
{paste test-relevant plan steps}

Standards:
- Follow CLAUDE.md testing rules for {repo}
- Co-locate test files with source (.test.ts suffix for TS, test_*.py for Python)
- Cover: happy path, edge cases, error paths
- For backend: test service layer; controller tests optional
- Use existing test patterns in the codebase as reference

Write the tests. When done, return:
- List of test files created/modified
- Brief description of what each test covers
- Run the tests and report pass/fail
```

**→ Run verification. Fix failures (max 3 cycles).**
**→ Save to progress.md**: `Tests written. Files: {list}. Coverage: {description}. Verification: {pass/fail}`

### 4c. Code review sub-agent — MANDATORY

**GATE: You MUST run the code review sub-agent after implementation and tests are written. Do not skip this step, even for small changes, any repo, or when resuming a session. If you are about to commit or create a PR and review was not run, STOP and run it now.**

Use the **Everything Claude Code** reviewer agents, matched to the repo language:

| Repo | Agent |
|------|-------|
| `product-core-backend` | `everything-claude-code:typescript-reviewer` |
| `product-core-frontend` | `everything-claude-code:typescript-reviewer` |
| `product-services-export` | `everything-claude-code:python-reviewer` |
| `product-services-mcp` | `everything-claude-code:python-reviewer` |
| Mixed / unknown | `everything-claude-code:code-reviewer` |

```
Review the changes for ticket {TICKET-KEY} in {WORKSPACE}/{repo} on branch {branch}.

Plan: {WORKSPACE}/notes/{TICKET-KEY}/plan.md

Review against:
- The plan's acceptance criteria
- CLAUDE.md standards for {repo}
- Code review best practices

Return only actionable findings. For each finding:
- File and line number
- What's wrong
- Suggested fix
```

**→ Save to progress.md**: `Review complete. Findings: {N actionable items}` (or `Review clean — no findings.`)

### 4d. Fix sub-agent (if review has findings)

```
You are fixing code review findings for ticket {TICKET-KEY} in {WORKSPACE}/{repo} on branch {branch}.

Findings to fix:
{paste findings from review agent}

Fix each finding. Return:
- List of fixes applied
- Any findings you chose to defer and why
```

**→ Run verification. Fix failures (max 3 cycles).**
**→ Save to progress.md**: `Review findings fixed. {N} applied, {N} deferred.`

### 4e. Final verification sub-agent

```
You are verifying ticket {TICKET-KEY} changes in {WORKSPACE}/{repo} on branch {branch}.

Run the /verify checks for this repo and report pass/fail for each.
Return the exit code and any failure output for each check.
Do NOT fix anything — just report.
```

**→ Save to progress.md**: `Final verification: {pass/fail for each check}`

---

## Step 5: Commit (main context)

### Commit Gate — ALL must be true

Before committing, verify this checklist. **Do not skip any item.**

- [ ] Code review agent (4c) ran
- [ ] Review findings fixed or explicitly deferred (4d)
- [ ] Verification passed AFTER the most recent code change
- [ ] All plan steps are implemented
- [ ] No outstanding questions or ambiguities

If resuming a session where code was already committed but review was not run, run the review NOW before proceeding to PR.

**Show the checklist to the user before committing:**
```
## Commit Gate — {TICKET-KEY}

- [x] Code review: ran, {N} findings → all fixed
- [x] Verification: lint ✓, typecheck ✓, tests ✓
- [x] Plan steps: {N}/{N} complete
- [x] No outstanding questions

Ready to commit: `{TICKET-KEY}: {short description}`
```

- Stage the relevant files and commit with message: `{TICKET-KEY}: short description`
- **Never run `git push`.** Remind the user: "Branch is committed; push when ready."

**→ Save to progress.md**: `Committed: {hash} — {TICKET-KEY}: {description}`

---

## Step 6: Handoff (main context)

Present a summary:

```
## {TICKET-KEY} — Complete

**Branch**: `{branch-name}`
**Commit**: `{hash}` — {message}
**Files changed**: {count}
{brief list of changed files}

**Tests**: {count} added/modified
**Review**: Clean (or: {N} findings fixed, {N} deferred)
**Verification**: All passing
```

Then ask the user: **"Ready to create a PR? I can use `/create-pr` to push the branch and open a PR with the repo's template filled out."**

- If yes → invoke `/create-pr` which handles push, template, draft approval, and PR creation
- If no → remind them: `git push -u origin {branch-name}` when ready

**→ Save to progress.md**: `Handoff complete. Branch ready for push and PR.` (or `PR created: {url}`)

---

## "Save our work" / Save progress

When the user says **"save our work"**, **"save progress"**, **"let's save"**, **"save what we've done"**, or similar:

1. Identify the current ticket key (from context or ask if unknown)
2. Write/append to `{WORKSPACE}/notes/{TICKET-KEY}/progress.md`:
   - Timestamp and session summary
   - What was completed in this session
   - Key decisions made and why
   - Files changed (brief list)
   - Current step in the workflow
   - What remains to be done
   - Any gotchas or context future-you should know
3. If `plan.md` needs updating (approach changed during implementation), update it
4. Offer to commit if there are uncommitted changes

---

## Parallel opportunities

**Can parallelize:**
- Independent plan step implementations (different files/modules)
- Tests for completed code while implementing next chunk
- Research sub-agent + Jira fetch (if doing both)

**Must be sequential:**
- Research → Plan (need findings to plan)
- Plan → Branch → Implement (need plan, need branch)
- Implement → **Verify** → Test (verify before writing tests)
- Test → **Verify** → Review (verify tests pass before review)
- Review → Fix (need findings to fix)
- Fix → **Verify** → Commit (verify fixes before committing)

---

## References

- **Branch naming**: [reference/branch-naming.md](../reference/branch-naming.md)
- **Full workflow details**: [reference/workflow.md](../reference/workflow.md)
- **Implementation standards**: Follow CLAUDE.md rules for each repo
- **Code review**: Everything Claude Code `typescript-reviewer` / `python-reviewer` / `code-reviewer` agents

## Team Tools (from plextrac agent-skills plugin)

These commands are provided by the team plugin and used by this workflow:

| Command | Used in | Purpose |
|---------|---------|---------|
| `/ticket` | Step 1 | Fetch Jira ticket details |
| `/verify` | Step 4 (all verification loops) | Lint, typecheck, tests |
| `/create-pr` | Step 6 | Push branch + create PR with template |
| `/logs` | Debugging during implementation | View service logs |
