# prove module

Two-pass discrimination runner that proves the export fix actually changes ToC heading levels.

## Key Files
- `prove.ts` — `runProve(cfg, spec)` — orchestrates fix-branch and main-branch export passes; returns `ProveResult`

## Flow
1. Capture `originalBranch` from `cfg.exportRepoPath` via `git rev-parse --abbrev-ref HEAD`
2. Pass 1: run the full UI export flow on the current (fix) branch; record `fix.pass`
3. `git switch` the export repo to `main`; log the switch to stdout
4. Pass 2: run the same UI export flow; catch any crash as `pass=false`; restore in `finally`
5. Assert `fix.pass && !main.pass` → `discriminates`

## Key invariants
- `runSinglePass` catches all errors internally; it never throws — crashes become `pass=false, crashMessage="..."`
- Branch restore is in a `finally` block inside `runMainSideWithRestore`, separate from the `switch-to-main` call, so restore runs even if the pass-2 export crashes
- `git switch` uses `execFileSync` with args as an array (no shell, no injection risk)
- A main-side crash (Export Failed, no PDF, UI error) counts as `!main.pass` — see task spec

## Expected main-side behavior
On `main`, the export service produces ToC with collapsed levels (h4 at depth 2 instead of 3), OR the export crashes/fails. Both count as `main.pass=false`. The harness discriminates when `fix.pass=true && main.pass=false`.

## Dependencies
- Depends on: `../config.ts`, `../spec/testSpec.ts`, `../fixture/fixtureBuilder.ts`, `../browser/run.ts`, `../verify/pdfTocParser.ts`, `../verify/diff.ts`
- Depended on by: `../cli.ts` (--prove flag)
