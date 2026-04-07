---
name: new-integration
description: Add a new EM integration to product-core-backend. Orchestrates sub-agents for research, implementation, testing, linting, typechecking, and code review. Handles both Synqly-proxied and direct-SDK integrations.
---

# New Integration

Add a new Exposure Management integration to `product-core-backend` using **sub-agents to preserve main context**. The orchestrator holds the plan and talks to the user; heavy work stays in sub-agents.

## Workspace detection

Detect the workspace root automatically from the current working directory — walk up from cwd until you find a directory containing PlexTrac product repos (e.g. `product-core-backend`, `product-core-frontend`). Store this as `{WORKSPACE}` for the session. All paths below use `{WORKSPACE}` as a placeholder for this resolved value.

**Workspace**: `{WORKSPACE}/product-core-backend`

**Notes folder**: Each ticket gets a folder at `{WORKSPACE}/notes/{TICKET-KEY}/` with:
- `research.md` — codebase exploration findings
- `plan.md` — the agreed implementation plan
- `progress.md` — running log of what was done; updated on "save our work"

## Arguments

`$ARGUMENTS` = integration name (e.g. `rapid7`, `wiz`, `crowdstrike`)

---

## Sub-Agent Architecture

| Agent | Type | subagent_type | Reads | Writes | Returns to main |
|-------|------|---------------|-------|--------|-----------------|
| **Research** | read-only | `Explore` | Codebase files | `research.md` | Summary of findings |
| **Implement** | writes code | `general-purpose` | `plan.md`, source files | Source code | Files changed + descriptions |
| **Test** | writes code | `general-purpose` | Changed files, existing tests | Test files | Tests added + pass/fail |
| **Review** | read-only | `everything-claude-code:typescript-reviewer` | All changed files, `plan.md` | Nothing | Actionable findings only |
| **Fix** | writes code | `general-purpose` | Review findings, source files | Source fixes | Fixes applied |
| **Verify** | read-only | `general-purpose` | Changed files | Nothing | Pass/fail for lint, typecheck, tests |

### Rules for sub-agents
- Each sub-agent gets a **self-contained prompt** with everything it needs — file paths, plan steps, standards to follow.
- Sub-agents **do not talk to the user**. Only the orchestrator talks to the user.
- If a sub-agent encounters ambiguity, it returns the question to the orchestrator, which asks the user.
- Launch **parallel sub-agents** when steps are independent.

---

## Step 0: Gather Context (orchestrator)

1. **Ticket key** — ask if not provided (e.g. `IO-2131`)
2. **Integration name** — from `$ARGUMENTS`
3. **Fetch ticket from Jira** (MCP) in main context — get title, description, acceptance criteria
4. **Check existing state** — read `notes/{TICKET-KEY}/research.md` and `plan.md` if they exist
   - If both exist: summarize to user, confirm whether to proceed or revise → skip to Step 3
   - If research exists but no plan: skip to Step 2
   - If neither exists: proceed to Step 1

---

## Step 1: Research (sub-agent)

Launch an **Explore** sub-agent to understand the current integration pattern.

```
You are researching how integrations are built in {WORKSPACE}/product-core-backend.

Ticket: {TICKET-KEY} — {ticket title and description from Jira}

CONTEXT: The "Synqly Integration Developer Guide" on Confluence (IN space) documents the full Synqly architecture — OCSF data flavors (Vulnerability vs AppSec vs Asset), plugin architecture, field mappings, provider configs, and token management. The orchestrator has this context; use it to inform your research rather than rediscovering it.

1. Read these files to understand the CURRENT pattern:
   - libs/common/src/integration-worker/api-integration/plugins/factory.ts
   - libs/common/src/integration-worker/api-integration/data/types.ts (ApiIntegrationKindEnum, Settings, Secrets)
   - libs/common/src/integration-worker/api-integration/synqly/types.ts (provider configs)
   - libs/common/src/integration-worker/constants.ts (license + feature flag maps)
   - apps/integration-worker/src/modules/metrics.ts (KIND_DISPLAY_NAMES)

2. Find an existing Synqly-based integration (e.g. qualys, snyk) and read ALL its files:
   - plugins/{name}/types.ts (Zod schemas)
   - plugins/{name}/util.ts (parse utility)
   - The factory build method for it

3. Check whether {INTEGRATION_NAME} already has:
   - An enum entry in ApiIntegrationKindEnum
   - A stub in the factory (DevelopmentApiIntegrationPlugin)
   - License constant and feature flag entries
   - A display name in metrics.ts

4. Write findings to {WORKSPACE}/notes/{TICKET-KEY}/research.md with:
   - Ticket summary (title, goal, acceptance criteria)
   - Affected areas (files, modules) with brief descriptions
   - How the current integration pattern works
   - What already exists vs what needs to be created
   - The reference integration used as template
   - Open questions or unknowns

5. Return a 2-3 paragraph summary of your findings to me

Return:
- Which files need to be CREATED vs MODIFIED
- What already exists for this integration
- The reference integration you used as a template (and which files)
- Any questions about auth type or provider config
```

