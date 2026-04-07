# PlexTrac Workflow

Personal Claude Code plugin for orchestrated PlexTrac ticket workflows.

## Prerequisites

- [PlexTrac agent-skills plugin](https://github.com/PlexTrac/agent-skills) installed (provides `/verify`, `/logs`, etc.)
- Agent teams enabled: `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` in `~/.claude/settings.local.json`
- MCP servers configured (GitHub, Jira, Confluence) — run `/setup` from agent-skills

## Commands

| Command | Description |
|---------|-------------|
| `/plextrac-work` | Full Jira ticket workflow — research, plan, implement, test, QA, commit |
| `/bootstrap-team` | One-time agent roster setup |
| `/team-audit` | Agent roster health review |
| `/new-integration` | Scaffold a new EM integration with sub-agents |

## Install

```bash
claude plugin add /path/to/plextrac-workflow
```
