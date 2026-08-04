# team-manager — Performance Log

## 2026-04-06 — Created (opus)
- Role: Agent architect — designs, creates, improves, and tunes the PlexTrac agent team
- Model rationale: Requires novel reasoning about agent design, cross-system architectural thinking
- Tools: Read Write Edit Bash Glob Grep (full access to create/edit agent files)
- maxTurns: 30
- Note: Hand-crafted — this is the one agent not created by Team Manager

## 2026-05-07 — Telemetry pipeline wired
- Telemetry pipeline wired into `commands/pt-doots.md` and `reference/workflow.md`. Pre-flight in `commands/team-audit.md` relaxed from hard-error to warning. Schema documented at `reference/metrics-format.md`. Future audits will have run-count, duration, and fix-cycle data.

## 2026-05-07 — /prs implementer/developer precedence audit
- Verified the `/prs` flow does NOT spawn any implementation-style agent for fix-up commits or addressing review findings. Finding: **C (agent-agnostic)**.
- `commands/prs.md` only spawns read-only reviewers: `pt-doots:edge-case-qa`, `pt-doots:acceptance-qa`, `pt-doots:researcher`, `pt-doots:code-reviewer`, `pt-doots:code-smells-reviewer`, `pt-doots:test-reviewer`, and (re-review path) `pt-doots:re-reviewer`. No `developer` or `implementer` spawn anywhere.
- `agents/re-reviewer.md` mentions "developer" only in the SendMessage Communication Rules example (Fast Tier) — talking to a hypothetical teammate, not spawning one. No change needed.
- Author fix-ups happen on the PR side (the human author addresses comments after we post). The /prs flow is purely observe-and-comment, so the implementer/developer precedence rule from `commands/pt-doots.md` does not apply here. No edits made. Logging this so future audits don't re-investigate.

## 2026-05-08 followup to 2026-05-07 audit
- Extended inline-diff prompt fix to `code-smells-reviewer` and `test-reviewer` (both were missed in yesterday's pass — they still passed `{list from implementation}` and required Read-time file exploration).
- Wired `{INLINED_DIFF}` substitution into `commands/pt-doots.md` Step 4c via a new "Step 4c — Inline-Diff Substitution Contract (MANDATORY)" subsection. Contract: orchestrator runs `git diff main...HEAD -- {files}` before fan-out, populates both `{INLINED_DIFF}` and `{INLINED_FUNCTION_BODIES}` placeholders, and passes fully-rendered prompts to each reviewer. Explicit guardrail: "the orchestrator reads files / runs git, NOT the reviewer agents."
- For `test-reviewer` the diff must include both test files AND their corresponding production files.
- Inline-context discipline now fully restored across all 5 quality-gate reviewers (`code-reviewer`, `acceptance-qa`, `edge-case-qa`, `code-smells-reviewer`, `test-reviewer`).

## 2026-05-15 — Overlay convention documented

Created `pt-doots/CLAUDE.md` and `pt-doots/OVERLAYS.md`; added a "Tuning agent behavior" pointer to README.md.

Background: voice-stylist had overlay support but no plugin-wide convention or documentation explained the bundle-vs-overlay model. Risk: users (or Claude in future sessions) edits agent files directly to add personal preferences, which then get clobbered on `git pull`.

Now documented:
- Convention: `~/.claude/projects/{project}/memory/feedback_{agent-slug}_<topic>.md`
- Rule: never edit plugin tree for personal tweaks
- Opt-in per-agent wiring (voice-stylist has it; others add it when needed)
- Pattern for adding overlay support to a new agent (single Glob + parallel Read batch)
