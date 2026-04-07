# PlexTrac Ticket Workflow (Sub-Agent Architecture)

Sequential steps to complete a Jira ticket in the PlexTrac workspace. The main conversation is an **orchestrator** — it manages flow, talks to the user, and delegates heavy work to sub-agents to preserve context.

## Workspace detection

Detect the workspace root automatically from the current working directory — walk up from cwd until you find a directory containing PlexTrac product repos (e.g. `product-core-backend`, `product-core-frontend`). Store this as `{WORKSPACE}` for the session. All paths below use `{WORKSPACE}` as a placeholder for this resolved value.

## Context budget philosophy

Every file read, test output, and codebase exploration costs context. The orchestrator should hold:
- The plan (`plan.md`)
- Short summaries from each sub-agent
- User conversation

Everything else lives in sub-agent context and gets discarded after the summary is returned.

---

## Notes folder — Source of Truth

Each ticket gets a folder at `{WORKSPACE}/notes/{TICKET-KEY}/`:

| File | Purpose | Updated when |
|------|---------|--------------|
| `research.md` | Codebase findings, approaches, tradeoffs | Step 1 (research sub-agent) |
| `plan.md` | Agreed implementation plan | Step 2 (main context, with user) |
| `progress.md` | Running session journal — crash recovery | **After every step completion** |

**Incremental persistence**: `progress.md` is updated after EVERY step, not just on "save our work". This is crash recovery — if the session dies, the next session resumes from the last saved state.

**Pre-dispatch saves**: Before launching any sub-agent, SYNCHRONOUSLY save the current state to progress.md. This ensures that if a sub-agent crashes, the orchestrator knows what was being attempted.

At the start of a new session: read existing notes files first to restore context instead of re-exploring.

---

## 0. Load Context (main context)

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

---

## 1. Research (sub-agent)

**Check notes first** (main context): If `notes/{TICKET-KEY}/research.md` exists, read it and skip to Step 2.

**Otherwise**:
1. Fetch ticket from Jira in main context (MCP call — small payload, stays in main)
2. Launch **Research sub-agent** (`subagent_type: "Explore"`, thoroughness: "very thorough"):
   - Give it the ticket content
   - It explores the codebase, reads files, traces call paths
   - It writes `research.md` to the notes folder
   - It returns a 2-3 paragraph summary to main
3. Main context receives only the summary — all file reads stay in the sub-agent
4. **Save to progress.md**: research complete, summary

---

## 2. Plan with user (main context)

Stays in main because it requires user interaction.

1. From research summary, propose approach and steps
2. Each plan step should be **self-contained enough for a sub-agent** — include:
   - Exact file path(s)
   - What to change (code snippets or clear description)
   - "Done when" condition
3. User confirms or adjusts
4. Write approved plan to `plan.md`
5. **Save to progress.md**: plan approved

---

## 3. Create branch (main context)

- Follow [branch-naming.md](branch-naming.md): `{issue-key}-{short-kebab-description}`
- Branch from default (e.g. `main`). Confirm name if ambiguous.
- **Save to progress.md**: branch created

---

## 4. Execute (sub-agents, sequential)

### Verification loop

After every code change, run verification. **Max 3 fix cycles per failure.** If still failing after 3 attempts, stop and ask the user.

```
Implement → Verify → Test → Verify → Review → Fix → Verify → Commit
            ▲ fail              ▲ fail           ▲ fail
            └─ fix ─┘           └─ fix ─┘        └─ fix ─┘
           (max 3x)            (max 3x)          (max 3x)
```

### Pre-dispatch save

Before launching ANY sub-agent, synchronously save to progress.md what is about to happen, which plan steps, and which files are in scope. This is the crash recovery point.

### 4a. Implementation sub-agent(s)

- Launch one sub-agent per logical chunk, or one for the whole plan if small
- Give it: plan steps, repo path, branch name, CLAUDE.md standards
- It returns: list of files changed + one-line descriptions + any questions
- If it has questions → orchestrator asks the user → resumes or launches new agent with answers
- **Run verification. Fix failures (max 3 cycles).**
- **Save to progress.md**: implementation complete, files changed, verification status

**Parallel opportunity**: If plan has independent chunks, launch implementation agents in parallel.

### 4b. Test sub-agent

- Give it: list of changed files, plan, test standards from CLAUDE.md
- It writes tests, runs them, returns: test files created + pass/fail
- If tests fail: orchestrator can resume the agent or launch a fix agent
- **Run verification. Fix failures (max 3 cycles).**
- **Save to progress.md**: tests written, coverage, verification status

### 4c. Review sub-agent — MANDATORY

- Use **Everything Claude Code** reviewers matched to repo language:
  - TypeScript repos → `subagent_type: "everything-claude-code:typescript-reviewer"`
  - Python repos → `subagent_type: "everything-claude-code:python-reviewer"`
  - Mixed/unknown → `subagent_type: "everything-claude-code:code-reviewer"`
- Give it: repo path, branch, plan.md path
- It returns: actionable findings only (file, line, issue, suggested fix)
- **GATE**: Never skip this step, even for small changes or any repo
- **Save to progress.md**: review complete, number of findings

### 4d. Fix sub-agent (if review has findings)

- Give it: the review findings list
- It applies fixes, returns: what was fixed + what was deferred
- **Run verification. Fix failures (max 3 cycles).**
- **Save to progress.md**: findings fixed/deferred, verification status

### 4e. Final verification sub-agent

- Runs all checks, reports pass/fail for each
- **No fixes** — just reports
- **Save to progress.md**: final verification results

---

## 5. Commit (main context)

### Commit gate — ALL must be true:
- [ ] Code review ran (4c)
- [ ] Review findings fixed or deferred (4d)
- [ ] Verification passed after most recent code change
- [ ] All plan steps implemented
- [ ] No outstanding questions

Show the checklist to user before committing:
```
## Commit Gate — {TICKET-KEY}

- [x] Code review: ran, {N} findings → all fixed
- [x] Verification: lint ✓, typecheck ✓, tests ✓
- [x] Plan steps: {N}/{N} complete
- [x] No outstanding questions

Ready to commit: `{TICKET-KEY}: {short description}`
```

Stage relevant files, commit: `{TICKET-KEY}: short description`. **Never push.** Remind user to push.

**Save to progress.md**: committed, hash, message

---

## 6. Handoff (main context)

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

### Suggested PR
**Title**: {TICKET-KEY}: {short description}
**Description**: {2-3 sentence summary}

⚠️ Push when ready: `git push -u origin {branch-name}`
```

**Save to progress.md**: handoff complete

---

## "Save our work"

Triggered by: "save our work", "save progress", "let's save", etc.

1. Write/append to `{WORKSPACE}/notes/{TICKET-KEY}/progress.md`:
   - Date/session marker
   - What was completed
   - Key decisions and why
   - Files changed (brief list)
   - Current workflow step
   - What remains
   - Gotchas for future sessions
2. Update plan.md if approach changed during implementation
3. Offer to commit if uncommitted changes exist

---

## Sub-agent sequencing rules

**Can parallelize:**
- Independent plan step implementations
- Tests for completed code while implementing next chunk

**Must be sequential:**
- Research → Plan → Branch → Implement → Verify → Test → Verify → Review → Fix → Verify → Commit

---

## References

- Branch naming: [branch-naming.md](branch-naming.md)
- Jira fetch: jira-ticket-review skill
- Implementation: typescript-principal-engineer skill
- Code review: Everything Claude Code typescript-reviewer / python-reviewer / code-reviewer agents
