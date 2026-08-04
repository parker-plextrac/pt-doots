# pt-doots

A Claude Code plugin for PlexTrac engineers. Turns a Jira ticket into a
finished PR via an orchestrated team of sub-agents — research → plan →
implement → test → review → commit.

Opinionated for our repos (`product-core-backend`, `product-core-frontend`,
`product-services-export`, `product-services-mcp`), our standards
(per-repo CLAUDE.md), and our tooling (Jira/Confluence REST, GitHub via `gh` CLI).

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

## Tuning agent behavior

Per-user tweaks go in overlay files in your memory dir, not in the plugin tree. See [OVERLAYS.md](./OVERLAYS.md). Bundle vs overlay separation keeps your customizations upgrade-safe.

## Prerequisites

- Claude Code with agent teams enabled (above)
- Workspace laid out with PlexTrac repos checked out side-by-side under one parent directory
- **[PlexTrac agent-skills plugin](https://github.com/PlexTrac/agent-skills) installed and `/setup` completed.** This is the hard requirement — pt-doots delegates verify, PR, ticket, log, and stack work to commands from agent-skills (`/verify`, `/create-pr`, `/ticket`, `/logs`, `/stack-up`, etc.) and its `/setup` provisions every credential and CLI listed below.

Agent-skills `/setup` installs/verifies:

- **`gh` CLI** authenticated against PlexTrac's GitHub org — primary tool for PR work; the GitHub MCP is a fallback when `gh` is unavailable
- **Atlassian API token** at `~/.jira-attlasian-cred` — pt-doots talks to Jira and Confluence via REST directly; the Atlassian MCP is **not** used because its OAuth flow fails mid-workflow
- **`~/bin/jira-attachment`** symlink to the bundled download script (used for tickets with attached repro files)

Install agent-skills first, run `/setup`, then come back here.

## Commands

| Command | What it does |
|---------|-------------|
| `/pt-doots` | Orchestrator — detects intent from your message |
| `/prs` | PR dashboard for all open PlexTrac PRs |
| `/prs <PR-url>` | Structured review of a single PR using the team |
| `/prs self [TICKET-KEY]` | Run the full review swarm against your own inflight code; saves findings to `notes/{TICKET}/`. Auto-detects the ticket from your current branches if you omit the key. Handles multi-repo tickets (FE + BE) as parallel arms. |
| `/prs <PR-url> loose` | Lighter review: surfaces only must-level blockers |
| `/bootstrap-team` | One-time setup — spawns the team-manager to create every agent locally |
| `/team-audit` | Roster health check + agent performance review |
| `/voice-profile` | Customize your personal voice overlay for the `voice-stylist` agent |

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
| `implementer` | The implementation agent: implements plan steps within a locked file surface, audits its own diff against the plan |
| `test-writer` | Writes co-located tests in the repo's framework (mocha, jest, pytest) |
| `code-reviewer` | Reviews changed files against per-repo CLAUDE.md standards |
| `acceptance-qa` | Verifies acceptance criteria with code evidence |
| `edge-case-qa` | Hunts boundary conditions, null/empty/race scenarios |
| `code-smells-reviewer` | Catches Fowler-catalog smells (long methods, feature envy, primitive obsession) |
| `test-reviewer` | Catches hollow assertions, over-mocking, and AI-test smells |
| `repro-verifier` | Proves or refutes review findings by writing and running repro scripts (used by `/prs`) |
| `self-containment-reviewer` | Flags committed artifacts that leak private notes paths, internal plan labels, or reviewer names |
| `re-reviewer` | Verifies prior review findings on subsequent commits (used by `/prs`) |
| `documentarian` | Updates READMEs and Confluence after merge (when scrum-master sets `Documentation: yes`, or workflow is `docs-only`) |
| `voice-stylist` | Final voice pass on every human-facing draft (PR comments, Slack, Jira). Used by `/prs` between rough draft and approval gate |
| `team-manager` | Creates and tunes the team itself; used by `/bootstrap-team` and `/team-audit` |

## Implementation

`implementer` is the sole implementation agent (strict, plan-fidelity). It locks the file surface from the plan, audits its own diff against forbidden patterns, and reports every plan deviation. It runs in both Step 4a (implement) and Step 4d (fix findings). Engineers who want a looser flow can say so during planning; the orchestrator relaxes plan-fidelity within `implementer` rather than switching agents.

Default sequencing is **test-first (TDD)**: the test-writer writes failing tests against the planned interface, then the implementer makes them pass. `TDD: no` (docs-only, dependency bumps, pure config) is the exception that runs implement-first.

## Conventions overlays

The base agents are language-neutral. Language-specific rules live in two overlays the orchestrator injects into each writer and language-sensitive reviewer at spawn time:

- `reference/typescript-conventions.md`: TypeScript rules (including size caps).
- `reference/python-conventions.md`: Python rules (hops-not-lines, no size caps; framework specifics for Pydantic, structlog, orjson triggered by imports).

The orchestrator detects the changed code's language (by repo and file extension) and injects the matching overlay path; a mixed-language PR loads both, applied per file. The rule and paths are defined once in `reference/workflow.md` (Language Detection section), and the target repo's own committed CLAUDE.md always wins over the overlay.

These **conventions overlays** are distinct from the **preference overlays** in [OVERLAYS.md](./OVERLAYS.md) (personal voice and agent tweaks in user memory). Same word, two mechanisms.

## Review Log Discipline

Every change to an agent definition (model tier, prompt, tools, maxTurns, role) MUST append a dated entry to `reference/agent-logs/{agent}.md` with:
- **Date** of the change
- **What changed** (current → proposed value)
- **Why** — linked ticket, observation, or learned pattern

Silent drift (changes without log entries) makes audits blind to regressions. The team-manager enforces this discipline at every `/team-audit` run; unexplained drift is flagged as a finding.

## Telemetry & state

`/pt-doots` records run-level metrics (which agents ran, durations, fix cycles, workflow outcome) so `/team-audit` has real history to analyze. This data lives in a fixed, home-anchored **state directory**, deliberately outside the plugin tree:

```
~/.claude/pt-doots/.local/
├── team-manager/metrics-summary.md    # one entry per ticket, per-agent
├── team-manager/learned-patterns.md   # patterns the team-manager accumulates
└── scrum-master/workflow-history.md   # one entry per ticket, overall outcome
```

Why `~/.claude/pt-doots` and not inside the plugin:

- **Always resolvable.** It is anchored to `$HOME`, so the orchestrator writes it with zero path-guessing. The plugin's own install path is *not* reliably knowable from a command's shell (`CLAUDE_PLUGIN_ROOT` is not set there, and the plugin may run from a live checkout, a cache copy, or a marketplace dir), which previously caused telemetry to silently fail to record.
- **Survives updates.** Plugin reinstalls, cache refreshes, and version bumps never touch it, so run history accumulates across upgrades.
- **Portable.** Any engineer using the plugin gets working telemetry with no path configuration.

It self-initializes on the first `/pt-doots` run (the command creates the tree and header files if missing), so a fresh install needs no manual setup. Nothing here is committed to git; it is per-user runtime state. The write/read contract is defined in [`commands/pt-doots.md` § Telemetry](./commands/pt-doots.md); the file schemas are in [`reference/metrics-format.md`](./reference/metrics-format.md).

## Workflow

```
Step 0    Load context + git state
Step 0.5  Scrum-master picks workflow type (+ Documentation / TDD flags, both default yes)
Step 1    Researcher → notes/{TICKET}/research.md
Step 2    Plan with the user → notes/{TICKET}/plan.md
Step 3    Branch ({TICKET-KEY}-{short-description})
Step 4b   Test-writer writes failing tests (TDD default, runs first) → /verify
Step 4a   Implementer implements to green → /verify
Step 4c   Quality gate (6 reviewers in parallel)
Step 4d   Implementer fixes findings → /verify
Step 4e   Documentarian updates docs (when Documentation: yes or workflow is docs-only)
Step 5    Commit gate: user approves checklist
Step 6    Handoff → /create-pr
```

All ticket artifacts (research, plan, progress, scratch scripts) live in
`notes/{TICKET-KEY}/` — never committed to product repos.

## Workflow types

The scrum-master picks one of four types, plus orthogonal flags
(`Documentation: yes/no`, `TDD: yes/no`):

| Type | When | Pipeline |
|------|------|----------|
| **standard** | Most tickets — features, multi-file changes, anything risky | Full pipeline; parallel quality gate (6 reviewers) |
| **lightweight** | Single-file fixes, dependency bumps, additive changes | Skips acceptance-qa + edge-case-qa; smaller review surface |
| **docs-only** | Documentation-only tickets (READMEs, comments, reference docs) | Researcher → documentarian → code-reviewer + self-containment-reviewer → commit |
| **custom** | Tickets that don't fit a template | Scrum-master proposes the variant with rationale |

You can override the recommendation when prompted.

## Customizing Your Voice

The `voice-stylist` agent rewrites human-facing drafts (PR comments, Slack
pings, Jira replies) into your voice before they're shown for approval. It
reads two layers of rules:

1. **Bundle** at `agents/voice-stylist/profile.md` — universal good-prose
   rules shipped with the plugin (banned-phrases starter list, prefix scheme,
   em-dash rule, plain-verb mappings). Works out of the box for everyone.
2. **User overlay** in your local user memory
   (`~/.claude/projects/{workspace}/memory/voice_*.md`) — personal additions
   that override or extend the bundle. Your audience tiers, signature
   emojis, phrases YOU don't use, prefix tweaks.

To set up or refresh your overlay, run `/voice-profile`. The command walks
you through a short interview and writes the overlay files for you. You
can also just ask Claude directly: "help me edit my voice profile."

Without an overlay, the agent runs on the bundle alone — still useful,
just less personal.

## Local development

```bash
git clone https://github.com/parker-plextrac/pt-doots ~/workspaces/plextrac/pt-doots
claude --plugin-dir ~/workspaces/plextrac/pt-doots
```

Edit any agent under `agents/` or command under `commands/` and reload
Claude Code to pick up changes.
