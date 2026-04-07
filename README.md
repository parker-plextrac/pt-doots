# pt-doots

Parker's PlexTrac Claude Code plugin — orchestrated ticket workflows, agent teams, PR dashboard, and integration scaffolding.

## Prerequisites

- [PlexTrac agent-skills plugin](https://github.com/PlexTrac/agent-skills) installed (provides `/verify`, `/logs`, etc.)
- Agent teams enabled: `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` in `~/.claude/settings.local.json`
- MCP servers configured (GitHub, Jira, Confluence) — run `/setup` from agent-skills

## Commands

| Command | Description |
|---------|-------------|
| `/pt-doots` | Full Jira ticket workflow — research, plan, implement, test, QA, commit |
| `/prs` | PR dashboard and review workflow |
| `/bootstrap-team` | One-time agent roster setup |
| `/team-audit` | Agent roster health review |
| `/new-integration` | Scaffold a new EM integration with sub-agents |

## Install

```bash
claude --plugin-dir /path/to/pt-doots
```
