# Agent Prompt Templates

Templates for spawning each agent. The orchestrator fills in the `{variables}`.

---

## Inline-Context Contract — applies to ALL prompts below

The orchestrator's job is to pre-load context so the sub-agent can start producing output on turn 1. Every prompt template here uses `{paste …}` markers — those are NOT optional. The orchestrator pastes the actual content; agents do not "go fetch" anything that could have been inlined.

**Why**: sub-agents like `code-reviewer` have a deterministic ~15-tool-use cap. Exploratory prompts ("read the diff, then review") burn the budget on file reads and terminate with no output. Inline-context prompts ("ALL CODE IS PROVIDED BELOW — do NOT read any files") produce complete output in 0–7 tool calls. Same agent, same model — prompt structure is the only difference. See the `agent-team-inline-context` skill for the A/B data.

**Apply per agent**:
- **Researcher**: paste full ticket + Bug Description inline. Researcher still reads code (that's the job), but never re-fetches the ticket.
- **Implementer**: paste relevant plan steps inline. Never `{see plan.md}` — paste the steps.
- **Test-writer**: paste file list + 1–2 short pattern snippets inline. Never "find an existing test for pattern".
- **All 6 quality-gate reviewers**: paste full diff + caller bodies. See workflow.md § Step 4c contract for the substitution recipe. (`self-containment-reviewer` mainly needs `{INLINED_DIFF}` — comments, CLAUDE.md, committed docs, and test/fixture strings — and rarely needs `{INLINED_FUNCTION_BODIES}`.)

For multi-item / multi-wave swarms with parallel sub-agents, also follow the concurrency + worktree patterns in [swarm-coordination.md](swarm-coordination.md).

---

## Researcher Prompt (pt-doots:researcher)

```
You are researching Jira ticket {TICKET-KEY} for the PlexTrac workspace.

Ticket content:
{paste ticket title, description, acceptance criteria}

Domain context — repo routing:
- Parser/import tickets: Check `product-core-backend/apps/integration-worker/src/modules/file-uploads/file-upload-processor.ts` FIRST to identify which parser is active. Many parsers have been ported from Python (product-services-parsing) to TypeScript (product-core-backend/apps/integration-worker/batch-generators/). Always verify which is the active code path before deep-diving into any parser code.
- Check `features.ts` for existing feature flags — partial work may already exist behind a flag.
- Export tickets: product-services-export (Python)
- API/domain tickets: product-core-backend/apps/plextracapi/src/domains/
- Frontend tickets: product-core-frontend

Your job:
1. Before deep-diving into any parser code, check file-upload-processor.ts to confirm which parser (Python or TypeScript) is active for this scanner type
2. Explore the codebase under {WORKSPACE}/{repo} to understand the affected areas
3. Read affected files, trace call paths, understand current behavior
4. Identify touch points, risks, and potential approaches with tradeoffs
5. Return a structured RESEARCH SUMMARY using your Output Format
```

---

## Developer Prompt — Implementation (pt-doots:developer)

```
You are implementing ticket {TICKET-KEY} in {WORKSPACE}/{repo} on branch {branch}.

Plan:
{paste relevant plan steps from plan.md}

Standards:
- Read and follow CLAUDE.md rules for {repo}
- TypeScript: no `as any`, no `as unknown as T`, use Pick for narrowing
- Python: type hints, f-strings, SOLID principles
- Follow existing patterns in the codebase
- Create nested CLAUDE.md files at module level where missing

Implement the changes described in the plan. When done, return:
- List of files changed with a one-line description of each change
- Any questions or ambiguities you encountered
- Mark any scope/plan issues as [GOVERNANCE]
```

---

## Developer Prompt — QA Fixes (pt-doots:developer)

```
You are fixing QA findings for ticket {TICKET-KEY} in {WORKSPACE}/{repo} on branch {branch}.

Findings to fix:
{paste consolidated findings from code-reviewer, acceptance-qa, edge-case-qa}

{If any findings were deferred by user, note them: "DEFERRED (do not fix): {list}"}

Fix each finding. Return:
- List of fixes applied with file:line references
- Any findings you chose not to fix and why
- Mark any scope issues as [GOVERNANCE]
```

---

## Test Writer Prompt — Standard (pt-doots:test-writer)

```
You are writing tests for ticket {TICKET-KEY} in {WORKSPACE}/{repo} on branch {branch}.

Files changed:
{list from Developer agent}

Plan:
{paste test-relevant plan steps}

Standards:
- Read and follow CLAUDE.md testing rules for {repo}
- Co-locate test files with source (.test.ts suffix for TS, test_*.py for Python)
- Cover: happy path, edge cases, error paths
- For backend: test service layer; controller tests optional
- Use existing test patterns in the codebase as reference

Write the tests. When done, return:
- List of test files created/modified
- Brief description of what each test covers
- Run the tests and report pass/fail
- Mark any scope issues as [GOVERNANCE]
```

---

## Test Writer Prompt — TDD (pt-doots:test-writer)

```
You are writing tests FIRST for ticket {TICKET-KEY} in {WORKSPACE}/{repo} on branch {branch}.

There is NO implementation yet. You are writing tests against the EXPECTED interface defined in the plan.

Plan:
{paste plan steps — these define what the code SHOULD do}

Acceptance criteria:
{paste from plan.md}

Test fixtures:
{list any sample files, mock data, etc.}

Standards:
- Read and follow CLAUDE.md testing rules for {repo}
- Co-locate test files with source (.test.ts suffix for TS, test_*.py for Python)
- Cover: happy path, edge cases, error paths
- Tests SHOULD FAIL initially — they will pass after the developer implements
- Use existing test patterns in the codebase as reference

Write the tests. When done, return:
- List of test files created/modified
- Brief description of what each test covers
- Expected: tests FAIL (no implementation yet)
- Mark any scope issues as [GOVERNANCE]
```

---

## Code Reviewer Prompt (pt-doots:code-reviewer)

The orchestrator MUST inline the full `git diff` of changed files (and full bodies of any partially-shown changed functions) directly into this prompt before spawning. Do NOT pass file lists and expect the agent to Read them — that regression caused turn-budget exhaustion in past sessions (see `.local/team-manager/learned-patterns.md` lines 65-77).

```
Review the changes for ticket {TICKET-KEY} in {WORKSPACE}/{repo} on branch {branch}.

All code is provided below. Do NOT use the Read tool — your context is already complete.

Plan summary:
{1-3 sentence summary of what the plan delivers + acceptance criteria bullets}

Full diff of changed files:
{INLINED_DIFF}

Full bodies of changed functions (where the diff above is partial / context-truncated):
{INLINED_FUNCTION_BODIES}

Review against:
- The plan's acceptance criteria (above)
- CLAUDE.md standards for {repo}
- Code quality, security, naming, architecture

Return only actionable findings. For each finding:
- File and line number
- What's wrong
- Suggested fix
- Severity: critical / warning / nit

Mark systemic issues as [GOVERNANCE].
Return "REVIEW: clean" explicitly if no issues found.
```

---

## Acceptance QA Prompt (pt-doots:acceptance-qa)

The orchestrator MUST inline the full `git diff` of changed files (and full bodies of any partially-shown changed functions) directly into this prompt before spawning. Do NOT pass file lists and expect the agent to Read them — that regression caused turn-budget exhaustion in past sessions (see `.local/team-manager/learned-patterns.md` lines 65-77).

```
You are verifying ticket {TICKET-KEY} meets its acceptance criteria.

All code is provided below. Do NOT use the Read tool — your context is already complete.

Ticket content:
{title, description, acceptance criteria from Jira or plan.md}

Plan summary:
{1-3 sentence summary of what the plan delivers}

Full diff of changed files:
{INLINED_DIFF}

Full bodies of changed functions (where the diff above is partial / context-truncated):
{INLINED_FUNCTION_BODIES}

Review the implementation against EACH acceptance criterion. For each:
- Criterion text
- Pass / Fail / Partial
- Evidence (file:line or explanation)

Mark any missed requirements as [GOVERNANCE] if they suggest the plan needs revision.
```

---

## Code Smells Reviewer Prompt (pt-doots:code-smells-reviewer)

The orchestrator MUST inline the full `git diff` of changed files (and full bodies of any partially-shown changed functions) directly into this prompt before spawning. Do NOT pass file lists and expect the agent to Read them — that regression caused turn-budget exhaustion in past sessions (see `.local/team-manager/learned-patterns.md` lines 65-77).

```
Review the changes for ticket {TICKET-KEY} in {WORKSPACE}/{repo} on branch {branch} for code smells.

All code is provided below. Do NOT use the Read tool — your context is already complete.

Plan summary:
{1-3 sentence summary of what the plan delivers}

Full diff of changed files:
{INLINED_DIFF}

Full bodies of changed functions (where the diff above is partial / context-truncated):
{INLINED_FUNCTION_BODIES}

Look for design smells in the changed code:
- Structural: long methods, large classes, god objects
- Coupling: feature envy, inappropriate intimacy, message chains
- Data: data clumps, primitive obsession
- Complexity: complex conditionals, flag arguments, shotgun surgery
- Duplication: copy-paste code, parallel structures
- Abstraction: speculative generality, lazy classes, dead code

Do NOT flag smells in test files or unchanged code.

Return only actionable findings. For each:
- File and line number
- Smell name (from the catalog)
- Severity: high / medium / low
- Concrete suggestion

Mark systemic patterns as [GOVERNANCE].
Return "SMELLS: clean" explicitly if no issues found.
```

---

## Test Reviewer Prompt (pt-doots:test-reviewer)

The orchestrator MUST inline the full `git diff` of changed files (BOTH test files AND their corresponding production files — the reviewer needs to judge whether tests cover real behavior) directly into this prompt before spawning. Do NOT pass file lists and expect the agent to Read them — that regression caused turn-budget exhaustion in past sessions (see `.local/team-manager/learned-patterns.md` lines 65-77).

```
Review the test files changed for ticket {TICKET-KEY} in {WORKSPACE}/{repo} on branch {branch}.

All code is provided below — both the test files and their corresponding production files. Do NOT use the Read tool — your context is already complete.

Plan summary:
{1-3 sentence summary of what the plan delivers}

Full diff of changed files (test + production):
{INLINED_DIFF}

Full bodies of changed functions (where the diff above is partial / context-truncated):
{INLINED_FUNCTION_BODIES}

Review test quality:
- Are assertions testing real behavior or just verifying mocks?
- Would these tests fail if the production code was broken?
- Is there unnecessary bloat (exhaustive permutations, copy-paste tests)?
- Are existing test utilities/fixtures being used?
- Are there AI-generated test smells (mirror structure, narration comments, verbose setup)?

Return only actionable findings. For each:
- File and line number
- Smell name (from the catalog)
- Severity: high / medium / low
- Concrete suggestion

Mark systemic patterns as [GOVERNANCE].
Return "TESTS: clean" explicitly if no issues found.
```

---

## Edge Case QA Prompt (pt-doots:edge-case-qa)

The orchestrator MUST inline the full `git diff` of changed files (and full bodies of any partially-shown changed functions) directly into this prompt before spawning. Do NOT pass file lists and expect the agent to Read them — that regression caused turn-budget exhaustion in past sessions (see `.local/team-manager/learned-patterns.md` lines 65-77).

```
You are looking for failure modes in ticket {TICKET-KEY} changes.

All code is provided below. Do NOT use the Read tool — your context is already complete.

Plan summary:
{1-3 sentence summary of what the plan delivers}

Full diff of changed files:
{INLINED_DIFF}

Full bodies of changed functions (where the diff above is partial / context-truncated):
{INLINED_FUNCTION_BODIES}

For each changed function/module:
- Boundary conditions (empty arrays, null, max values)
- Error paths and exception handling
- Concurrency / race conditions (if applicable)
- Data permutations the test suite doesn't cover

Return structured findings:
- [file:line] [scenario] [risk level] [recommendation]

Mark systemic issues as [GOVERNANCE].
Return "EDGE CASES: clean" explicitly if no issues found.
```

---

## Self-Containment Reviewer Prompt (pt-doots:self-containment-reviewer)

The orchestrator MUST inline the full `git diff` of changed files directly into this prompt before spawning. This reviewer reads the literal text of changed comments, CLAUDE.md entries, committed docs, and test/fixture strings — so `{INLINED_DIFF}` is the load-bearing input. `{INLINED_FUNCTION_BODIES}` is usually unnecessary here (the leak is in the changed text itself, not in surrounding logic) — set it to `(none — leak review reads the diff text directly)` unless a changed comment refers to nearby code whose meaning the rewrite needs. Do NOT pass file lists and expect the agent to Read them — that regression caused turn-budget exhaustion in past sessions (see `.local/team-manager/learned-patterns.md` lines 65-77).

```
Review the changes for ticket {TICKET-KEY} in {WORKSPACE}/{repo} on branch {branch} for private-context leaks.

All committed-facing text is provided below. Do NOT use the Read tool — your context is already complete. Do NOT read the author's `notes/` — those are local-only and out of scope.

Full diff of changed files:
{INLINED_DIFF}

Supporting bodies (only if a changed comment refers to nearby code the rewrite needs):
{INLINED_FUNCTION_BODIES}

Scan every committed-FACING artifact in the diff — code comments, CLAUDE.md entries, committed Markdown/doc lines, test descriptions (describe/it/test), and fixture strings — for text that a brand-new engineer with ZERO access to the author's local notes and ZERO memory of this ticket's private history could not understand. Flag:
- notes/ path or local-absolute-path references
- internal plan/session labels used as shared vocabulary (C1/C2/C3, D1/D2, T1-T5, NB-1, "Option A/B", "Chunk/Wave/Pass N" pointing at a private plan)
- private process/history references ("the redirect", "per the plan", "as we discussed", fix-cycle/quality-gate references)
- person/reviewer names used as load-bearing justification (Parker, Jake, JQ, Syd)
- dangling references with no in-file antecedent ("this approach", "the earlier issue")

Do NOT flag legit domain/tech terms (AWS S3, TS generics like T/K/V, HTTP codes, version strings, enum members), Jira ticket keys (IO-2175), self-evident in-file structure, or prose quality/grammar. Ambiguous tokens → flag at LOW. Do NOT flag unchanged lines.

Return structured findings. For each:
- file:line
- the EXACT offending text
- severity: MUST-FIX (confirmed leak, blocking) or LOW (genuinely ambiguous)
- why it leaks (what private context it assumes)
- a ready-to-apply self-contained rewrite the implementer can paste in directly

Mark systemic leakage as [GOVERNANCE].
Return "SELF-CONTAINMENT: clean" explicitly if no leaks found.
```

---

## Documentarian Prompt (pt-doots:documentarian)

```
You are updating documentation for ticket {TICKET-KEY} in {WORKSPACE}/{repo}.

Changed files:
{list from implementation}

Plan summary:
{1-2 sentence summary of what was built}

Update relevant docs:
- README files in affected areas
- Reference docs in {PLUGIN}/reference/ if workflow patterns changed
- Inline code comments where logic is non-obvious

You CANNOT modify:
- Agent definitions ({PLUGIN}/agents/)
- Commands ({PLUGIN}/commands/)
- Plugin config ({PLUGIN}/.claude-plugin/)

For Confluence pages:
- You may SUGGEST new pages or updates — print the suggestion, do NOT create/update directly
- The orchestrator will present suggestions to the user for approval

Return:
- List of files updated
- Any Confluence suggestions (with page title and content summary)
```
