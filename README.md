# pt-doots

A Claude Code plugin for PlexTrac engineers. Turns a Jira ticket into a
finished PR via an orchestrated team of sub-agents — research → plan →
implement → test → review → commit.

Opinionated for our repos (`product-core-backend`, `product-core-frontend`,
`product-services-export`, `product-services-mcp`), our standards
(per-repo CLAUDE.md), and our tooling (Jira, Confluence, GitHub MCP).

## Install (from marketplace)

```
/plugin marketplace add parker-plextrac/pt-doots
/plugin install pt-doots@pt-doots
```

Then enable agent teams (one-time):

```bash
echo 'CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1' >> ~/.claude/settings.local.json
```

Restart Claude Code after install.

## Prerequisites

- Claude Code with agent teams enabled (above)
- [PlexTrac agent-skills plugin](https://github.com/PlexTrac/agent-skills) — provides `/verify`, `/logs`, `/create-pr`, `/setup`, etc.
- MCP servers configured for GitHub + Atlassian (Jira/Confluence) — run `/setup` from agent-skills if you haven't
- Workspace laid out with PlexTrac repos checked out side-by-side under one parent directory

## Commands

| Command | What it does |
|---------|-------------|
| `/pt-doots` | Orchestrator — detects intent from your message |
| `/prs` | PR dashboard for all open PlexTrac PRs |
| `/prs <PR-url>` | Structured review of a single PR using the team |
| `/bootstrap-team` | One-time setup — spawns the team-manager to create every agent locally |
| `/team-audit` | Roster health check + agent performance review |
| `/new-integration` | Scaffold a new EM integration across BE + FE repos |

### Talking to `/pt-doots`

The orchestrator picks a mode from how you phrase it:

| Phrasing | Mode |
|----------|------|
| "tackle IO-2097", "do IO-2097", "implement IO-2097", "doots IO-2097" | Tackle the ticket end-to-end |
| "check on IO-2097", "status IO-2097", "where are we on IO-2097" | Status check — reads `notes/IO-2097/progress.md` |
| "save our work", "save progress", "let's save" | Save current state to `progress.md` |

## The Agent Team

`/pt-doots` orchestrates a team of focused sub-agents. Each one has a narrow
job, a locked tool surface, and a prompt tuned to PlexTrac standards.

| Agent | Role |
|-------|------|
| `scrum-master` | Picks the right workflow (standard / lightweight / docs-only / custom) per ticket |
| `researcher` | Traces the codebase + Confluence, writes `notes/{TICKET}/research.md` |
| `developer` | Implements plan steps; writes production code following the repo's CLAUDE.md |
| `implementer` | Plan-fidelity variant of developer — audits its own diff against the plan |
| `test-writer` | Writes co-located tests in the repo's framework (mocha, jest, pytest) |
| `code-reviewer` | Reviews changed files against per-repo CLAUDE.md standards |
| `acceptance-qa` | Verifies acceptance criteria with code evidence |
| `edge-case-qa` | Hunts boundary conditions, null/empty/race scenarios |
| `code-smells-reviewer` | Catches Fowler-catalog smells (long methods, feature envy, primitive obsession) |
| `test-reviewer` | Catches hollow assertions, over-mocking, and AI-test smells |
| `re-reviewer` | Verifies prior review findings on subsequent commits (used by `/prs`) |
| `documentarian` | Updates READMEs and Confluence after merge (when scrum-master sets `Documentation: yes`, or workflow is `docs-only`) |
| `team-manager` | Creates and tunes the team itself; used by `/bootstrap-team` and `/team-audit` |

## Developer modes

Pt-doots ships two implementation agents:

- **`implementer`** (default, strict). Locks the file surface from the plan, audits its own diff against forbidden patterns, and reports every plan deviation. Slower, higher signal.
- **`developer`** (opt-in, loose). Faster, less ceremony, more latitude. Default for `lightweight` workflows.

The orchestrator picks based on:
1. Env var `PT_DOOTS_DEV_MODE=loose` → `developer`
2. Scrum-master classifies workflow as `lightweight` → `developer`
3. Otherwise → `implementer`

Other engineers who want the looser flow as their default can `export PT_DOOTS_DEV_MODE=loose` in their shell rc.

## Review Log Discipline

Every change to an agent definition (model tier, prompt, tools, maxTurns, role) MUST append a dated entry to `agents/reviews/{agent}.md` with:
- **Date** of the change
- **What changed** (current → proposed value)
- **Why** — linked ticket, observation, or learned pattern

Silent drift (changes without log entries) makes audits blind to regressions. The team-manager enforces this discipline at every `/team-audit` run; unexplained drift is flagged as a finding.

## Workflow

```
Step 0    Load context + git state
Step 0.5  Scrum-master picks workflow type
Step 1    Researcher → notes/{TICKET}/research.md
Step 2    Plan with the user → notes/{TICKET}/plan.md
Step 3    Branch ({TICKET-KEY}-{short-description})
Step 4a   Developer implements → /verify
Step 4b   Test-writer writes tests → /verify
Step 4c   Quality gate (5 reviewers in parallel)
Step 4d   Developer fixes findings → /verify
Step 4e   Documentarian updates docs (when Documentation: yes or workflow is docs-only)
Step 5    Commit gate — user approves checklist
Step 6    Handoff → /create-pr
```

All ticket artifacts (research, plan, progress, scratch scripts) live in
`notes/{TICKET-KEY}/` — never committed to product repos.

## Workflow types

The scrum-master picks one of four types, plus orthogonal flags
(`Documentation: yes/no`, `TDD: yes/no`):

| Type | When | Pipeline |
|------|------|----------|
| **standard** | Most tickets — features, multi-file changes, anything risky | Full pipeline; parallel quality gate (5 reviewers) |
| **lightweight** | Single-file fixes, dependency bumps, additive changes | Skips acceptance-qa + edge-case-qa; smaller review surface |
| **docs-only** | Documentation-only tickets (READMEs, comments, reference docs) | Researcher → documentarian → code-reviewer → commit |
| **custom** | Tickets that don't fit a template | Scrum-master proposes the variant with rationale |

You can override the recommendation when prompted.

## Local development

```bash
git clone https://github.com/parker-plextrac/pt-doots ~/workspaces/plextrac/pt-doots
claude --plugin-dir ~/workspaces/plextrac/pt-doots
```

Edit any agent under `agents/` or command under `commands/` and reload
Claude Code to pick up changes.
