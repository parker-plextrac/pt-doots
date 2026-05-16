# pt-doots — Operating Notes for Claude

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
