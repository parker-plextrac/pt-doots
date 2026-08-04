# Progress Log Format

Each entry in `notes/{TICKET-KEY}/progress.md` follows this structure.

## Rules
- Always append, never overwrite previous entries
- New sessions get a new `## Session:` header
- Pre-dispatch entries use `### Dispatching:` prefix
- Keep each entry concise — this is a log, not documentation
- The `**Run tally**` line under the session header is the one exception to append-only: refresh it in place after each fix-cycle or spawn so it always shows current totals

## Template

```markdown
# {TICKET-KEY} Progress Log

## Session: {YYYY-MM-DD HH:MM}

**Run tally**: fix-cycles used {N} of ~8 soft cross-loop budget (across 4a/4b/4d), agents spawned {N}. (Live token and turn metering is left to the harness, for example `/goal`, not tracked here.)

### Step 0: Load Context
- Status: complete
- Resumed from: {previous session date, or "new ticket"}
- Branch: `{branch-name}` ({N} commits ahead of main)
- Workflow: {standard | lightweight | docs-only | custom} — {rationale}
- Execution mode: {standard | tdd}

### Step 1: Research
- Status: complete
- Agent: researcher ({model})
- Summary: {1-2 sentence summary of findings}

### Step 2: Plan
- Status: complete
- Approach: {1 sentence}
- Done when: {the ticket-level done-condition: 1 line for lightweight/docs-only, or a short bulleted block for standard}
- Steps: {N} implementation steps
- Execution mode: {standard | tdd}

### Dispatching: {agent-name}
- Plan steps: {which steps}
- Files in scope: {list}

### Step 4a: Implementation
- Status: complete
- Agent: implementer ({model})
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
- Agents: code-reviewer, acceptance-qa, edge-case-qa, code-smells-reviewer, test-reviewer, self-containment-reviewer (parallel)
- Code Review: {N} findings (or: clean)
- Acceptance QA: {N}/{N} criteria passed
- Edge Case QA: {N} scenarios flagged
- Code Smells: {N} smells flagged
- Test Review: {N} findings
- Self-Containment: {N} leaks flagged
- Governance: {none | list}

### Step 4d: Fix QA Findings
- Status: complete
- Agent: implementer ({model})
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
