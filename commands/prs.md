---
name: prs
description: >
  PR dashboard and review workflow for PlexTrac repos.
  Triggers: "/prs" (dashboard), "/prs <github-pr-url>" (direct review).
argument-hint: "[pr-url]"
---

# PRs — PlexTrac PR Dashboard & Review

Two modes based on arguments:
- **No arguments** → Dashboard mode (show all open PRs)
- **GitHub PR URL** → Direct Review mode (multi-agent code review)

**GitHub user:** `parker-plextrac`

**QA engineer:** `bwilson-pt` (Brandon Wilson — his PRs are prefixed with `QA-`)

**Target repos:**

| Repo | Slug |
|------|------|
| product-core-backend | `PlexTrac/product-core-backend` |
| product-core-frontend | `PlexTrac/product-core-frontend` |
| product-services-export | `PlexTrac/product-services-export` |
| product-services-mcp | `PlexTrac/product-services-mcp` |
| agent-skills | `PlexTrac/agent-skills` |

---

## Step 0: Resolve Workspace Path

The PR review state files live at `{WORKSPACE}/notes/pr-reviews/`. Resolve `WORKSPACE` in this order:

1. **Read `~/.plextrac-stack.json`** — use the `workspace` field:
   ```bash
   cat ~/.plextrac-stack.json 2>/dev/null
   ```
2. **Check `PLEXTRAC_WORKSPACE` env var** — if the config file doesn't exist.
3. **Fall back to cwd** — walk up from the current working directory looking for a directory containing `product-core-backend/` (the PlexTrac workspace marker).

If none resolve, tell the user:

> Could not determine your PlexTrac workspace path. Run **/stack-up** first (it saves your workspace path), or set the `PLEXTRAC_WORKSPACE` environment variable.

Then stop.

Store the resolved path as `WORKSPACE`.

---

## Parse ARGUMENTS

Examine `$ARGUMENTS` (the text after `/prs`):

| Input | Mode |
|-------|------|
| *(empty)* | **Dashboard** |
| URL matching `https://github.com/PlexTrac/*/pull/*` | **Direct Review** — extract `owner`, `repo`, and `pr_number` from the URL |
| Anything else | Show usage: `/prs` for dashboard, `/prs <github-pr-url>` to review a specific PR |

---

## Mode 1: Dashboard

### Step 1: Data Gathering

Make **parallel** GitHub MCP calls across all 5 target repos. For each repo:

```
mcp__github__list_pull_requests(owner: "PlexTrac", repo: "{repo_name}", state: "open")
```

From the results, split into four lists (apply in order, **deduplicate** — a PR appears in only the first list it qualifies for):
- **Your PRs**: PRs where `user.login` is `parker-plextrac` (no age filter — show regardless of age)
- **Requesting Your Review**: PRs where `requested_reviewers` includes `parker-plextrac` (no age filter)
- **QA — Brandon Wilson**: PRs where `user.login` is `bwilson-pt`, **created within the last 40 days**
- **IO Tickets (All Open)**: PRs where the title or `head.ref` starts with `IO-`, **created within the last 40 days**

The 40-day freshness filter on QA and IO sections keeps the dashboard focused on actively in-flight work. Older PRs are usually abandoned and just add noise.

For each PR in **Your PRs**, **QA — Brandon Wilson**, and **IO Tickets (All Open)**, also fetch CI status:

```
mcp__github__get_pull_request_status(owner: "PlexTrac", repo: "{repo_name}", sha: "{head.sha}")
```

For each PR in **QA — Brandon Wilson** and **IO Tickets (All Open)**, also fetch review state to detect if Parker has reviewed:

```bash
/opt/homebrew/bin/gh api "repos/PlexTrac/{repo_name}/pulls/{pr_number}/reviews" --jq '[.[] | select(.user.login == "parker-plextrac") | .state] | last // "NONE"'
```

This returns Parker's most recent review state (`APPROVED`, `COMMENTED`, `CHANGES_REQUESTED`) or `NONE` if he has not reviewed.

Launch all these calls in parallel.

**If a repo call fails**: note it and continue with the others.
> "Could not fetch PRs from {repo} (API error). Showing results from other repos."

**If no PRs found anywhere**:
> "No open PRs found across PlexTrac repos."
Then stop.

### Step 2: Display Dashboard

Sort both sections with **IO-prefixed PRs first**. IO detection: PR title or branch name (`head.ref`) starts with `IO-`.

#### Your PRs

| # | Repo | PR | CI | Approvals | Comments | Days | Draft? |
|---|------|----|----|-----------|----------|------|--------|

Column definitions:
- **#**: Row number for easy reference (e.g. "review #1")
- **Repo**: Short repo name (e.g. `product-core-backend`)
- **PR**: `#{number} {title}` — truncate title to ~50 chars if needed
- **CI**: From status checks — `PASS` (all succeed), `FAIL` (any failed), `PENDING` (running), `—` (no checks)
- **Approvals**: `{approved}/{requested}` count
- **Comments**: Total count (`comments` + `review_comments` fields)
- **Days**: Days since `created_at` (e.g. `3d`, `14d`)
- **Draft?**: `DRAFT` if `draft: true`, empty otherwise

If no authored PRs: "No open PRs authored by you."

#### Requesting Your Review

| # | Repo | PR | Author | Files | IO? |
|---|------|----|--------|-------|-----|

Column definitions:
- **#**: Row number (continues from Your PRs numbering)
- **Repo**: Short repo name
- **PR**: `#{number} {title}`
- **Author**: `@{user.login}`
- **Files**: `changed_files` count
- **IO?**: `YES` if IO-prefixed, `no` otherwise

If no review-requested PRs: "No PRs requesting your review."

#### QA — Brandon Wilson

| # | Repo | PR | CI | Reviewed | Days | Draft? |
|---|------|----|----|----------|------|--------|

