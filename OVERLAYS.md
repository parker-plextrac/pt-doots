# Overlays

pt-doots agents are tuned via **overlay files** in user memory, not by editing the plugin tree. This keeps personal preferences upgrade-safe — `git pull` on the plugin never clobbers your tweaks.

## Where overlays live

`~/.claude/projects/{project}/memory/feedback_{agent-slug}_<topic>.md`

For Parker's setup that's:

`~/.claude/projects/-Users-parker-workspaces-plextrac/memory/feedback_<agent>_<topic>.md`

The `feedback_` prefix marks the file as a user feedback memory; the `{agent-slug}` segment routes it to a specific agent.

## How to add one

You usually don't have to. When you tell Claude "make voice-stylist stop using the word `derive`," Claude writes the overlay file for you and reports the path back.

If you want to add one by hand:

1. Pick the agent slug (`voice`, `code-reviewer`, `scrum-master`, etc.)
2. Create `~/.claude/projects/{project}/memory/feedback_{agent-slug}_<topic>.md`
3. Add YAML frontmatter:
   ```
   ---
   name: <short title>
   description: <one-line — what this overlay does>
   type: feedback
   ---
   ```
4. Write the rule below. Format depends on the agent; see existing overlays for patterns.

## Which agents support overlays

| Agent | Overlay-loaded? | Pattern |
|---|---|---|
| voice-stylist | Yes | Globs `feedback_voice_*.md`, `feedback_no_em_dashes.md`, `feedback_review_voice.md`, `feedback_review_comment_prefixes.md`, `user_voice_profile.md` |
| All others | Not yet — opt-in | Add overlay-loading via the pattern below when a concrete tuning need arises |

Most agents (researcher, implementer, test-writer, the QA reviewers) take structured inputs and produce structured outputs — they're tuned by code patterns and the plan, not by personal style. Wiring overlay loading into them is pay-as-you-go.

## How to add overlay support to a new agent

In the agent's body (`pt-doots/agents/<agent>.md`), add a "User overlay" section near the top of the instructions:

```
## User overlay

Before applying your standard logic, run ONE Glob:

`~/.claude/projects/*/memory/feedback_<agent-slug>_*.md`

Then read every match in a single parallel batch. Silently skip 404s.
Apply overlay rules on top of your defaults; overlays win on conflict.

If the Glob returns zero matches, proceed with defaults. Do not retry
or search elsewhere. Bundle-only is a valid configuration.
```

Two-tool-message contract: one Glob, one parallel Read batch. No second discovery pass.

## Why this design

The plugin is checked into a shared repo; user preferences are not. Mixing them invites three failure modes:

1. `git pull` clobbers personal tweaks
2. Personal tweaks leak across users (one engineer's "I hate the word X" becomes everyone's rule)
3. Bundle drift becomes invisible — no clean line between "we changed this" and "I changed this"

Separating bundle (universal, plugin-tree) from overlay (personal, user-memory) keeps that line bright.

## Examples

Browse `~/.claude/projects/-Users-parker-workspaces-plextrac/memory/feedback_voice_*.md` for working examples. The voice-stylist overlays are the most developed reference.
