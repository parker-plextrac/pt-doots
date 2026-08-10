# documentarian — Performance Log

## 2026-04-06 — Created (haiku)
- Role: Documentation agent that updates repo docs (READMEs, reference docs, inline comments) and proposes Confluence wiki changes after code changes are merged
- Model rationale: Task is reading changed files, understanding what changed, and updating documentation to match — this is mostly reading and summarizing with light writing. The answer is in the code, no deep reasoning needed. Haiku is sufficient for accurate doc updates.
- Effort: medium
- Tools: Read Write Edit Grep Glob + Confluence MCP (conf_get, conf_post, conf_put)
- disallowedTools: Bash
- permissionMode: auto — Confluence writes require user approval via [CONFLUENCE] output sections, but repo doc writes are auto-approved since the agent only touches documentation files
- maxTurns: 15
- Key design decisions:
  - Confluence writes gated by [CONFLUENCE] approval sections in output, not by tool restrictions — the agent has the tools but the system prompt enforces the approval workflow
  - No Bash access — doc updates do not require shell commands
  - No isolation (worktree) — runs after all code changes are merged, so no conflict risk
  - Cannot self-initiate doc creation — only executes when explicitly tasked by Scrum Master workflow plan or Team Manager audit
  - Cannot modify CLAUDE.md (Developer's job), agents/, commands/, or .claude-plugin/ directories

## 2026-05-07 — Scope expansion + priority order + research handshake (CHANGE 6 + CHANGE 7)
- What changed:
  - System prompt rewritten with an explicit **Repo Documentation — Priority Order**: nested CLAUDE.md (highest) → repo READMEs → inline JSDoc/docstrings → Confluence (lowest, only when explicitly tasked).
  - Documentarian is now the verifier of nested CLAUDE.md files post-change. It still does NOT modify production CLAUDE.md authored by the Developer in flight, but it walks every changed directory and fixes stale claims / creates missing module-level CLAUDE.md when shape changed. (Note: this is consistent with the prior "do not modify CLAUDE.md files" rule when read as "do not author them as a substitute for the Developer." Audit follow-up: re-read the prohibition wording in a future pass to confirm the verifier role isn't ambiguous.)
  - Added handshake with Researcher: documentarian now reads `notes/{TICKET}/research.md` "Related Documentation → Update candidates" first and verifies each candidate against the merged code before doing anything else. Empty section means the researcher confirmed nothing needs updating.
  - `reference/workflow.md` Step 4e updated to mirror the priority order and the default-yes documentation polarity.
- Why: Roster audit found documentation was being skipped on tickets shipping behavior changes, and when it ran the order was unclear (often started at READMEs and never visited nested CLAUDE.md). Pairing this with researcher reconnaissance (CHANGE 7) gives the documentarian a candidate list instead of cold-walking every changed file.
- Risk: priority-order rewrite is in tension with the historical "do NOT modify CLAUDE.md files" boundary. The intent has always been "do not author CLAUDE.md *during* implementation — that is the Developer's job"; the documentarian is the post-merge verifier. Open question flagged for next audit: tighten the wording in the agent prompt so the boundary and the priority order are unambiguous.

## 2026-08-07 — Retargeted as verifier; mechanical trigger; CLAUDE.md contradiction resolved
- **The problem.** 1 fire in 12 sessions. Not a classifier failure: scrum-master correctly set
  `Documentation: yes` on both IO-2349 and IO-1622 and the orchestrator skipped it anyway. Five
  sessions give the same reason — the implementer already wrote the docs. This agent was
  *displaced*, not under-triggered.
- Distinguished from retired `developer`, which was a true duplicate. The 2026-05-07 role
  (post-merge verifier of nested CLAUDE.md and README claims) is real work nobody does today.
  Evidence it is needed: a maintainer shipped a commit titled "Update stale app.py citations in
  docs/shoulds" because doc line references had drifted against moved code. Done by hand because
  this agent never fired.
- **Changes.** (1) Job restated: primarily a VERIFIER of claims the implementer wrote, not an author.
  (2) Trigger made **mechanical** in `commands/pt-doots.md` — any `.md`, README, docstring, or block
  comment in the diff fires it, no judgment call, because the 11-session failure was the orchestrator
  exercising discretion and skipping. (3) Resolved the contradiction this log flagged twice and never
  closed: the body forbade touching CLAUDE.md "at any level" while also making stale-CLAUDE.md repair
  its highest priority. Now explicit — nested module-level CLAUDE.md is in scope for stale-claim
  fixes, the repo-root CLAUDE.md is not, because that is a standards document rather than a
  doc-accuracy target.
- Retained on haiku. Nearly free, and a wrong CLAUDE.md misleads every future agent session.

## 2026-08-10 — Concision pass (comment bloat + PR size)
- Trigger: a human reviewer called the workspace's PRs "a bit out of control" and asked to "fix
  comments and shit." Root cause was a rule interaction, not a missing rule: the overlays said
  comments must explain a non-obvious why, which every bloated comment passed, while separate
  no-size-caps guidance was being read across from code to prose. Fixed across the overlays, the
  implementer (write-time rule + audit counts), the orchestrator's planning step and commit gate,
  and the reviewers.
- This agent's share of that pass is recorded in the same commit. The shared test, used verbatim
  everywhere so it stays one idea: **would omitting this line let someone make a wrong change?**
  If not, it is commentary, not documentation.
- The other half is scope: PR size is decided at planning, not at review, so the planning step now
  estimates the file surface out loud and offers a split, and the commit gate asks whether every
  commit traces to the ticket in the branch name.