Column definitions:
- **#**: Row number (continues numbering)
- **Repo**: Short repo name
- **PR**: `#{number} {title}` (typically `QA-` prefixed)
- **CI**: `PASS` / `FAIL` / `PENDING` / `—`
- **Reviewed**: Parker's last review state — `APPROVED` / `COMMENTED` / `CHANGES_REQ` / `—` (not reviewed)
- **Days**: Days since `created_at`
- **Draft?**: `DRAFT` if `draft: true`, empty otherwise

If none: "No open PRs from Brandon."

#### IO Tickets (All Open)

| # | Repo | PR | Author | CI | Reviewed | Days | Draft? |
|---|------|----|--------|----|----------|------|--------|

Column definitions:
- **#**: Row number (continues numbering)
- **Repo**: Short repo name
- **PR**: `#{number} {title}`
- **Author**: `@{user.login}`
- **CI**: `PASS` / `FAIL` / `PENDING` / `—`
- **Reviewed**: Parker's last review state — `APPROVED` / `COMMENTED` / `CHANGES_REQ` / `—` (not reviewed)
- **Days**: Days since `created_at`
- **Draft?**: `DRAFT` if `draft: true`, empty otherwise

If none: "No open IO PRs."

### Step 3: Stale Review Cleanup

Check if `{WORKSPACE}/notes/pr-reviews/` exists. If it does, list `.md` files in it. For each file:

1. Parse the YAML frontmatter to get `owner`, `repo`, `pr`, and `status`
2. If `status` is not `posted`, call `mcp__github__get_pull_request` to check if the PR is now closed or merged
3. Collect filenames for any closed/merged PRs

If stale files found:
> "Found {N} stale review file(s) for closed/merged PRs ({filenames}). Want me to clean those up?"

If user says yes, delete the files. Otherwise continue.

### Step 4: Action Prompt

Present specific options:

> **What would you like to do?**
> - **Review a PR** — "review #1" or "review 8540"
> - **Check a failing build** — "what's failing on #1?"
> - **Show comments** — "show comments on #1"
> - **Refresh** — "refresh" to re-fetch the dashboard

**If the user picks "review #N":**
1. Look up the PR from the dashboard table by row number
2. If the PR is a draft: "This PR is still a draft. Want to review it anyway?"
3. If confirmed (or not a draft), proceed to **Mode 2: Direct Review** — use the `owner`, `repo`, and `pr_number` from the dashboard data directly (skip the URL parsing step in Mode 2, go straight to Step 1: Check for In-Progress Review)

**If the user picks "what's failing on #N":**
1. Call `mcp__github__get_pull_request_status` for that PR
2. Show the failing check names, their status, and URLs

**If the user picks "show comments on #N":**
1. Fetch **both** comment types in parallel:
   - `mcp__github__get_pull_request_comments` — inline review comments
   - `gh api repos/{owner}/{repo}/issues/{pr_number}/comments` — conversation comments
2. Merge and sort by date, show the last 10 with author, date, and body (truncated to ~200 chars)
3. Filter out bot comments (github-actions[bot], etc.) unless the user asks for them

**If the user says something unexpected**, handle it conversationally — these are the primary paths but don't be rigid.

---

## Mode 2: Direct Review

Parse the PR URL from `$ARGUMENTS`:
- Extract `owner` (e.g. `PlexTrac`), `repo` (e.g. `product-core-backend`), and `pr_number` (e.g. `8532`) from `https://github.com/{owner}/{repo}/pull/{pr_number}`

### Step 1: Check for In-Progress Review

Check if `{WORKSPACE}/notes/pr-reviews/{repo}-{pr_number}.md` exists.

If found, read the file and parse the YAML frontmatter:

- **If `status` is `findings_ready` or `drafting`** (in-progress prior session):
  1. Get the current PR head SHA via `mcp__github__get_pull_request`
  2. Compare with the saved `head_sha` from the file
  3. If they differ, count new commits:
     ```bash
     /opt/homebrew/bin/gh api repos/{owner}/{repo}/compare/{saved_sha}...{current_sha} --jq '.ahead_by'
     ```
  4. Present the resume prompt:
     > "Found an in-progress review for #{pr_number} from {date} ({N} new commits since then). Status: {status}. Resume where you left off, or start fresh?"
  5. If "resume": always run Step 2 (Context Gathering) first — this includes both worktree setup (2b) and PR metadata (2a). The worktree ensures agents run on the correct code without interfering with whatever branch the main checkout is on (the user may have a parallel session editing it). Then jump based on status: `findings_ready` → Step 5, `drafting` → Step 6. Skip Step 3 (the expensive agent work) since findings are already saved.
  6. If "fresh": proceed to Step 2

