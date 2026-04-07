# pt-doots v2 — Design Spec

**Date:** 2026-04-07
**Status:** Draft
**Goal:** Refactor the pt-doots command from a 455-line monolith into a thin orchestrator that references docs, uses the pt-doots agent roster, and routes workflows dynamically.

---

## Problem

The current `commands/pt-doots.md` has three issues:

1. **Duplicates reference docs** — The command inlines ~455 lines of workflow detail that largely duplicate `reference/workflow.md` and `reference/agent-prompts.md`. Changes to one don't propagate to the other.
2. **Doesn't use its own agents** — The command spawns generic agents (`subagent_type: "Explore"`, `"general-purpose"`, `"everything-claude-code:typescript-reviewer"`) instead of the purpose-built `pt-doots:*` agents that have PlexTrac domain knowledge baked in.
3. **One-size-fits-all** — Every invocation runs the full workflow. There's no lightweight path for status checks, no dynamic routing based on ticket complexity.

---

## Design

### Command structure (~120 lines)

The command becomes a **routing and orchestration layer**. It knows:
- How to detect user intent (status check vs. save vs. tackle)
- How to load context from notes
- Which agents to spawn for each step
- Gate conditions (verification loops, commit checklist)

It does NOT contain:
- Detailed step-by-step instructions (→ `reference/workflow.md`)
- Agent spawn prompt templates (→ `reference/agent-prompts.md`)
- Progress log format (→ `reference/progress-format.md`)

### Three modes

The command detects intent from the user's message:

| Intent signal | Mode | What happens |
|---------------|------|-------------|
| "check on IO-2132", "status IO-2132", "where are we on IO-2132" | **Status check** | Read `notes/{TICKET-KEY}/`, display progress summary, done. No workflow. |
| "save our work", "save progress", "let's save" | **Save progress** | Write/append to `progress.md`, offer to commit. |
| "tackle IO-2132", "do IO-2097", "implement this ticket" | **Tackle ticket** | Full workflow with scrum-master routing. |

### Tackle ticket flow

```
Step 0:  Load Context          (main context — read notes, git state)
Step 0.5: Route Workflow       (spawn pt-doots:scrum-master → get recommendation)
Step 1:  Research              (spawn pt-doots:researcher)
Step 2:  Plan                  (main context — user interaction)
Step 3:  Create Branch         (main context)
Step 4a: Implement             (spawn pt-doots:developer)
         → Verify              (spawn /verify)
Step 4b: Write Tests           (spawn pt-doots:test-writer)
         → Verify              (spawn /verify)
Step 4c: Quality Gate          (spawn pt-doots:code-reviewer + acceptance-qa + edge-case-qa in parallel)
         → Optional: ECC       (spawn ECC reviewer if scrum-master recommended "thorough")
Step 4d: Fix Findings          (spawn pt-doots:developer in fix-cycle mode)
         → Verify              (spawn /verify)
Step 4e: Documentation         (spawn pt-doots:documentarian — optional, scrum-master decides)
Step 5:  Commit                (main context — commit gate checklist)
Step 6:  Handoff               (main context — summary, offer /create-pr)
```

### Scrum-master workflow routing

At Step 0.5, spawn `pt-doots:scrum-master` (haiku, 1 turn, near-zero cost) with the ticket summary. It returns a structured recommendation:

```
WORKFLOW RECOMMENDATION

Workflow: standard | lightweight | thorough
Agents: [list of agents to spawn and in what order]
Review depth: standard (pt-doots reviewers) | thorough (pt-doots + ECC second pass)
Documentation: yes | no
TDD: yes | no
Rationale: {why this workflow}
```

**Workflow types:**

| Type | When | What's different |
|------|------|-----------------|
| **lightweight** | Small bug fix, config change, single-file edit | Skip research (or minimal). Skip acceptance-qa and edge-case-qa. Single reviewer. |
| **standard** | Most tickets — feature work, multi-file changes | Full pipeline. pt-doots reviewers in parallel quality gate. |
| **thorough** | Complex/risky — migrations, multi-service, security-sensitive | Full pipeline + ECC reviewer second pass. Documentation step included. |

The orchestrator follows the scrum-master's recommendation but the user can override it.

### Agent mapping

Every step maps to a specific pt-doots agent:

| Step | Agent | Type | Why pt-doots over generic |
|------|-------|------|--------------------------|
| 0.5 | `pt-doots:scrum-master` | haiku, 1 turn | Knows PlexTrac ticket patterns, workflow types |
| 1 | `pt-doots:researcher` | sonnet, 20 turns | Knows 4-repo structure, parser routing, Confluence |
| 4a, 4d | `pt-doots:developer` | sonnet, 50 turns, worktree | CLAUDE.md standards, nested CLAUDE.md creation, layer rules |
| 4b | `pt-doots:test-writer` | sonnet, 30 turns, worktree | Repo-specific test frameworks (Mocha/Jest/pytest) |
| 4c | `pt-doots:code-reviewer` | sonnet, 15 turns | PlexTrac CLAUDE.md standards checklist |
| 4c | `pt-doots:acceptance-qa` | haiku, 10 turns | Acceptance criteria verification |
| 4c | `pt-doots:edge-case-qa` | sonnet, 15 turns | Boundary conditions, failure modes |
| 4c (thorough) | `everything-claude-code:typescript-reviewer` or `python-reviewer` | ECC agent | Broader industry patterns, async/security review |
| 4e | `pt-doots:documentarian` | sonnet | Docs updates, Confluence suggestions |

