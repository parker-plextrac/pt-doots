# Team Manager — Learned Patterns

## Workflow Patterns

### Pattern: Parser and exporter tickets always need full QA (standard workflow)
- Evidence: IO-2158 — Scrum Master recommended lightweight, user overrode to standard
- Recommendation: When ticket involves parser code (integration-worker parsers) or export service (product-services-export), Scrum Master should always recommend Standard workflow with all 3 QA agents
- Reason: Parser and exporter code is legacy, brittle, and tightly coupled. Fixing one parser frequently breaks another. Full QA gate catches regressions.
- Confidence: medium (1 ticket, but strong user signal — "parser fixes are tricky, we tend to fix something and break another part")

## Agent Performance Patterns

### Pattern: Scrum Master lacks PlexTrac domain knowledge
- Evidence: IO-2158 — SM referenced non-existent repo "product-services-parsing", didn't know parsers live in product-core-backend/apps/integration-worker
- Recommendation: SM agent definition needs baseline PlexTrac domain context (repo structure, legacy areas, brittle zones)
- Confidence: high (fundamental gap, not ticket-specific)

### Pattern: Researcher must search active repos, not legacy repos
- Evidence: IO-2182 — Researcher explored legacy Python parser in product-services-parsing instead of active TypeScript parser in product-core-backend/apps/integration-worker. Missed that the work was already 80% done behind a feature flag (BURP_IO_1611_MAPPING). This led to a completely wrong LOE estimate (4-6 hrs instead of 2-3 hrs).
- Recommendation: Researcher agent prompt MUST include explicit instruction: "Parsers live in product-core-backend/apps/integration-worker, NOT product-services-parsing (legacy). Always check the integration-worker batch-generators first for any parser ticket."
- Confidence: high (caused incorrect research output and wasted a session)

## Codebase Patterns

### Pattern: Legacy brittle areas — handle with care
- Areas: integration-worker parsers (product-core-backend), product-services-export (Python)
- Recommendation: Always use standard workflow, always run edge-case-qa, always add regression test fixtures
- Confidence: medium (user feedback, needs more ticket data)

### Pattern: Many parsers have been ported to TypeScript — always check which is active
- Evidence: IO-2182 — The Burp parser has both a Python version (product-services-parsing) and an active TypeScript version (product-core-backend/apps/integration-worker/batch-generators/burp-xml-generator.ts). Some Python parsers are still active.
- Recommendation: For any parser ticket, check `file-upload-processor.ts` to see which code path is wired up. If a TypeScript batch-generator exists, that's likely the active one. Don't assume all Python parsers are inactive.
- Confidence: high (confirmed by checking file-upload-processor.ts)

### Pattern: Check for existing feature flags before estimating work
- Evidence: IO-2182 — The Burp parser already had locationUrl and vulnerableParameters support behind BURP_IO_1611_MAPPING flag. Researcher missed this because it searched the wrong repo.
- Recommendation: For any parser/import ticket, check features.ts for existing feature flags related to the scanner type. Partial work may already exist behind a flag.
- Confidence: high (would have saved an entire research cycle)

## Agent Architecture Patterns

### Pattern: `disallowedTools` frontmatter is NOT enforced by the agent teams framework
- Evidence: IO-2158 session — SM had `disallowedTools: Read Write Edit Bash Grep Glob` but still used Read (5), Grep (8), Glob (3) in 16 tool calls
- Fix: Use `tools` whitelist as the enforcement mechanism. Remove `disallowedTools` from all agents (misleading).
- Confidence: high (tested 3 times in same session)

### Pattern: `tools: ""` (empty string) does NOT mean "no tools"
- Evidence: IO-2158 session — SM with `tools: ""` still had full tool access
- Fix: Empty string is parsed as "no restriction". To remove tools, omit the `tools` field entirely AND set `maxTurns: 1`
- Confidence: high (tested directly)

### Pattern: Return-as-output pattern for read-only agents (RECOMMENDED)
- Evidence: IO-2158 session — expert consultation on agent teams best practices
- Problem: Agents with Write tool spend all turns exploring and never write their output file. Prompt-based turn budgeting is unreliable (agents have no internal turn counter).
- Fix: Remove Write from read-only agents. Their structured text response IS the deliverable. The orchestrator writes the file. `maxTurns` cutoff still produces a final text response — output is guaranteed.
- Applied to: researcher, code-reviewer, acceptance-qa, edge-case-qa, scrum-master
- Exception: developer, test-writer, documentarian, team-manager legitimately need Write/Edit
- Confidence: high (expert-validated pattern, SM fix tested and confirmed)

### Pattern: Classifier agents (SM) work best with maxTurns: 1
- Evidence: IO-2158 session — SM spent all 8 turns exploring parser source code instead of producing a workflow recommendation. With maxTurns: 1, produced clean WORKFLOW PLAN in 11.5s with 0 tool calls.
- Fix: `maxTurns: 1` + no `tools` field. All context passed in prompt by orchestrator.
- Confidence: high (tested and validated)

### Pattern: QA agents (read-only) also exhaust turns exploring without delivering findings
- Evidence: IO-2158 session — code-reviewer (15 turns), acceptance-qa (10 turns), and edge-case-qa (15 turns) all hit maxTurns while reading files. None produced a final structured verdict.
- Problem: Same root cause as write-agents — agents explore too much and don't reserve turns for output. Read-only agents with maxTurns cutoff DO produce a final text response, but it's whatever they were thinking mid-exploration, not a structured summary.
- Fix: Include ALL relevant code diffs and file contents inline in the agent prompt. Tell the agent "All code is provided below — do NOT read any files. Produce your findings immediately."
- Confidence: high (3/3 QA agents failed to produce structured output in the same session)

### Pattern: Write-agents need complete context inline — don't reference files
- Evidence: IO-2158 session — test-writer burned 34 tool calls (161s) exploring `nipper-xml-generator.test.ts` (23K tokens) and never wrote the test file. Second spawn with complete test pattern inline in the prompt succeeded in 14 tool calls (137s).
- Problem: Prompts that say "follow the pattern from {file}" cause write-agents to spend all their turns reading that file. By the time they understand the pattern, they're out of turns.
- Fix: Orchestrator reads reference files in main context BEFORE spawning the agent, then pastes the relevant patterns (imports, setup boilerplate, type signatures) directly into the agent prompt. Agent should need zero or minimal exploration to start writing.
- Applied to: test-writer (confirmed), likely applies to developer and documentarian too
- Confidence: high (A/B tested in same session — reference-based prompt failed, inline prompt succeeded)

---
Last updated: 2026-04-07
Total tickets analyzed: 2 (IO-2158, IO-2182)