- **If `status` is `posted`** — the prior review was already sent. Compare current head SHA with the saved `head_sha`:
  - If they match: nothing has changed since the prior review.
    > "Already reviewed #{pr_number} on {date} — no new commits since then. Want to re-review anyway, or skip?"
    If user says skip, stop. If re-review anyway, proceed to **Step 1b: Re-review flow**.
  - If they differ: there are new commits since the prior review. Count them:
    ```bash
    /opt/homebrew/bin/gh api repos/{owner}/{repo}/compare/{saved_sha}...{current_sha} --jq '.ahead_by'
    ```
    Then present:
    > "Reviewed #{pr_number} on {date} — {N} new commits since then. Want to re-review (focused on the delta + verification of prior findings), full fresh review, or skip?"
    - "re-review" → proceed to **Step 1b: Re-review flow**
    - "fresh" → proceed to Step 2 as a brand-new review (the saved file's findings are ignored, but keep the file as historical record)
    - "skip" → stop

If no file found, proceed to Step 2.

### Step 1b: Re-review flow

This flow runs when a prior review is `posted` and the user wants a delta-focused re-review. The goal is to verify whether prior findings were addressed and flag NEW concerns introduced in the new commits — without re-running a full fresh review.

#### 1b.1: Gather re-review context

1. Run **Step 2 (Context Gathering)** in full — fetch PR metadata, files, comments, set up the worktree, fetch Jira context. This produces `{WORKTREE_DIR}` and the prior comment threads.
2. Capture the **delta diff** between the prior-reviewed SHA and current head, scoped to PR-relevant directories. Save to `/tmp/{repo}-{pr_number}-delta.patch`:
   ```bash
   git -C "$WORKTREE_DIR" diff {saved_sha}..HEAD -- {pr_top_level_dirs} > /tmp/{repo}-{pr_number}-delta.patch
   ```
   Determine `{pr_top_level_dirs}` from `mcp__github__get_pull_request_files` — group changed files by their top-level directory (e.g., `apps/plextracapi/src/domains/jira/module/`) and pass those paths to scope the diff.

3. Parse the GitHub PR comments to assemble **author replies** to each prior finding. For each saved finding, find the matching inline comment (by file:line proximity) and extract any `in_reply_to_id` replies from the author.

#### 1b.2: Spawn re-review agents in parallel

Launch THREE parallel agents:

**Agent 1 — Re-reviewer (verifier)** (`subagent_type: "pt-doots:re-reviewer"`)

Pass the agent:
- The full prior findings list (from the saved review file's "## Findings" table) with severity and original concern
- Author replies parsed from PR comments (file:line + reply text)
- `WORKTREE_DIR` path
- Delta diff path: `/tmp/{repo}-{pr_number}-delta.patch`

The agent returns a structured verdict per finding (Addressed / Partial / Not addressed / Pushback warrants accepting / Explicitly deferred) with current-state line citations. See `pt-doots:re-reviewer` agent definition for full output format.

**Agent 2 — Edge-case scan of the delta** (`subagent_type: "pt-doots:edge-case-qa"`)

Scope the prompt tightly: examine ONLY new code introduced in the delta. List the prior findings as "already raised — do not re-flag" so the agent doesn't duplicate them. Cap at 8 findings.

**Agent 3 — Test smell scan of the delta** (`subagent_type: "pt-doots:test-reviewer"`)

Only spawn if the delta includes test files. Scope to new tests added in the delta. Cap at 8 findings.

#### 1b.3: Consolidate and present

Show the user:
1. The verifier's per-finding verdicts (table format)
2. New concerns from edge-case + test reviewers (if any), filtered to high/medium severity
3. A net recommendation line — e.g., "PR is in good shape, ready for approving follow-up" or "1 unaddressed concern remains"

Then ask:
> "Want to walk through new findings one-at-a-time (proceed to Step 5b), drop a top-level approval comment, or skip?"

Approval shortcut: if the user says "approve" or "approve with classic," skip directly to Step 8 with `event: APPROVE` and body `🎺 💀 🤖`.

#### 1b.4: Update the saved review file

After posting (or skipping), update the saved review file in place:
- Set `re_reviewed_at: {ISO timestamp}`
- Set `re_review_outcome: approved` / `commented` / `skipped`
- Update `head_sha` to the current SHA
- Append a new `## Re-review {date}` section below the original findings, with the verifier's verdicts table

Do NOT delete or rewrite the original findings — keep the historical record intact.

Then proceed to Step 9 (clean up worktree).

### Step 2: Context Gathering

#### 2a: Fetch PR metadata (lightweight — runs first)

**Call 1 must run before anything else** — it provides `{head_ref}` (the PR branch name) needed by the worktree setup in Step 2b.

**Call 1:** `mcp__github__get_pull_request` — get PR title, description, author, base branch, head ref/branch name, head SHA, draft status

Store `{head_ref}` from the response's `head.ref` field. This is the branch the worktree will track in Step 2b.

Then launch these **in parallel** (they don't depend on Call 1's result):

**Call 2:** `mcp__github__get_pull_request_files` — get list of changed files with patch/diff content

**Call 3 (MCP — inline + review comments):**
- `mcp__github__get_pull_request_comments` — inline review comments
- `mcp__github__get_pull_request_reviews` — review submissions

**Call 4 (Bash — conversation comments):**
```bash
/opt/homebrew/bin/gh api repos/{owner}/{repo}/issues/{pr_number}/comments
```
This fetches **conversation comments** (issue-level). This is where most human reviewer feedback lives. Do NOT skip this — `get_pull_request_comments` only returns inline comments. This is a separate Bash call, not an MCP call.

**Call 5:** Extract the Jira ticket key from the PR title or branch name using regex `[A-Z]+-\d+` (e.g. `IO-2168`). If found:
```
mcp__atlassian__getJiraIssue(cloudId: "plextrac.atlassian.net", issueIdOrKey: "{ticket_key}", responseContentFormat: "markdown")
```
Extract: summary, description, acceptance criteria, and status.

#### 2a-backport: Detect Backport & Check Prior Reviews

After Call 1 returns, check if the PR's `base.ref` targets a release branch (e.g. `release/v3.0`, `release/v2.28`) rather than `main`. If so, this is a **backport**.

For backport PRs:

1. Extract the Jira ticket key from the PR title or branch name using regex `[A-Z]+-\d+`
2. Search `{WORKSPACE}/notes/pr-reviews/` for a prior review of the same work. Try these strategies in order (stop at first match):
   - **Ticket match**: scan review files whose `ticket` field matches the extracted ticket key
   - **Title match**: if ticket is "none" in review files, search for review files whose `title` contains the ticket key (e.g. a review file titled "add severity to synqly plugin" won't match, but one titled "IO-2191: fix severity" would)
   - **Author + recency match**: look for review files from the same `author` in the same `repo`, posted within the last 7 days — these are likely the original PR that's now being backported. Present as a candidate and ask user to confirm.
3. If a prior review is found, read it and present a summary:

   > **Backport detected** — this PR targets `{base_ref}` (not `main`).
   > Found a prior review for the same work: PR #{original_pr} ("{original_title}") reviewed on {date}, status: {status}.
   >
   > Prior findings:
   > {findings table from the original review file}
   >
   > Since this is a backport of already-reviewed code, you can:
   > - **Skip** — the code was already reviewed on the original PR
   > - **Quick diff** — compare the backport diff against the original to check for cherry-pick drift
   > - **Full review** — run the full multi-agent review anyway

4. If no prior review file is found, proceed with the full review but note "Backport detected (targets `{base_ref}`) — no prior review found for {ticket_key}" in the review header.

5. If the user chooses **Skip**, jump to Step 9 (clean up worktree). If **Quick diff**, do a lightweight comparison (no agents — just fetch both PR diffs and highlight differences). If **Full review**, continue to Step 2b as normal.

#### 2b: Set up isolated worktree (DEFAULT)

The user often has a parallel Claude session editing the main checkout. **Always review in an isolated worktree** so the main checkout stays on whatever branch they're working on. After Call 1 completes and `{head_ref}` is known:

```bash
# Resolve worktree path — keeps all review worktrees in one place
WORKTREE_DIR={WORKSPACE}/.worktrees/{repo}-{head_ref}

# Fetch the latest PR branch tip
git -C {WORKSPACE}/{repo} fetch origin {head_ref}

# Create the worktree (or reuse if it already exists from a prior review)
if [ -d "$WORKTREE_DIR" ]; then
    git -C "$WORKTREE_DIR" fetch origin {head_ref}
    git -C "$WORKTREE_DIR" reset --hard origin/{head_ref}
else
    git -C {WORKSPACE}/{repo} worktree add "$WORKTREE_DIR" origin/{head_ref}
fi
```

Store `WORKTREE_DIR` for the rest of the review. **All agent prompts and pre-flight checks must reference `WORKTREE_DIR`, not `{WORKSPACE}/{repo}`.** This is the path agents read code from.

**Why worktrees by default:** the user almost always has another session editing the main checkout. A normal `git checkout` would either fail (uncommitted changes) or yank their working tree out from under them. Worktrees give a clean isolated copy that the main checkout never notices.

If the worktree creation fails (e.g. the branch was already checked out somewhere else), report the error and ask the user — do NOT fall back to checking out in the main checkout without explicit permission.

**Escape hatch:** if the user explicitly says "review in place" or "no worktree," fall back to the legacy `git checkout` flow — capture `PREVIOUS_BRANCH` first, checkout `{head_ref}` in `{WORKSPACE}/{repo}`, and restore the previous branch in Step 9.

#### 2c: Show existing comments

If any human (non-bot) comments exist from Call 3/Call 4, display them before launching review agents:

```
### Existing Comments
- **@reviewer-name** (2026-04-09): "summary of their comment..."
- **@author-name** (2026-04-09): "summary of their reply..."
```

This gives the orchestrator (and user) context on what's already been discussed.

**Error handling:**
- If Jira ticket key can't be extracted: proceed without. Note "No Jira ticket detected" in the review header.
- If Jira MCP call fails: proceed without. Note "Jira unavailable" in the review header.
- If any GitHub MCP call fails: report the error and stop — can't review without PR data.

### Step 3: Code Review Agents

**Do NOT invoke the `code-review:code-review` skill.** The review pipeline is built directly here for full control over output format and posting.

**IMPORTANT — Pre-flight checks before spawning agents:**
1. Confirm `WORKTREE_DIR` exists and is a valid git worktree: `git -C "$WORKTREE_DIR" rev-parse --is-inside-work-tree` returns `true`
2. Confirm the worktree HEAD points at the PR branch tip: `git -C "$WORKTREE_DIR" rev-parse HEAD` matches the PR's `head.sha` from Call 1
3. If either check fails, fix it before spawning agents. Do NOT proceed with agents pointed at a stale or missing path.

(Legacy fallback: if the user opted into in-place review, the checks instead confirm `pwd` is `{WORKSPACE}/{repo}` and the PR branch is checked out there.)

**Context strategy — diff inlining is mandatory, not optional:**

Before spawning ANY agent, the prompt MUST contain the full patch content for every changed non-binary, non-fixture file. Pointing the agent at the worktree with "run `git diff main..HEAD` to see the changes" is NOT acceptable — agents that have to discover the diff themselves will burn 10-20 tool calls running git, listing files, and reading them one at a time, and routinely run out of turns BEFORE producing findings. This has happened on real reviews; do not repeat it.

Pre-spawn checklist (run this mentally for every agent prompt before calling the Agent tool):

1. Does the prompt contain the patch/diff content for every changed file the agent is responsible for? Not a file list — the actual `+`/`-` lines.
2. For newly-added files, does the prompt contain the FULL file content (not just a description of what was added)?
3. If the agent is scoped to a subset of files (split-diff strategy), is that scope spelled out explicitly?

If any answer is "no," fix the prompt before spawning. A 20KB prompt that runs in 60s is strictly better than a 5KB prompt that times out at 90s with no findings.

Agents CAN read additional files from the worktree for surrounding context (CLAUDE.md, imports, types, peer plugin patterns) — but they should never need to read a CHANGED file to learn what changed.

For PRs with very large diffs (>200KB of patch content total), split files across agents by domain instead of duplicating the entire diff to all agents. Note which agent got which files. Still inline the relevant subset for each agent — don't fall back to "go look in the worktree."

Launch **5-7 parallel sub-agents** via the Agent tool (6th is conditional on test files, 7th+ are conditional on artifact types — see below). Each agent returns **structured findings ONLY** — no posting, no GitHub interaction.

**Use pt-doots agents wherever possible** — they have domain expertise, CLAUDE.md awareness, and structured output formats that general-purpose agents don't match.

---

**Agent 1 — Edge Case QA** (`subagent_type: "pt-doots:edge-case-qa"`)

```
Review PR #{pr_number} in {owner}/{repo} for boundary conditions and edge cases.

PR title: {title}
PR description: {description}

The repo is checked out at {WORKTREE_DIR} (an isolated git worktree of {WORKSPACE}/{repo} on branch {head_ref}). Read all code from {WORKTREE_DIR}, not the main checkout.

Changed files and their diffs:
{paste file list and FULL diff/patch content from Call 2 — skip binary files and test fixtures}

Examine every changed function for boundary conditions, null/undefined/empty handling, error paths, race conditions, async edge cases, and data permutations. Return your EDGE CASE QA report.
```

---

**Agent 2 — Acceptance QA (HIGHEST PRIORITY)** (`subagent_type: "pt-doots:acceptance-qa"`)

```
Review PR #{pr_number} in {owner}/{repo} to verify implementation meets its claims.

PR title: {title}
PR description: {description}
Jira context: {jira_summary_and_acceptance_criteria OR "No Jira ticket"}

The repo is checked out at {WORKTREE_DIR} (an isolated git worktree of {WORKSPACE}/{repo} on branch {head_ref}). Read all code from {WORKTREE_DIR}, not the main checkout.

Changed files and their diffs:
{paste file list and FULL diff/patch content from Call 2 — skip binary files and test fixtures}

Verify the PR's claims against the actual code. Trace data flow through all changed files. Check for .map() stale state bugs, Promise.all() over shared state, upsert logic that drops fields, and tests that only use 1 item per key. Return your per-criterion PASS/FAIL report.
```

---

**Agent 3 — History & Context** (`subagent_type: "pt-doots:researcher"`)

```
Research PR #{pr_number} in {owner}/{repo} using git history context.

The repo is checked out at {WORKTREE_DIR} (an isolated git worktree of {WORKSPACE}/{repo} on branch {head_ref}). Read all code from {WORKTREE_DIR}, not the main checkout.

Changed files:
{list of changed file paths}

For each changed file: run git blame on modified sections, check for previous PRs that touched these files, read code comments for guidance compliance, look for TODO/FIXME/HACK that should have been addressed. For positive observations use severity "NICE". Return findings as:

FINDING | severity: HIGH/MED/LOW/NICE | file: path/to/file.ts | line: 45 | description

If no issues found, return: NO_FINDINGS
```

---

**Agent 4 — Code Reviewer** (`subagent_type: "pt-doots:code-reviewer"`)

```
Review PR #{pr_number} in {owner}/{repo} against CLAUDE.md standards.

The repo is checked out at {WORKTREE_DIR} (an isolated git worktree of {WORKSPACE}/{repo} on branch {head_ref}). Read all code from {WORKTREE_DIR}, not the main checkout.

Changed files and their diffs:
{paste file list and FULL diff/patch content from Call 2 — skip binary files and test fixtures}

Review every changed file against the workspace CLAUDE.md at {WORKSPACE}/CLAUDE.md and any repo-specific or directory-level CLAUDE.md files. Only flag violations of explicitly stated rules. Return your structured findings report.
```

---

**Agent 5 — Code Smells Detector**

Spawn using `subagent_type: "pt-doots:code-smells-reviewer"` — the agent definition has the full smell catalog and review strategy. Just provide the PR context:

```
Review PR #{pr_number} in {owner}/{repo} for code smells.

PR title: {title}
PR description: {description}

The repo is checked out at {WORKTREE_DIR} (an isolated git worktree of {WORKSPACE}/{repo} on branch {head_ref}). Read all code from {WORKTREE_DIR}, not the main checkout.

Changed files and their diffs:
{paste file list and FULL diff/patch content from Call 2 — skip binary files and test fixtures}

Review these changed files using your full smell catalog. Skip test files. Return your CODE SMELLS REPORT.
```

**Output mapping:** The agent returns findings in `[file:line] [Smell Name] [severity] description` format. When consolidating with other agents' findings, normalize to the same structure: extract file, line, severity, and description from each finding line.

---

**Agent 6 — Test Quality Reviewer (conditional)**

**Only spawn this agent if the PR includes test files** (`.test.ts`, `.test.tsx`, `test_*.py`). Check the changed files list from Call 2 — if none match test file patterns, skip this agent entirely.

Spawn using `subagent_type: "pt-doots:test-reviewer"` — the agent definition has the full test smells catalog and review strategy. Just provide the PR context:

```
Review the test files in PR #{pr_number} in {owner}/{repo} for test quality issues.

PR title: {title}
PR description: {description}

The repo is checked out at {WORKTREE_DIR} (an isolated git worktree of {WORKSPACE}/{repo} on branch {head_ref}). Read all code from {WORKTREE_DIR}, not the main checkout.

Changed files and their diffs:
{paste file list and FULL diff/patch content from Call 2 — include ALL files, not just test files, so the reviewer can read production code alongside tests}

Review only the test files in this changeset using your full test smells catalog. Return your TEST REVIEW report.
```

**Output mapping:** The agent returns findings in `[file:line] [Smell Name] [severity] description` format. When consolidating with other agents' findings, normalize to the same structure: extract file, line, severity, and description from each finding line.

---

**Agent 7+ — Dynamic Specialized Reviewers (conditional)**

Check the changed files for artifact types that deserve dedicated expertise. Add a specialized general-purpose agent for each:

| Artifact type | Trigger | Agent focus |
|---|---|---|
| Claude skill (`.claude/skills/**/SKILL.md`) | Any SKILL.md added/modified | Trigger accuracy, technical correctness vs codebase, completeness, maintainability, security (credential leaks in examples) |
| Database migration (`migrations/`) | Any migration file | Schema safety, rollback plan, data loss risk |
| CI/CD config (`.github/workflows/`) | Any workflow change | Correctness, security, performance |
| Docker/infra (`Dockerfile`, `docker-compose*`) | Any container config | Security, layer efficiency, env leaks |

For skill files specifically, the agent should compare the skill's code examples, file paths, and patterns against the actual codebase to catch drift. Check existing similar skills in the repo for consistency.

These use general-purpose agents since no pt-doots equivalent exists.

---

After all agents return, collect all findings. Deduplicate findings that refer to the same file:line from different agents (keep the higher severity). Sort by severity: HIGH → MED → LOW → NICE.

### Step 4: Save Review State

Create directory if needed:
```bash
mkdir -p {WORKSPACE}/notes/pr-reviews
```

Save to `{WORKSPACE}/notes/pr-reviews/{repo}-{pr_number}.md` with YAML frontmatter for reliable machine parsing:

```markdown
---
repo: {repo}
owner: {owner}
pr: {pr_number}
title: "{pr_title}"
author: {pr_author}
ticket: {ticket_key or "none"}
head_sha: {head_sha}
status: findings_ready
date: {ISO 8601 timestamp}
selected_findings: []
---

## Findings

| # | Severity | Agent | File:Line | Finding |
|---|----------|-------|-----------|---------|
{populated from agent results}

## Blurb

(not drafted)

## Inline Comments

(not drafted)
```

The `head_sha` field is used on resume to detect new commits since the review.

### Step 5: Present Findings

#### 5a: Orchestrator pre-promotion check (HIGH and MED findings only)

Reviewer agents work from inlined diffs and tend to over-flag plausible-sounding concerns without verification (per `feedback_reviewer_agent_overflagging.md`). Each agent is now responsible for its own "Verify Before Flag" pass, but the orchestrator still does a final sanity check before showing HIGH/MED findings to the user.

For each HIGH or MED finding, run this quick check:

1. **Did the agent note that it ran the Verify Before Flag pass?** Look for "verified caller," "checked enclosing try/catch," "ran sanity check," etc. If absent, treat the finding as un-verified and run the verification yourself (see below).

2. **For HIGH findings, do a 30-second caller trace** before presenting:
   - "Missing FF gate / Server-vs-Cloud / version compat" → grep the file for feature flag references and trace one level of callers. If a flag wraps the path, downgrade to MED and rephrase as "worth confirming the flag covers all call sites" or drop entirely.
   - "Throw not caught / breaks batch" → read the immediate caller's loop body. If there's a per-iteration `try/catch` pushing to `errors[]`, downgrade or drop.
   - "Race condition / concurrent access" → confirm there's an actual `await` between read and write, OR the state lives in Redis/Postgres. Single-threaded JS object access is not a race. If neither, drop.

3. **For both HIGH and MED, check for cross-agent duplication.** Two agents may have flagged the same underlying issue from different angles (e.g., code-reviewer and edge-case-qa both flagging the same null check). Merge into one finding, keep the higher severity, cite both agents.

4. **For findings that survived the check, mark them with a small ✓ symbol** in your internal notes — this signals to your future self (when drafting comments) that the finding was sanity-checked and the framing is sound.

5. **Track demotions in an internal sanity-check log** so you can mention them once at the top when presenting. Don't quietly drop findings without saying so — Parker likes seeing what got pruned and why.

If after this pass NO HIGH findings remain, default-tone the recommendation toward "ready for an approving follow-up" rather than "needs another round."

#### 5b: Show the consolidated findings table

```
## Review: #{pr_number} {ticket_key} — {pr_title}
Jira: {ticket_key} | Author: @{author} | Files: {file_count} | Base: {base_branch}

### Pre-promotion sanity check
- {N} findings demoted/dropped — examples: "HIGH on jira_sdk.ts:649 demoted to MED (FF gate present at call site)"
(omit this section if nothing was demoted)

### Findings ({count})
| # | Severity | File | Finding |
|---|----------|------|---------|
| 1 | HIGH | file.ts:45 | Description of the issue |
| 2 | MED | other-file.ts:112 | Description |
| 3 | NICE | test-file.ts | Positive observation |
```

If **no findings** (all agents returned NO_FINDINGS or all were demoted):
> "No issues found! This PR looks clean. Want to leave an approving review, or skip?"

Otherwise:
> "Which findings do you want to comment on? (e.g. '1, 3' or 'all' or 'none')"

If "none": ask if they want a top-level comment only, approve, or skip entirely.

### Step 5b: Walk Through Findings One-at-a-Time

**Do NOT batch all findings at once.** Present each finding individually and wait for the user's decision before moving to the next.

**Use this exact format for every finding** (do not improvise — Parker has explicitly asked for consistency here):

```
### Finding N — SEV — {file:line or "(top-level)"}

**what the agent said:**
{the raw agent finding, paraphrased tightly — no verbatim quoting}

**why this matters:**
{concrete impact if this isn't addressed — what breaks, what surprises a future reader, what slips through review. Be specific to the consequence, not abstract — "operators won't have a log breadcrumb to debug from", not "violates CLAUDE.md".}

**your suggestions:**
{1-2 concrete code-shaped fixes — extract X helper, add Y log line, change ?? to ||. No hedging. No "consider improving."}

**my opinion:**
{your recommendation: comment / skip / downgrade. This is YOUR judgment call as the orchestrator, NOT a quote from the agent. Parker can always override. Tie it to a concrete reason: "I'd skip — pre-existing code JQ didn't touch, off-scope." / "I'd flag as `should:` — customer-visible regression in report output." / "I'd downgrade to a nit — real but minor, low ROI on review attention." Where helpful, surface tradeoffs (e.g. "real LOW but flagging dilutes the must-fix list"). This section is mandatory for every finding — it's how Parker decides which battles to fight.}

**Comment, skip, or tweak?**
```

Then wait for the user's response. If they say comment, draft the inline comment, then **MANDATORY: spawn `pt-doots:voice-stylist` and pipe the draft through it before showing it for approval**. Pass the agent the raw draft text only — no preamble, no "please rewrite this" framing. Take its output verbatim and show that to Parker. If skip, move to the next. If tweak, apply their change, run the new draft through `pt-doots:voice-stylist` again, and re-show.

**Why mandatory:** voice rewrite loops (Parker calls out drift, orchestrator re-reads memory files, redrafts) burn more tokens than one focused haiku call. The agent reads the canonical voice memories on every invocation, so it stays current as Parker's preferences evolve. Skipping the agent and "drafting in voice yourself" is a guaranteed regression — do not do it.

**One call per comment.** Do not batch multiple comments into a single `pt-doots:voice-stylist` invocation. Per-comment calls keep the no-op rule clean (clean drafts return unchanged) and avoid cross-comment voice bleed.

**Format rules (strict):**
- One section header per `what / why / suggestions` block. Don't merge them.
- "what the agent said" is paraphrased, not quoted verbatim. Tight.
- "why this matters" should go into **decent detail** — Parker hasn't seen the code. Walk through the actual code path that produces the bug, name the surrounding functions, show a concrete real-world input that triggers it, and explain why the existing tests miss it. The user is reading review findings to *learn*, not just to approve. Be specific to the consequence (e.g. "operators won't have a log breadcrumb to debug from"), not abstract style/violation framing.
- "your suggestions" should be concrete and actionable, ideally code-shaped.
- "my opinion" is required, not optional. Parker reads this to decide whether to even spend a review slot on the finding. Tie the recommendation to a real reason (scope, severity, ROI, customer impact); never just "I'd skip" with no rationale.
- No jokes, no "(may be downgrade-worthy)" asides, no "Counter:" sections, no "So: flag or skip?" editorializing.
- Pre-filter: if a finding matches existing convention in untouched code and the PR author is following it, skip before presenting.

This format gives the user control over:
- Which findings to include/skip
- Whether to combine related findings into one comment
- Whether to cross-reference other findings
- The exact tone and content of each comment
- Whether to escalate a nit to a real comment or vice versa

After walking through all findings, show the complete batch (blurb + all approved comments) for final review.

### Step 6: Draft Review as a Batch

**This step MUST happen in the main context (not a sub-agent) to preserve voice consistency.**

Based on the user's selection, assemble a single GitHub review. Every prose draft you generate in this step — the top-level blurb AND every inline comment — MUST go through `pt-doots:voice-stylist` before being shown to Parker for batch approval. The agent reads the canonical voice memories, normalizes prefixes, strips banned phrases, and returns paste-ready text. One call per draft, no batching.

#### Top-level blurb

Write a 2-3 sentence review comment that:
- Calls out what the PR does well (specific, not generic praise)
- Sets the tone for inline comments ("Left a couple small thoughts inline but nothing blocking")
- If any findings can't be posted inline (outside the diff), include them in the blurb with **GitHub permalink links** (`[description](https://github.com/{owner}/{repo}/blob/{head_sha}/{path}#L{line})`)

Then spawn `pt-doots:voice-stylist` with the blurb as input. Use its output verbatim.

> **Note:** Parker has `feedback_no_pr_blurb.md` indicating blurbs are usually skipped. Check the user's prior preference and skip the blurb entirely if that's the standing rule.

#### Inline comments

For each selected finding, write a rough draft of the comment, then spawn `pt-doots:voice-stylist` on it. Take the agent's output verbatim and queue it for the batch approval gate.

**What to write in the rough draft (the agent handles the rest):**
- Lead with the prefix. Parker's canonical scheme (per `feedback_review_comment_prefixes.md`):
  - `must:` blocking — has to change before merge. Reserved for data corruption on the normal flow, security holes, anything that hits a customer on day one, anything that breaks the PR's stated goal.
  - `should:` strong recommendation. Author should address; can push back with a reason. Use for real bugs that only trigger under unusual conditions, missing error handling on edge paths, things you'd accept as a follow-up ticket if not done now.
  - `nit:` purely cosmetic. Take it or leave it.
  - `opinion:` taste call, non-blocking.
  - `idea:` brainstorm / forward-looking proposal.
  - `question:` asking for clarification or intent. Not asserting anything is wrong.
  - `praise:` positive callout (use sparingly; weave most praise into the blurb).
- Pick exactly one prefix. The voice-stylist will fix capitalization or swap unknown prefixes (`observation:`, `bug:`) silently — but you should still pick from the canonical set.
- Structure: (1) what's wrong, (2) why it matters, (3) suggested fix.
- Offer concrete code-shaped suggestions when possible.
- Skip findings already covered by another comment. Cross-reference instead.
- For pre-existing issues, check git blame to see if the PR author owns the code. If yes, "while you're in here" is fair. If not, acknowledge it's not from this PR.

**The voice-stylist agent handles voice scrubbing.** It strips banned phrases, replaces em/en dashes, swaps Latinate verbs for plain Anglo-Saxon ones, and normalizes prefixes — so don't burn cycles polishing the rough draft. Get the substance right and let the agent finish the voice pass.

**NEVER hand-edit a voice-stylist output before showing Parker.** If the output reads wrong, that's signal to either (a) fix the source draft and re-run the agent, or (b) flag a voice-stylist regression for the next `/team-audit`. Hand-editing defeats the consistency the agent provides.

**Formatting rules (readability matters):**
- Break comments into short paragraphs. Never post a wall of text
- Structure: (1) what's wrong, (2) why it matters, (3) suggested fix
- Each paragraph should be 1-2 sentences max
- Inline code backticks are fine but don't over-backtick

**NEVER include:**
- "Generated with Claude Code" or any AI attribution
- Praise-only inline comments (weave praise into the blurb)
- Lecture-style explanations
- "you should" or "this needs to" language

Present the full batch:

```
### Top-level blurb (draft)
"{blurb text}"

### Inline comments (draft)
| # | File:Line | Comment |
|---|-----------|---------|
| 1 | file.ts:45 | "{comment text}" |
| 3 | other.ts:112 | "{comment text}" |
```

Update the saved review file: set `status: drafting`, save selected findings, blurb, and comments.

### Step 7: Approval Gate

> "Good to post? (You can also edit any comment — just say 'change #1 to ...' or 'rewrite the blurb to ...')"

**Only post after explicit approval from the user.** Never post directly.

If the user wants edits:
1. Apply their changes
2. Re-present the updated draft
3. Ask again: "Good to post?"
4. Update the saved review file

After approval:
> "Want to also approve this PR, or just leave as a comment?"

- "comment" or "just comment" → event: `COMMENT`
- "approve" → event: `APPROVE`, body is ONLY: `🎺 💀 🤖` (Parker's signature approval emojis — no other text)

### Step 8: Post Review

Post in two phases: (1) the top-level review with just the blurb, then (2) individual inline comments on the code.

**Prefer inline comments on specific code lines.** The review body should primarily contain the blurb. However, findings that reference lines OUTSIDE the diff (e.g., a hardcoded value on line 93 when the diff only touches lines 200-250) belong in the body — **always with a clickable GitHub permalink** so the author can jump straight to the line.

#### Phase 1: Post the review (blurb only)

```bash
python3 -c "
import json

payload = {
    'event': 'COMMENT',  # or 'APPROVE' if user chose to approve
    'body': '''BLURB_TEXT_HERE''',
}

with open('/tmp/pr-review.json', 'w') as f:
    json.dump(payload, f)
"
```

```bash
/opt/homebrew/bin/gh api repos/{owner}/{repo}/pulls/{pr_number}/reviews \
  --method POST \
  --input /tmp/pr-review.json
```

#### Phase 2: Post inline comments

For each selected finding, post an inline comment using the PR comments API:

```bash
python3 -c "
import json

comment = {
    'body': '''COMMENT_TEXT_HERE''',
    'commit_id': '{head_sha}',
    'path': '{file_path}',
    'line': {line_number},
    'side': 'RIGHT',
}

with open('/tmp/pr-comment-N.json', 'w') as f:
    json.dump(comment, f)
"
```

```bash
/opt/homebrew/bin/gh api repos/{owner}/{repo}/pulls/{pr_number}/comments \
  --method POST \
  --input /tmp/pr-comment-N.json
```

**Line placement rules:**
- GitHub only allows inline comments on lines within the diff context
- If the finding's line IS in the diff: post directly on that line using the inline comment API
- If the finding's line is OUTSIDE the diff: put it in the review body with a **GitHub permalink** (format: `https://github.com/{owner}/{repo}/blob/{head_sha}/{file_path}#L{line}`)
- Use `line` + `side: "RIGHT"` (for new-side lines) — do NOT use `position` (deprecated diff-relative counting)
- **Permalink rule**: Every finding mentioned in the review body MUST include a clickable link to the exact line. Never reference "line ~93" without a link — the author should be able to click and navigate instantly.

Clean up temp files after all comments are posted:
```bash
rm /tmp/pr-review.json /tmp/pr-comment-*.json
```

**If the post succeeds:**
- Update the review file: `status: posted`, add `posted_at` timestamp
- Tell the user: "Review posted! [View it here](https://github.com/{owner}/{repo}/pull/{pr_number})"

**If the post fails:**
- Show the error
- Keep review file at `status: drafting` for retry
- "Want to try posting again, or save the draft for later?"

### Step 9: Clean up worktree

**This step runs ALWAYS** — after posting, after a failed post, or if the user skips posting at Step 7.

**Worktree path (default):**

```bash
git -C {WORKSPACE}/{repo} worktree remove "$WORKTREE_DIR" --force
```

If `worktree remove` fails (e.g. uncommitted notes inside the worktree the user wants to keep), tell the user and leave it in place — they can run `git worktree remove` themselves later. Don't `rm -rf` the directory; that orphans git metadata.

**Escape-hatch path (if review ran in-place):**

```bash
cd {WORKSPACE}/{repo}
git checkout {PREVIOUS_BRANCH}
```

If the restore fails (e.g. the branch was deleted), stay on the PR branch and inform the user.

---

## Error Handling

| Scenario | Behavior |
|----------|----------|
| GitHub MCP call fails (dashboard) | Show partial results for repos that succeeded, note which failed |
| GitHub MCP call fails (review) | Stop — can't review without PR data. Report the error. |
| Jira ticket key not found | Skip Jira context. Note "No Jira ticket detected" in review header. |
| Jira MCP call fails | Proceed without Jira. Note "Jira unavailable" in review header. |
| No open PRs found (dashboard) | Show "No open PRs found across PlexTrac repos." |
| Sub-agent fails during review | Report which agent failed. Present findings from agents that succeeded. |
| Review post fails | Show error, keep state at `drafting` for retry. |
| Invalid PR URL format | Show usage message. |
| PR URL from non-PlexTrac repo | Show: "This PR is not in a PlexTrac repo. Supported repos: {list}" |

---

## Context Management

The command is split between lightweight orchestrator (main context) and heavyweight analysis (sub-agents):

- **Main context:** Dashboard display, findings presentation, comment drafting (voice-sensitive), approval gate, posting
- **Sub-agents:** All code review analysis (5-6 parallel agents), context gathering where needed

This keeps the orchestrator lean and avoids context exhaustion from dumping full diffs into the main conversation.
