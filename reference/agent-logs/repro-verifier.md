# repro-verifier — Performance Log

## 2026-08-07 — Backfilled creation record (roster audit)
- **This log did not exist until now.** The agent had been running with no recorded justification
  for its config, while retired `developer` still had a log. The 2026-05-07 audit made
  team-manager responsible for preventing exactly this drift, so this is a governance gap being
  closed, not a change.
- Role: proves or refutes static reviewers' findings by writing and running reproduction scripts,
  and grounds them by running the repo's own gates. Verdicts: Confirmed / Proven-safe / Inconclusive.
- Model: sonnet, effort high, maxTurns 60, tools Read Grep Glob Bash Write.
- Config rationale (reconstructed): 60 turns because it builds, runs, and iterates on real scripts
  rather than reading. `Bash` is the whole point of the agent. `Write` is the one thing worth
  watching — it is the only reviewer-side agent holding it — and it is scoped by prompt to a named
  scratch directory, never the repo. That scoping is prompt-level, not tool-level; if it ever
  writes outside its scratch dir, that is the moment to reconsider.

## 2026-08-07 — Two runs recorded, highest value per run on the roster
- **IO-2375**: confirmed the orphaned-pending-row finding AND proved the proposed fix would
  silently no-op (`mark_failed` gates on `status='processing'`, the row was `pending`), and refuted
  the critical finding's reachability claims. Prevented both a wasted fix attempt and a wrong
  finding being posted.
- **PR #19 (IO-2373)**: confirmed all 3 selected findings by execution — a mutation test proving
  two unit tests could not detect a router ignoring its injected subject, a 3x POST run showing row
  counts 0/1/2/3 all stuck `pending`, and a real end-to-end run with the production handler showing
  `status='completed'` on an unparsed file. Also re-ran all three gates. Reverted its mutation and
  proved the worktree clean.
- Both runs were the highest-value agent of their session. Recommendation from the audit: make it
  routine on any ticket with runtime behavior rather than occasional. Static reviewers cannot see
  runtime gaps — on IO-2375 six reviewers plus 222 tests missed a 500 that one smoke run found.

## 2026-08-17 — Added the "Differentials" section (bundle change, universal practice)
- **Trigger, from a real run on IO-2369 / PR #197.** A reviewer challenged a change with "cases that
  cannot be generated in CKEditor but would break after your change and not before." The agent ran a
  before/after matrix in the changed context only and reported "the reviewer is right, 7 regressions."
  That answer was reversed an hour later, to "23 of 23 pre-existing, 0 new," but only because the
  orchestrator went back and explicitly asked for a control cell the agent had not thought to run.
- **The gap:** the agent answered *did behavior change* (yes) when the question that mattered was
  *is this failure new* (no). Without the control, its first report was a misleading half-answer that
  conceded a point that was not true, and the reversal read to the human as agents contradicting
  each other.
- **The fix:** a `## Differentials` section defining the four-cell A/B/C/D matrix, naming C
  (pre-existing context, before the change) as the deciding cell, requiring bucket counts up front,
  and requiring the "it's pre-existing code" premise to be PROVEN by occurrence-count on both
  checkouts rather than accepted from a commit message. An extraction and a copy-paste both report as
  "semantically identical"; only the count distinguishes them, and a 1→2 count means the change
  duplicated a bug rather than moving one.
- Also added: enumerate failing shapes exhaustively before naming a number. A separate run in the
  same session undercounted ("three shapes") and the missing cases surfaced after the summary had
  already gone out.
- **Placed in the bundle, not a user overlay**, per CLAUDE.md rule 5 — this is how the job should be
  done, not one user's preference.
