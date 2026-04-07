---
name: bootstrap-team
description: >
  One-time command to bootstrap the PlexTrac agent team. Spawns the Team Manager
  to create each agent in the roster, with user approval before each creation.
  Run once after installing the plugin. Triggers: "bootstrap team", "bootstrap agents",
  "create the team", "/bootstrap-team".
---

# Bootstrap Team — Agent Roster Setup

One-time setup command that spawns the Team Manager to create each agent in the roster.

## Pre-flight

1. Verify the Team Manager agent exists:
   ```bash
   test -f plugins/plextrac/agents/team-manager.md && echo "OK" || echo "MISSING"
   ```
   If missing, tell the user: "Team Manager agent not found. The plugin may not be installed correctly."

2. Check if roster already exists (more than just team-manager.md in agents/):
   ```bash
   ls plugins/plextrac/agents/*.md | grep -v team-manager | head -1
   ```
   If agents exist, ask: "Agent roster already exists. Re-bootstrap will recreate all agents. Continue? (yes/no)"

3. Verify the agent teams environment flag is enabled. Check if `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` is set to `1` in the current session environment. If not set, tell the user:

   > Agent teams require `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` to be set.
   > Add this to your `~/.claude/settings.local.json`:
   > ```json
   > {
   >   "env": {
   >     "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"
   >   }
   > }
   > ```
   > Then restart Claude Code and run `/bootstrap-team` again.

   Then stop — do not proceed without the flag.

## Bootstrap Sequence

The Team Manager creates agents one at a time. For each agent:

1. **Spawn Team Manager** (foreground, `name: "team-manager"`) with task: "Propose the next agent for the roster. Here is the current roster: {list agents/ directory}. The roles still needed are: {list missing roles from the expected roster}."

2. **Team Manager returns a PITCH** with model, tools, role, boundaries, and rationale.

3. **Print the pitch to the user:**
   ```
   ┌─────────────────────────────────────────────────┐
   │ Team Manager Pitch: Create "{agent-name}"        │
   │                                                   │
   │ Model: {model}                                    │
   │ Tools: {tools}                                    │
   │ Role: {role}                                      │
   │ Does NOT: {boundaries}                            │
   │ maxTurns: {maxTurns}                              │
   │                                                   │
   │ Rationale: {rationale}                            │
   │                                                   │
   │ Approve? (yes / no / modify: "change to haiku")   │
   └─────────────────────────────────────────────────┘
   ```

4. **Wait for user approval.** If modified, pass modifications to Team Manager.

5. **Spawn Team Manager** (foreground, `name: "team-manager"`) with task: "Create the {agent-name} agent with these specifications: {approved pitch + any modifications}. Write the agent file to `agents/{agent-name}.md` and the review log to `agents/reviews/{agent-name}.md`."

6. **Team Manager creates the files and returns confirmation.**

7. **Repeat for all 8 agents:** scrum-master, researcher, developer, test-writer, code-reviewer, acceptance-qa, edge-case-qa, documentarian.

## Self-Evaluation

After all agents are created, spawn Team Manager (foreground, `name: "team-manager"`) one more time with task: "Self-evaluate your own definition. Read all the agents you just created. Is there anything about your own system prompt that should be improved now that you've seen the full roster in context? If yes, update your own file."

## Completion

After bootstrap:

1. List all created agents with their models:
   ```
   Agent Team — Bootstrap Complete

   ✓ team-manager (opus)
   ✓ scrum-master ({model})
   ✓ researcher ({model})
   ✓ developer ({model})
   ✓ test-writer ({model})
   ✓ code-reviewer ({model})
   ✓ acceptance-qa ({model})
   ✓ edge-case-qa ({model})
   ✓ documentarian ({model})

   Review the agents in plugins/plextrac/agents/ and commit when ready.
   ```

2. Suggest committing: "Ready to commit the full roster? (yes/no)"
