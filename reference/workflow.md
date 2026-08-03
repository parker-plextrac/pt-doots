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

## Language Detection & Conventions-Overlay Injection

The implementer, test-writer, and the language-sensitive reviewers (code-reviewer, code-smells-reviewer, test-reviewer, edge-case-qa) are language-neutral skeletons. Their language-specific rules come from a **conventions overlay** the orchestrator loads by detecting the changed code's language and names in each spawn prompt. This section is the **single source of truth** for that detection and injection — `commands/prs.md` (Step 3, Step S6) and `reference/agent-prompts.md` both reference it. Do not re-specify the rule anywhere else.

**When:** compute `LANG` once the changed-file list is known — in the ticket flow that is after Step 4a (the implementer reports its changed files), just before the Step 4c quality gate; in `/prs` it is after `get_pull_request_files`.

### Detect `LANG`

From the changed-file list (skip test fixtures and binaries):

1. **By extension:** any `.ts` / `.tsx` / `.js` / `.jsx` ⇒ TypeScript; any `.py` ⇒ Python.
2. **Repo-marker confirm / tiebreak:** `product-core-backend`, `product-core-frontend` ⇒ TypeScript; `product-services-export`, `product-services-mcp`, `zenith-inbound-service` ⇒ Python.
3. **Mixed** (both a TypeScript/JS extension **and** `.py` are present) ⇒ `LANG = mixed`.

### Overlay path(s) per `LANG`

| `LANG` | Overlay path(s) to inject |
|--------|---------------------------|
| TypeScript | `/Users/parker/workspaces/plextrac/pt-doots/reference/typescript-conventions.md` |
| Python | `/Users/parker/workspaces/plextrac/pt-doots/reference/python-conventions.md` |
| mixed | **both** of the above |

### Injection block (add to each writer / language-sensitive-reviewer spawn prompt)

Fill `{CONVENTIONS_OVERLAY}` with the path(s) resolved above, then add this block to the prompt:

    Conventions overlay: {CONVENTIONS_OVERLAY}
    Read and apply it. The target repo's own committed CLAUDE.md is authoritative over the overlay — read it first and defer to it; the overlay is the baseline.

For `LANG = mixed`, list **both** paths on the `Conventions overlay:` line and append: "Each file follows its own language's overlay — apply the TypeScript rules to `.ts`/`.js` files and the Python rules to `.py` files."

**Gets the block:** implementer, test-writer, code-reviewer, code-smells-reviewer, test-reviewer, edge-case-qa.
**Takes no block** (language-neutral — reasons about ticket criteria, leaks, or runtime behavior, not language conventions): acceptance-qa, self-containment-reviewer, repro-verifier, researcher, documentarian.

**Adding a language later** = add its `<lang>-conventions.md` overlay file and one row to the table above. Zero agent or spawn-template edits.

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
   **Done when**: {done-condition echoed from progress.md; the anchor for the rest of the run}
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
   - "Done when" condition (per step)
3. **Derive the ticket-level Done-condition.** This is distinct from the per-step "Done when" above. It is ONE short, explicit statement of what makes the WHOLE ticket done, read straight off the ticket's acceptance criteria (or, for defects with an empty description, off the Bug Description / customfield_10227 expected-behavior). Keep it lightweight: a short bulleted "Done when:" block, not a spec. This is the single condition acceptance-qa evaluates at Step 4c and the Commit Gate checks.
4. User confirms the plan AND the Done-condition, or adjusts
5. Write the approved plan and the "Done when:" block to `plan.md`. Echo the same "Done when:" block into `progress.md` (Step 2 entry) so a post-/clear resume re-anchors on it. `plan.md` is canonical; the `progress.md` copy is a pointer.

**Done-condition format** (top of `plan.md`, echoed to `progress.md`):

    ## Done when:
    - {criterion 1: observable and testable}
    - {criterion 2}
    - Verification green (lint + typecheck + tests)

**Scale-down for lightweight and docs-only:** collapse the Done-condition to ONE line. For example "Done when: dependency bumped to X.Y and verify green", or "Done when: README section Y documents the new flag and code-reviewer is clean". Do not manufacture a multi-bullet block when the ticket has a single observable outcome. Note that acceptance-qa does not run on these two workflows, so their Done-condition is evaluated by code-reviewer plus the Commit Gate rather than by acceptance-qa.

**Save to progress.md**: `Plan approved. {N} steps. Approach: {1 sentence}. Done when: {1-line restatement or bulleted block}`

---

## Step 3: Create Branch (main context)

- Format: `{issue-key}-{short-kebab-description}` — see [branch-naming.md](branch-naming.md)
- Branch from default (e.g. `main`). Confirm name if ambiguous.
- **Create AND check out** in the same step: `cd {WORKSPACE}/{repo} && git switch -c {branch}`. The parent repo MUST be on the feature branch when Step 4a spawns the implementer, otherwise the implementer's patch-apply step lands the commit on whatever was previously checked out (commonly `main`). The `pt-doots:implementer` agent's `git switch "$BRANCH"` defensive check will fail-fast if this step is skipped, but the cleanest path is for the orchestrator to switch first and the implementer to verify.
- If the branch already exists locally (e.g., fix-cycle resuming from a prior session): `git switch {branch}` (no `-c`). Confirm with the user before reusing a branch that has commits not in `origin/main`.

**Save to progress.md**: `Branch created: {branch-name}` (or `Branch resumed: {branch-name}` for an existing branch)

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

