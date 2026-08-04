# pt-doots — Operating Notes for Claude

## Working ON pt-doots itself (cold-start map)

**Editing pt-doots (its flow, agents, prompts, or docs) rather than running it on a ticket? Read this, don't re-derive it.** Stable architecture is here; live in-flight work is in `notes/pt-doots-upgrades/SESSION_RESUME.md`.

**Two framings, don't confuse them:**
- **Running** pt-doots on a ticket = the `pt-doots` orchestrator skill (SessionStart auto-loads it); follow `commands/pt-doots.md`.
- **Editing** pt-doots = meta-work on this plugin tree (this map). The orchestrator's "don't touch code" rule is about PlexTrac *product* source; editing pt-doots's own markdown IS the task here.

**Layer model:**
- `commands/*.md`: the playbooks that run (`pt-doots.md` = ticket orchestrator, `prs.md` = PR review).
- `reference/*.md`: the specs the playbooks cite. `workflow.md` holds the detailed ticket steps and the canonical language-detection spec; `agent-prompts.md` holds every sub-agent spawn template; supporting specs are `swarm-coordination.md`, `metrics-format.md`, `progress-format.md`, `branch-naming.md`.
- `agents/*.md` (top level): the sub-agent definitions the flows spawn as `pt-doots:<name>`. Edit these.
- `reference/{typescript,python}-conventions.md`: the language **overlays** injected into language-neutral agents.

**Want to change X, edit Y:**
| Change | File |
|--------|------|
| A ticket-flow step | `reference/workflow.md` |
| A sub-agent's spawn prompt | `reference/agent-prompts.md` |
| A sub-agent's behavior / tools / model | `agents/<name>.md` (top level) |
| Language rules (TS or Python) | `reference/<lang>-conventions.md` |
| The `/prs` review flow or its loose mode | `commands/prs.md` |
| Orchestrator flow contracts | `commands/pt-doots.md` |

**Load-bearing invariants (don't silently break):**
- **Overlay injection:** the language-neutral agents (implementer, test-writer, code / code-smells / test / edge-case reviewers) get a conventions overlay injected at spawn. Detection and paths are defined ONCE in workflow.md's Language Detection section; resolve `LANG` early (ticket flow: Step 3, from the repo) so the implementer gets it.
- **Inline-diff contract (Step 4c):** the orchestrator inlines the full diff and caller bodies into every reviewer prompt; reviewers never Read files themselves. See the Step 4c contract in `commands/pt-doots.md`.
- **Flag-and-wait:** sub-agents, and the orchestrator during planning, surface substantive decisions and WAIT; they never decide solo.
- **Telemetry** lives under `~/.claude/pt-doots/.local/` (home-anchored, never in the plugin tree, never committed).
- **Agent change-logs live in `reference/agent-logs/`** (one per agent, dated entries). They were relocated out of `agents/` because, lacking frontmatter, Claude Code mis-loaded them as junk `pt-doots:reviews:*` agents. Never put logs under `agents/`.

**Editing mechanics:** this is the inline dev checkout (`pt-doots@inline`); edits go live on the next session reload, no reinstall. Work on `main`.

## How to tune agent behavior

When the user asks to change how a pt-doots agent reviews, drafts, or
behaves, the answer is **always an overlay file in user memory**, never
an edit to the plugin's agent definitions or bundled profiles.

The plugin tree is upstream code. User tweaks live in user memory so
they survive `git pull` and don't get clobbered by plugin updates.

### Overlay path

`~/.claude/projects/{project}/memory/feedback_{agent-slug}_<topic>.md`

Where:
- `{project}` is the user's project memory dir (e.g.
  `-Users-parker-workspaces-plextrac`)
- `{agent-slug}` is the agent name in kebab-case
  (`voice`, `code-reviewer`, `scrum-master`, etc. — match what the agent
  already looks for, or pick a sensible slug for new agents)
- `<topic>` is whatever the user wants to call this tweak

Examples:
- `feedback_voice_engineer_textbook.md` — voice-stylist banned phrases
- `feedback_code_reviewer_strict_zod.md` — code-reviewer rule addition
- `feedback_scrum_master_always_standard.md` — scrum-master workflow tweak

### Rules

1. **Never edit `pt-doots/agents/*.md` or `pt-doots/agents/voice-stylist/profile.md` to add user preferences.** Those are the plugin's bundled defaults. User changes belong in user memory.

2. **Write the overlay file directly.** Don't ask the user to do it. They asked you to make the change; the overlay file IS the change.

3. **Tell the user where you put it.** "Saved the rule to `~/.claude/projects/{project}/memory/feedback_<agent>_<topic>.md`" so they can grep / edit / delete later.

4. **If the agent already has overlay-loading wired in** (voice-stylist does), the overlay takes effect the next invocation. **If it doesn't yet**, either inline the overlay content into the agent's spawn prompt for one-off use, OR add overlay-loading to the agent's body if the tweak is permanent (see `OVERLAYS.md` for the pattern).

5. **Bundle changes are NOT user changes.** If a tweak is universal good practice (not specific to one user's style or one repo's quirks), it belongs in the bundle profile or agent definition, not user memory. When in doubt, ask the user before writing it as a user overlay.

### When in doubt

Re-read `pt-doots/OVERLAYS.md`.
