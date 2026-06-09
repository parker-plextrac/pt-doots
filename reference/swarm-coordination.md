# Swarm Coordination — Patterns for Multi-Wave Parallel Agent Work

Sourced from Anthropic's official Claude Code docs (2026-06-09). These patterns apply when the orchestrator dispatches MANY sub-agents in parallel — either many items in one wave, or multiple waves of items in sequence. For single-ticket flow, see [workflow.md](workflow.md).

---

## Sub-agents vs Agent Teams — pick the right primitive

| | Sub-agents | Agent Teams |
|---|---|---|
| **Spawned via** | `Agent` tool from orchestrator | `Agent` tool from lead **with `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`** + `name:` param |
| **Communication** | Report results to orchestrator only | Teammates message each other directly via `SendMessage` |
| **Context** | Own context window; results return to caller | Own context window; fully independent |
| **Token cost** | Lower — results summarized back to main | Higher — each teammate is a separate Claude instance |
| **Plan-mode cost** | Normal | **~7x more** when teammates run in plan mode ([source](https://code.claude.com/docs/en/costs)) |
| **Best for** | Naturally sequential workflows (research → impl → test); fan-out where workers don't need to talk to each other | Adversarial debate, debugging with competing hypotheses, cross-layer work where workers must coordinate live |
| **Cleanup** | Auto on agent finish | Lead must explicitly clean up; fails if teammates still active |

**Default for pt-doots swarms: sub-agents.** Our work-units are file-disjoint by design and follow research → implement → test → review → fix sequentially within each unit. There's no inter-agent dialogue, so we get the cheaper primitive. Switch to agent teams ONLY when a wave genuinely needs adversarial debate or live cross-agent coordination.

> "For workflows that are naturally sequential, basic sub-agents may be simpler and cheaper." — `claude-code-agent-teams` skill (local).

---

## Concurrency

**Anthropic guidance** ([source](https://code.claude.com/docs/en/agent-teams#choose-an-appropriate-team-size)):

> "There's no hard limit on the number of teammates, but practical constraints apply… Start with 3-5 teammates for most workflows. This balances parallel work with manageable coordination."
>
> "Having 5-6 tasks per teammate keeps everyone productive without excessive context switching. If you have 15 independent tasks, 3 teammates is a good starting point."

**pt-doots default cap:** 3–5 parallel sub-agents per repo. Scale up only if monitoring shows underutilization. Token costs scale linearly with active agent count.

When dispatching, batch independent items into a single message with multiple `Agent` tool calls (the harness fan-outs in parallel). Sequential items go in separate messages.

---

## Worktree isolation for parallel writes

**For parallel implementers in the same repo:** add `isolation: worktree` to the agent definition's frontmatter. Each spawn gets its own temporary git worktree under `.claude/worktrees/`, branched off `origin/HEAD` by default.

```yaml
---
name: implementer
isolation: worktree
---
```

**Auto-cleanup behavior** ([source](https://code.claude.com/docs/en/worktrees#clean-up-worktrees)):
- Worktree with **no changes** → removed automatically when agent finishes.
- Worktree **with changes** → persists for orchestrator review.

**To branch off the agent's current `HEAD` instead of `origin/HEAD`** (useful when isolating sub-agents that need to operate on in-progress work), set in `settings.json`:

```json
{ "worktree": { "baseRef": "head" } }
```

### `.worktreeinclude` — auto-copy `.env` and other gitignored files

Worktrees are fresh checkouts — gitignored files like `.env` are NOT present. To copy them automatically when a sub-agent worktree is created, add a `.worktreeinclude` file at the repo root using `.gitignore` syntax. Only gitignored files that match are copied:

```
.env
.env.local
config/secrets.json
```

This applies to `--worktree`, sub-agent worktrees, and parallel sessions in the desktop app. **Use this in every PlexTrac repo we run sub-agent worktrees against** — it replaces ad-hoc symlink-then-copy hacks.

---

## Do NOT require plan approval per sub-agent

Per-agent plan approval is what triggers the **7x token cost multiplier** for agent teams ([source](https://code.claude.com/docs/en/costs)). pt-doots already does NOT require per-sub-agent plan approval — the orchestrator owns planning (Step 2) and gates approval at the wave/PR boundary. Keep it that way.

For complex changes that need approval, gate at the orchestrator level (one plan presented to user before dispatching N implementers), not at the per-sub-agent level (N plans).

---

## Wave-based swarm pattern (multi-item production work)

Use for backlog-burndowns: 5+ items to ship under one quality bar.

### Wave structure

Each wave is a discrete batch of work-units that ship together. Inside a wave:

1. **Pre-wave**: orchestrator sets up worktree skeleton; opens a tracking issue (per-wave); locks branch-naming and PR template; saves wave plan to a notes file.
2. **Implement (parallel)**: spawn `pt-doots:implementer` per item, each in its own worktree (`isolation: worktree`). Single message, multiple tool calls. Cap at 3–5 concurrent.
3. **Test (parallel)**: spawn `pt-doots:test-writer` per item for coverage gaps.
4. **Per-item `/verify`**: orchestrator runs verification in each branch.
5. **Quality gate (parallel)**: 5-reviewer gate per item (or batched across small items). Inline-diff + caller-body substitution per [agent-prompts.md § Step 4c contract](agent-prompts.md).
6. **Fix-cycle**: implementer addresses findings in same branch.
7. **Merge sequence**: merge each branch's PR in dependency order; re-verify after each merge.
8. **Wave-exit checklist** before starting wave N+1: all PRs merged, CI green, tracking issue closed.

### Sequencing rule

**Wave-by-wave, no pipelining.** Each wave fully closes before the next begins. Deferring quality across waves compounds tech debt — the inverse of our project goal. (Source: 2026-05 integration-broker pivot debt experience.)

### Audit trail

- **Per-item PR** with branch `swarm/wave-N/<ITEM-ID>-<slug>` and title citing the roadmap item ID.
- **Per-wave GitHub tracking issue** listing all child PRs + wave-exit criteria. Auto-closes when all PRs merge.
- **Per-item notes** at `notes/<project>/swarm/wave-N/<ITEM-ID>/{research,plan,progress}.md`.
- **Telemetry** to `.local/scrum-master/workflow-history.md` and `.local/team-manager/metrics-summary.md` per spawn (see [metrics-format.md](metrics-format.md)).

---

## Inline-context contract — applies to ALL agent spawns

The Step 4c contract in [workflow.md](workflow.md) makes inline-diff substitution mandatory for the 5 quality-gate reviewers. **Extend the same discipline to every sub-agent spawn**:

- **Researcher**: paste ticket details inline; researcher will still need to read code (that's the job), but spawn prompt should never say "go fetch the ticket".
- **Implementer**: paste relevant plan steps inline; do not say "read plan.md to figure out what to do".
- **Test-writer**: paste the list of changed files + paste pattern snippets to follow; do not say "read existing tests for pattern".
- **All reviewers**: paste full diff + caller bodies. See [agent-prompts.md § quality gate prompts](agent-prompts.md).

**Why**: the `code-reviewer` agent has a deterministic 15-tool-use cap. Exploratory prompts terminate at 15 tools with no output. Inline context turns "15 tools, no report" into "0–7 tools, full report". Same agent, same model, same diff — prompt structure is the only difference. (Source: `agent-team-inline-context` skill; A/B data from integration-broker PR 2, 2026-05-19.)

---

## Limitations to be aware of

From Anthropic ([source](https://code.claude.com/docs/en/agent-teams#limitations)):

- **No nested teams**: sub-agents cannot spawn their own sub-agents. Only the orchestrator can. Any agent that needs to coordinate sibling agents must return recommendations to the orchestrator.
- **No session resumption with in-process teammates**: `/resume` and `/rewind` do not restore in-process teammates. After resuming a session, the lead may attempt to message teammates that no longer exist.
- **Task status can lag**: teammates sometimes fail to mark tasks complete, blocking dependents. Orchestrator should nudge if a task appears stuck.
- **Agent teams are experimental**: behavior may change. Sub-agent primitives are more stable.

---

## References

- Anthropic Claude Code — Agent teams: https://code.claude.com/docs/en/agent-teams
- Anthropic Claude Code — Worktrees: https://code.claude.com/docs/en/worktrees
- Anthropic Claude Code — Manage costs: https://code.claude.com/docs/en/costs
- Anthropic Claude Code — Sub-agents: https://code.claude.com/docs/en/sub-agents
- Local skill: `claude-code-agent-teams` — architecture constraints
- Local skill: `agent-team-inline-context` — inline-context contract + A/B data
- pt-doots: [workflow.md](workflow.md), [agent-prompts.md](agent-prompts.md), [metrics-format.md](metrics-format.md)