### What the command inlines vs. references

**Inlined in the command (~120 lines):**
- Trigger detection logic (status check / save / tackle)
- Status check mode (read notes, format output)
- Save progress mode (append to progress.md)
- Tackle ticket flow outline (step names + agent mappings)
- Gate conditions (verification loop: max 3 cycles, commit gate checklist)
- Notes folder convention (`{WORKSPACE}/notes/{TICKET-KEY}/`)
- Agent mapping table
- "Read reference/workflow.md for detailed step instructions"
- "Read reference/agent-prompts.md for spawn prompt templates"

**In reference docs (read by orchestrator as needed):**
- `reference/workflow.md` — Detailed step-by-step instructions for each step
- `reference/agent-prompts.md` — Full prompt templates for spawning each agent
- `reference/progress-format.md` — Progress log format specification
- `reference/branch-naming.md` — Branch naming convention

### Verification loop (inlined — short, critical)

```
After every code change → run /verify
Max 3 fix cycles per failure
If still failing after 3 → STOP, ask the user

Implement → Verify → Test → Verify → Review → Fix → Verify → Commit
```

### Commit gate (inlined — short, critical)

```
ALL must be true before committing:
- [ ] Quality gate ran (4c)
- [ ] Findings fixed or explicitly deferred (4d)
- [ ] Verification passed after most recent change
- [ ] All plan steps implemented
- [ ] No outstanding questions or [GOVERNANCE] items
```

### Pre-dispatch save (inlined — short, critical)

Before launching any sub-agent, synchronously save to `progress.md`:
```
### Dispatching: {agent type}
- Plan steps: {which steps}
- Files in scope: {list}
```

---

## Changes to reference/workflow.md

Update the existing workflow doc to become the single source of truth:

1. **Replace generic agent references** with `pt-doots:*` agents throughout
2. **Add Step 0.5** — Scrum-master routing
3. **Update Step 4c** — Parallel quality gate (code-reviewer + acceptance-qa + edge-case-qa) instead of single reviewer
4. **Add Step 4e** — Documentation step (optional, per scrum-master recommendation)
5. **Add workflow types** — Standard, lightweight, thorough
6. **Update progress format references** to match `reference/progress-format.md`
7. **Remove prompt templates** — Reference `agent-prompts.md` instead of duplicating

---

## Changes to reference/agent-prompts.md

Minimal changes — the prompt templates are already good:

1. **Remove `learned-patterns` references** — The `.local/team-manager/learned-patterns.md` pattern is aspirational but not implemented. Remove these placeholder lines to avoid confusion. Re-add when the team-manager actually produces this file.
2. **Ensure each prompt template names the `pt-doots:*` agent type** so the orchestrator knows which `subagent_type` to use when spawning.

---

## Changes to reference/progress-format.md

Already in good shape. One addition:

1. **Add `Workflow: {type}` to Step 0** — Record which workflow the scrum-master recommended so future sessions know the original routing decision.

---

## What does NOT change

- **Agent definitions** (`agents/*.md`) — These are already well-designed. No changes needed.
- **Other commands** (`prs.md`, `new-integration.md`, `bootstrap-team.md`, `team-audit.md`) — Unaffected.
- **Notes folder convention** — Same structure, same files.
- **Branch naming, commit format** — Unchanged.

---

## Migration

This is a breaking change to the command format (shorter, references docs). No migration needed since:
- The notes folder format is unchanged
- The progress.md format is backward-compatible (new fields are additive)
- The agents are unchanged
- Only the orchestrator behavior changes

---

## Token budget estimate

**Current command:** ~455 lines loaded into every session = ~2,000 tokens of context on every invocation, regardless of mode.

**v2 command:** ~120 lines loaded = ~500 tokens. Reference docs loaded only when needed (tackle ticket mode reads workflow.md + agent-prompts.md). Status check mode reads zero reference docs.

**Savings for status checks:** ~1,500 tokens per invocation (75% reduction).
**Savings for full workflow:** Modest — still needs to read reference docs, but they're loaded on-demand rather than always.

---

## Success criteria

1. Command is under 150 lines
2. Status check mode works without loading reference docs
3. Scrum-master routes to correct workflow type
4. All pt-doots agents are used (no generic/ECC agents except as second-pass reviewer)
5. reference/workflow.md is the single source of truth for step details
6. reference/agent-prompts.md is the single source of truth for spawn prompts
7. No duplicated content between command and reference docs