**Soft cross-loop budget.** The max-3 cap above is per failure. Also watch the running total across 4a/4b/4d. If total fix-cycles across those three steps exceeds roughly 8, STOP and reassess with the user even if no single failure hit the max-3 cap. A ticket that needs that many fix cycles usually has a plan or scope problem, not a code problem. Track the current total on the `**Run tally**` line in `progress.md`. Live token and turn metering is intentionally left to the harness (for example `/goal`) and is not estimated here.

### 4a. Implementation (`pt-doots:implementer`)

- Spawn with the **Implementer Prompt (Implementation)** from [agent-prompts.md](agent-prompts.md)
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

**Conventions overlay (all variants):** before spawning, detect `LANG` from the implementer's changed-file list and inject the matching conventions-overlay path into each language-sensitive reviewer's prompt (code-reviewer, code-smells-reviewer, test-reviewer, edge-case-qa) — see the **Language Detection & Conventions-Overlay Injection** section. The language-neutral acceptance-qa takes no overlay.

Consolidate all findings from all reviewers before proceeding. FIRST clear the completion barrier: every dispatched reviewer must have returned a REAL result, not a truncated or empty completion notification. Retrieve any thin result via SendMessage (see [swarm-coordination.md](swarm-coordination.md) "Completion barrier") before consolidating. Do NOT consolidate a partial set.

**Save to progress.md**: `Quality gate complete. Code Review: {N}. Acceptance QA: {pass/fail or skipped}. Edge Case QA: {N or skipped}. Code Smells: {N}. Test Review: {N or skipped}.`

### 4d. Fix Findings (`pt-doots:implementer`, fix-cycle mode)

Only if quality gate has actionable findings.

- Spawn with the **Implementer Prompt (QA Fixes)** from [agent-prompts.md](agent-prompts.md)
- Pass consolidated findings from all reviewers
- Returns: fixes applied + any deferred
- **Run `/verify`. Fix failures (max 3 cycles).**

**Save to progress.md**: `Findings fixed. {N} applied, {N} deferred. Verification: {pass/fail}`

### 4e. Documentation (`pt-doots:documentarian`)

Spawn whenever the scrum-master returns `Documentation: yes` (the default polarity — the scrum-master only sets `no` when the ticket has zero documentation surface, e.g. a pure refactor with no behavior change). Always spawn when the workflow type is `docs-only`.

The documentarian walks its priority order:
1. **Nested CLAUDE.md** files in changed directories — verify they still match reality, fix stale claims, create one for directories whose shape meaningfully changed.
2. **Repo READMEs** — update setup/run/config/API sections affected by the change.
3. **Inline JSDoc/docstrings** — add or refresh doc comments on new or modified public surfaces.
4. **Confluence** — only when the spawn prompt or workflow plan explicitly names a Confluence target (or the ticket is cross-team-visible). Writes always require user approval via `[CONFLUENCE]` sections.

The agent does not skip a higher-priority level just because work exists at a lower one.

- Spawn with the **Documentarian Prompt** from [agent-prompts.md](agent-prompts.md)
- Returns: files updated + any Confluence suggestions
- Present Confluence suggestions to user for approval before acting

**Save to progress.md**: `Documentation updated. Files: {list}`

---

## Step 5: Commit (main context)

### Commit Gate — ALL must be true:
- [ ] Quality gate ran (4c), and all reviewers returned a REAL result (no truncated or empty completion notifications; any thin ones retrieved via SendMessage before consolidating)
- [ ] Findings fixed or deferred (4d)
- [ ] Verification passed after most recent code change
- [ ] All plan steps implemented
- [ ] Done-condition met (the "Done when:" block from plan.md; verified by acceptance-qa on standard, or by code-reviewer plus the orchestrator on lightweight/docs-only where acceptance-qa is skipped)
- [ ] No outstanding [GOVERNANCE] items unaddressed

Show checklist to user before committing:
```
## Commit Gate — {TICKET-KEY}

- [x] Quality gate: ran, {N} total findings → {N} fixed, {N} deferred
- [x] Verification: lint ✓, typecheck ✓, tests ✓
- [x] Plan steps: {N}/{N} complete
- [x] Done-condition: MET ({1-line restatement})
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

**Multi-item / multi-wave swarms:** see [swarm-coordination.md](swarm-coordination.md) for concurrency caps, worktree isolation, `.worktreeinclude` for env copying, sub-agents vs agent teams, and the wave-based pattern for production backlog burndowns.

---

## Telemetry

Run-level metrics (per-agent and per-workflow) are recorded under `$STATE/.local/` (where `$STATE` = `${HOME}/.claude/pt-doots`, the home-anchored state dir) after every spawn and at workflow completion. The contract — when to write, what to write, and how to initialize the files — lives in [`commands/pt-doots.md` § Telemetry](../commands/pt-doots.md#telemetry). The schema for both files lives in [metrics-format.md](metrics-format.md). Do not duplicate the contract here; `pt-doots.md` is the source of truth.

---

## References

- Branch naming: [branch-naming.md](branch-naming.md)
- Agent spawn prompts: [agent-prompts.md](agent-prompts.md)
- Progress log format: [progress-format.md](progress-format.md)
- Metrics schema: [metrics-format.md](metrics-format.md)
- Multi-item / multi-wave swarms: [swarm-coordination.md](swarm-coordination.md)
- Telemetry contract: [../commands/pt-doots.md](../commands/pt-doots.md) § Telemetry
