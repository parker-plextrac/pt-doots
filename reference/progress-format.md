# Progress Log Format

Each entry in `notes/{TICKET-KEY}/progress.md` follows this structure.

## Rules
- Always append, never overwrite previous entries
- New sessions get a new `## Session:` header
- Pre-dispatch entries use `### Dispatching:` prefix
- Keep each entry concise — this is a log, not documentation

## Template

```markdown
# {TICKET-KEY} Progress Log

## Session: {YYYY-MM-DD HH:MM}

### Step 0: Load Context
- Status: complete
- Resumed from: {previous session date, or "new ticket"}
- Branch: `{branch-name}` ({N} commits ahead of main)
- Workflow: {standard | lightweight | thorough} — {rationale}
- Execution mode: {standard | tdd}

### Step 1: Research
- Status: complete
- Agent: researcher ({model})
- Summary: {1-2 sentence summary of findings}

### Step 2: Plan
- Status: complete
- Approach: {1 sentence}
- Steps: {N} implementation steps
- Execution mode: {standard | tdd}

### Dispatching: {agent-name}
- Plan steps: {which steps}
- Files in scope: {list}

### Step 4a: Implementation
- Status: complete
- Agent: developer ({model})
- Files changed: {list with one-line descriptions}
- Verification: pass (or: fail → fixed in {N} cycles)
- Governance: {none | list of [GOVERNANCE] items found}

### Step 4b: Tests
- Status: complete
- Agent: test-writer ({model})
- Test files: {list}
- Verification: pass

### Step 4c: Quality Gate
- Status: complete
- Agents: code-reviewer, acceptance-qa, edge-case-qa (parallel)
- Code Review: {N} findings (or: clean)
- Acceptance QA: {N}/{N} criteria passed
- Edge Case QA: {N} scenarios flagged
- Governance: {none | list}

### Step 4d: Fix QA Findings
- Status: complete
- Agent: developer ({model})
- Fixed: {N}, Deferred: {N}
- Verification: pass

### Step 4e: Documentation
- Status: complete
- Agent: documentarian ({model})
- Files updated: {list}

### Step 5: Commit
- Status: complete
- Hash: `{short-hash}`
- Message: {TICKET-KEY}: {description}

### Step 6: Handoff
- Status: complete
- Branch ready for push and PR
```
