# voice-stylist — Performance Log

## 2026-05-11 — Created (haiku)
- Role: Final voice pass on human-facing drafts (PR comments, Slack, Jira). Rewrites prose into Parker's voice, leaves code untouched.
- Model rationale: haiku. Task is mechanical text substitution against a fixed rule list. No reasoning about code, no tracing call paths, no architecture. The rules are in the prompt; the answer is in the input text. Sonnet would be overkill and would risk over-editing.
- Effort: low. Routine, well-defined transform.
- Tools: Read. Pure transform — input is in the prompt. Read kept available only for rare cases where the caller references a draft file path. No Write, no Bash, no Grep — the agent must not modify anything on disk.
- permissionMode: dontAsk. Read-only and idempotent; no need to prompt.
- maxTurns: 2. One pass is the norm; second turn allowed only if the agent self-checks against the rule list.

### Design tightenings applied (per Parker, pre-ship)
1. Code fences AND inline backticks pass through byte-for-byte unchanged. Explicit example baked into the prompt.
2. No "prefix swap" notification line. Agent silently corrects bad prefixes and returns only the clean rewrite. One output shape, no parsing overhead for the caller.
3. No-op rule: if the draft is already clean, return it byte-for-byte unchanged. Prevents haiku from "improving" clean drafts and drifting voice.

### Wiring notes for `/prs`
- Plug voice-stylist in as the FINAL step after every reviewer agent (code-reviewer, code-smells-reviewer, test-reviewer, re-reviewer) produces draft inline comments.
- Caller passes the raw draft as the user message; agent returns the cleaned draft. No JSON, no envelope.
- For multi-comment review batches, call voice-stylist once per comment rather than passing the whole batch — keeps the no-op rule clean per-comment and avoids cross-comment bleed.

## 2026-05-11 — Switched to two-layer model (bundle + user overlay)

- Refactored `voice-stylist.md` from a self-contained inlined prompt to a layered loader that reads a bundled profile plus any user overlay files.
- New bundle file: `agents/voice-stylist/profile.md`. Ships with the plugin. Carries the universal good-prose rules: em-dash ban, universal banned phrases (`coalesce`, `trigger` as verb, `bypass`, `soft handoff`, `leverage`, `utilize`, `facilitate`, `in order to`, `walk the lines`, `where it shakes out`), Anglo-Saxon verb mappings, prefix scheme with severity mapping, code-fence sanctity, no-op rule, universal structural rules (short sentences, no preamble, no trailing disclaimers, contractions OK, review comment structure).
- User overlay loading via Glob over `~/.claude/projects/*/memory/voice_*.md`, `user_voice_profile.md`, `feedback_voice_*.md`, `feedback_review_voice.md`, `feedback_review_comment_prefixes.md`, `feedback_no_em_dashes.md`. Overlay wins on direct conflict; otherwise rules are unioned.
- Tool change: added `Glob` alongside `Read`. Still no Write, no Bash. maxTurns bumped from 2 to 3 to cover bundle-read + overlay-glob + rewrite.
- Fallback: if no profile is loadable (no bundle, no overlay), the agent returns the input unchanged. Explicit instruction not to invent voice rules from training data.
- Why: the original prompt was implicitly Parker-specific because it relied on user-memory files that don't ship with the plugin. Bundling universal rules makes the agent work for any user out of the box. User overlay still customizes via memory files.
