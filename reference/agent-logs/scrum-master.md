# scrum-master — Performance Log

## 2026-04-06 — Created (haiku)
- Role: Read-only workflow advisor — classifies tickets and recommends workflow type (standard/lightweight/docs-only/custom)
- Model rationale: Task is classification and structured output based on signals in the text — no deep reasoning or code analysis needed. Haiku is sufficient.
- Effort: medium
- Tools: Read Grep Glob (read-only — no file modification)
- disallowedTools: Write Edit Bash
- permissionMode: dontAsk
- maxTurns: 8

## 2026-05-07 — Removed vestigial `disallowedTools` field (CHANGE 5)
- What changed: Frontmatter `disallowedTools: Read Write Edit Bash Grep Glob Agent` removed.
- Why: `learned-patterns.md` lines 42-45 documents that `disallowedTools` is NOT enforced by the agent teams framework. IO-2158 confirmed this 3 times in a single session — the SM had `disallowedTools` set but still made 16 tool calls. The `tools` whitelist (or omitting `tools` entirely with `maxTurns: 1`) is the actual enforcement. The field was misleading and signaled false safety. Other agents have the field stripped via the same audit (re: change 5 batch).

## 2026-05-07 — Logging silent maxTurns drift (CHANGE 4)
- Drift observed: maxTurns 8 → 1 (no prior dated entry). Justified by the IO-2158 tool-strip fix (learned-patterns.md lines 60-63: classifier agents work best at maxTurns: 1) but never logged. Counted as silent drift.
- Action: This entry retroactively documents the change. No rollback — the value is correct.

## 2026-05-07 — Documentarian polarity flip (CHANGE 6)
- What changed: Documentation classifier section rewrote. Default polarity is now "yes"; only set "no" when the ticket has zero documentation surface (pure refactors with no behavior change, test-only changes, etc.). Replaces the prior Confluence-only signaling.
- Why: Roster audit found documentarian was being skipped on tickets that ship behavior changes. Default-yes makes the agent auto-fire for the majority case.

## 2026-07-20 - Escalation/Defect to standard heuristic (roster audit)
- Added to the bundled agent body (agents/scrum-master.md): a customer escalation (ES-prefixed ticket key, e.g. ES1-1677) or a Defect-type ticket now recommends standard by default and must not be classified lightweight. Added as a Standard Workflow Signal plus a caveat on the Lightweight signals ("a customer-reported defect is never lightweight even with a clear root cause").
- Placement rationale: scrum-master has no tools (maxTurns:1, no Read), so it cannot load a user overlay at runtime; an overlay would never reach it. The rule is workflow-correctness grounded in a real misclassification, not a personal style preference, and the agent body already carries PlexTrac-specific routing (parser/exporter to standard). Per pt-doots/CLAUDE.md rule 5 (bundle changes for universal good practice) this belongs in the agent definition. Parker (via team-lead) explicitly authorized the bundle edit.
- Evidence: ES1-1677 (a customer escalation) was classified lightweight; the orchestrator had to override to standard.

## 2026-08-07 — Reverted the tools/maxTurns change (roster audit; config correctness)
- `maxTurns: 4` → `1`, and the `tools: Read Grep Glob` field removed entirely. Note `tools: ""`
  does NOT mean no tools; the field must be absent.
- **Why reverted.** Those settings were added to fix agents "returning no output", which was later
  proven to be a harness delivery bug — the agents had completed their work and the text was lost in
  transit. So the config addressed a non-cause. Assessed on its own merits, independent of the dead
  theory, it fails three ways: it contradicted this agent's own body ("CRITICAL — You Have No Tools
  ... You cannot and should not explore the codebase"), it contradicted `commands/pt-doots.md`
  (still describing it as "haiku, 1 turn"), and it re-opened a measured failure — on IO-2158 it spent
  every turn reading parser source and returned no recommendation, where at 1 turn with no tools it
  produced a clean WORKFLOW PLAN in 11.5s with zero tool calls.
- The old config is proven: 2 clean runs at haiku/1-turn (IO-2349 ~12s, IO-1622 ~24s).
- Also closed a real gap the audit surfaced: body step 5 told this agent to "read workflow history
  and learned patterns", which it cannot do with no tools. Now states the orchestrator inlines them.
- Routing quality is not the problem: 3 of 4 recommendations correct, and the one miss (ES1-1677
  classified lightweight for a customer escalation) was already patched in the body on 2026-07-20.