---

## Step 2: Plan with User (orchestrator)

Planning **stays in main context** because it requires user interaction.

Present a plan based on research findings. **Key decisions to confirm with the user:**

### Decision: Integration Type
- **Synqly-proxied** (most common) — reuses SynqlyVulnerabilityPlugin or SynqlyAppSecPlugin
- **Direct SDK** — custom plugin class with its own API client

### Decision: Auth Type
- **Token** (API key) — e.g. Rapid7, Tenable
- **Basic** (username + password/secret) — e.g. Qualys
- **OAuth/Client credentials** — e.g. Defender
- **Custom** — unique credential shape

### Decision: Credential Fields
- What settings does the user configure? (apiUrl, region, org ID, etc.)
- What secrets are stored? (apiSecret, apiKey, etc.)
- What is the Synqly provider type string? (check https://docs.synqly.com/api-reference/management/integrations/integrations_list.md)

### Checklist (adapt based on research)
Files to **create**:
- [ ] `plugins/{name}/types.ts` — Zod schemas for settings + secrets
- [ ] `plugins/{name}/util.ts` — Parse utility class

Files to **modify**:
- [ ] `synqly/types.ts` — Add provider config type to union
- [ ] `plugins/factory.ts` — Replace stub with real build method
- [ ] (if needed) `data/types.ts` — Add enum entry
- [ ] (if needed) `constants.ts` — Add license + feature flag map entries
- [ ] (if needed) `metrics.ts` — Add display name
- [ ] (if needed) `features.ts` — Add feature flag
- [ ] (if needed) `license.ts` — Add license constant

Files to **create** (tests):
- [ ] `plugins/factory.test.ts` — Factory wiring tests (or add to existing)

**User confirms** or adjusts before proceeding.

Write the approved plan to `{WORKSPACE}/notes/{TICKET-KEY}/plan.md` with:
- Chosen approach and rationale
- Ordered implementation steps, each with:
  - **Exact file path(s)** for each change
  - **Code snippets** showing the before/after or specific lines to add/modify
  - A clear "done when" condition
- Acceptance criteria checklist
- Any deferred ideas or out-of-scope notes

---

## Step 3: Create Branch (orchestrator)

Branch from `main`: `{TICKET-KEY}-{integration-name}-synqly-integration`

> **Note:** The `-synqly-integration` suffix is the convention specifically for integration tickets. The general branch naming pattern (`{TICKET-KEY}-{short-kebab-description}`) from [reference/branch-naming.md](../reference/branch-naming.md) still applies — integration branches just use this more descriptive suffix to distinguish them.

Follow branch naming from [reference/branch-naming.md](../reference/branch-naming.md). Confirm name with user if ambiguous.

---

## Step 4: Implement (sub-agents)

### Verification Loop — CRITICAL

**Every time code changes — after implementation, after tests, after fixes — you MUST run the verification checks before proceeding to the next step.** This is not optional. Skipping this wastes resources and time when errors compound.

```
Verification checks (run after EVERY code change):
1. npx eslint {list of changed files}
2. npm run typecheck (tsc --noEmit)
3. NODE_ENV=development LOG_LEVEL=error npx mocha --config .mocharc.apps-libs.js '{test file path}'
```

If any check fails, fix the issue and re-run ALL checks before moving on. The flow is:

```
Implement → Verify → Test → Verify → Review → Fix → Verify → Commit
            ^ fail              ^ fail           ^ fail
            └─ fix ─┘           └─ fix ─┘        └─ fix ─┘
```

### 4a. Implementation Agent

```
You are implementing a new {INTEGRATION_NAME} integration in {WORKSPACE}/product-core-backend on branch {BRANCH}.

Plan: {WORKSPACE}/notes/{TICKET-KEY}/plan.md

Reference implementation to follow: {REFERENCE_INTEGRATION} (e.g. qualys, snyk)

Context: The "Synqly Integration Developer Guide" on Confluence (IN space) documents OCSF data flavors, plugin architecture, field mappings, provider configs, and token management. Use it to understand which plugin type to use (SynqlyVulnerabilityPlugin vs SynqlyAppSecPlugin) and how provider configs are structured.

Standards:
- Read CLAUDE.md for product-core-backend rules
- TypeScript: no `as any`, no `as unknown as T`, use Pick for narrowing
- Zod: use `z.strictObject` for schema definitions
- Follow the EXACT pattern of the reference integration
- Follow existing patterns in the codebase

Implement all changes from the plan. Return:
- List of files created/modified with one-line description each
- Any questions or ambiguities
```

**→ Run verification checks on all changed files. Fix any failures before proceeding.**

### 4b. Test Agent

```
You are writing tests for the {INTEGRATION_NAME} integration in {WORKSPACE}/product-core-backend on branch {BRANCH}.

Files changed: {list from implementation agent}

Write factory tests following the pattern in plugins/factory.test.ts (if it exists) or add to it.
Tests should cover:
- Plugin creation with valid settings/secrets returns correct plugin type
- SynqlyDisabledError when Synqly is not enabled
- Zod validation rejects missing required fields
- Zod strictObject rejects unexpected fields
- Sentinel parsing (null and provided)
- Factory routing (createPlugin dispatches to correct build method)

Standards:
- Follow CLAUDE.md testing rules for product-core-backend
- Co-locate test files with source (.test.ts suffix)
- Cover: happy path, edge cases, error paths
- Use existing test patterns in the codebase as reference
- Use proper enum types (e.g. IntegrationSyncFrequency.Daily, not string literals)

Use: Mocha + Chai + moq.ts (the project's test stack)
Run: NODE_ENV=development LOG_LEVEL=error npx mocha --config .mocharc.apps-libs.js '{test file path}'

Return: test file path, test names, pass/fail results
```

**→ Run verification checks on ALL changed files (including new test files). Fix any failures before proceeding.**

### 4c. Code Review Agent — MANDATORY

**GATE: You MUST run the code review sub-agent after implementation and tests are written AND verification passes. Do not skip this step, even for small changes. If you are about to commit or create a PR and review was not run, STOP and run it now.**

Use `subagent_type: "everything-claude-code:typescript-reviewer"`.

```
Review the changes for ticket {TICKET-KEY} in {WORKSPACE}/product-core-backend on branch {BRANCH}.

Plan: {WORKSPACE}/notes/{TICKET-KEY}/plan.md

Review against:
- The plan's acceptance criteria
- CLAUDE.md standards for product-core-backend
- The reference integration pattern (consistency)
- Correct credential type and Synqly provider string
- Code review best practices

Return only actionable findings. For each finding:
- File and line number
- What's wrong
- Suggested fix
```

### 4d. Fix Agent (if review has findings)

```
You are fixing code review findings for ticket {TICKET-KEY} in {WORKSPACE}/product-core-backend on branch {BRANCH}.

Findings to fix:
{paste findings from review agent}

Fix each finding. Return:
- List of fixes applied
- Any findings you chose to defer and why
```

**→ Run verification checks AGAIN on all changed files. Fix any failures before committing.**

---

## Step 5: Commit (orchestrator)

**GATE: Do NOT commit unless ALL of these are true:**
1. Code review agent (4c) ran and approved (or findings were fixed)
2. Verification checks (eslint, typecheck, tests) passed AFTER the most recent code change
3. No outstanding fix needed

If resuming a session where code was already committed but review was not run, run the review NOW before proceeding to PR.

- Stage the relevant files and commit with message: `{TICKET-KEY}: wire up {Integration Name} Synqly integration`
- **Never run `git push`.** Remind the user: "Branch is committed; push when ready."

---

## Step 6: Handoff (orchestrator)

- **Summary**: What was implemented, which files changed, and what was tested.
- **Branch name** and **commit hash(es)**.
- **Manual test steps** for verifying the integration end-to-end.
- Suggested **PR title and body** (following BE PR template with Observability section).
- Reminder that the user should push the branch when ready.

---

## "Save our work" / Save progress

When the user says **"save our work"**, **"save progress"**, **"let's save"**, or similar:

1. Identify the current ticket key (from context or ask if unknown).
2. Append to `{WORKSPACE}/notes/{TICKET-KEY}/progress.md` (create if it doesn't exist):
   - Timestamp and session summary
   - What was completed in this session
   - Key decisions made and why
   - Files changed (brief list)
   - What remains to be done
   - Any gotchas or context future-you should know

---

## Parallel Opportunities

Independent (can run in parallel):
- Implementation of unrelated files (e.g. types.ts + factory.ts if no dependency)
- Tests can start once implementation is done

Sequential (must wait):
- Research → Plan (need findings to plan)
- Plan → Implement (need plan to implement)
- Implement → **Verify** → Test (verify implementation before writing tests)
- Test → **Verify** → Review (verify tests pass before review)
- Review → Fix (need findings to fix)
- Fix → **Verify** → Commit (verify fixes before committing)

---

## References

- **Synqly Developer Guide**: [Confluence — IN space](https://plextrac.atlassian.net/wiki/spaces/IN/pages/4762632195/Synqly+Integration+Developer+Guide) — OCSF data flavors, field mappings, plugin architecture, token management, sentinel sync, and how to add new integrations. Sub-agents should read this for Synqly context.
- **Architecture snapshot**: [reference/architecture-snapshot.md](../reference/architecture-snapshot.md)
- **Branch naming**: [reference/branch-naming.md](../reference/branch-naming.md)
- **Implementation standards**: typescript-principal-engineer skill
- **Code review**: Everything Claude Code `typescript-reviewer` agent
- **Synqly provider types**: https://docs.synqly.com/api-reference/management/integrations/integrations_list.md
