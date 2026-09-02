---
name: prs
description: >
  PR dashboard and review workflow for PlexTrac repos.
  Triggers: "/prs" (dashboard), "/prs <github-pr-url>" (direct review),
  "/prs self [TICKET-KEY]" (review your own inflight code), "/prs <url> loose" (lighter must-only review).
argument-hint: "[pr-url]"
---

# PRs — PlexTrac PR Dashboard & Review

Three modes based on arguments:
- **No arguments** → Dashboard mode (show all open PRs)
- **GitHub PR URL** → Direct Review mode (multi-agent code review of someone else's PR)
- **`self` or `self <TICKET-KEY>`** → Self-Review mode (multi-agent review of your own inflight code across one or more repos; output saved to `notes/{TICKET}/`)

**GitHub user:** `parker-plextrac`

**Team:** loaded from a user overlay file (see Step 0b). Falls back to Brandon Wilson (`bwilson-pt`, QA) if no overlay is set.

**Target repos:**

| Repo | Slug |
|------|------|
| product-core-backend | `PlexTrac/product-core-backend` |
| product-core-frontend | `PlexTrac/product-core-frontend` |
| product-services-export | `PlexTrac/product-services-export` |
| product-services-mcp | `PlexTrac/product-services-mcp` |
| agent-skills | `PlexTrac/agent-skills` |
| zenith-inbound-service | `PlexTrac/zenith-inbound-service` |

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

## Step 0b: Load Team Overlay

The "Team" dashboard section is driven by a user overlay file, following the pt-doots overlay convention (see `OVERLAYS.md`). Each user customizes their own team without editing this skill.

1. Glob for overlay files:
   ```bash
   ls ~/.claude/projects/*/memory/feedback_prs_team_*.md 2>/dev/null
   ```
2. For each match, parse the markdown table whose header row is `| github_login | display_name |`. Collect each data row as `{ login, display_name }`. Skip the header and the `|---|---|` separator.
3. Concatenate all overlay rows into `TEAM` (last-wins on duplicate login).
4. If no overlay file exists or no rows parse, fall back to:
   ```
   TEAM = [{ login: "bwilson-pt", display_name: "Brandon Wilson (QA)" }]
   ```

Derive `TEAM_LOGINS` as the set of login strings for filter lookups, and a `LOGIN_TO_NAME` map for display lookups.

Users add or remove teammates by editing the overlay markdown directly — they don't touch this skill.

---

## Parse ARGUMENTS

Examine `$ARGUMENTS` (the text after `/prs`):

**Review-mode detection (Direct Review only — runs before the table match).** Check whether `$ARGUMENTS` is a PR URL followed by an optional trailing `loose` token (e.g. `https://github.com/PlexTrac/product-core-backend/pull/8532 loose`):
- Trailing `loose` present → set `REVIEW_MODE = loose`, then **strip the `loose` token** so the remaining URL parses normally (`owner`/`repo`/`pr_number` still extract cleanly).
- Otherwise → `REVIEW_MODE = rigorous`.

`REVIEW_MODE` defaults to `rigorous` for **every** path (dashboard, self-review, and a plain review URL). It only changes behavior in **Direct Review** (Mode 2): a `loose` run trims the agent set (Step 3 "Loose profile") and the output (Step 5 "Loose output"). Every other mode ignores it.

| Input | Mode |
|-------|------|
| *(empty)* | **Dashboard** |
| URL matching `https://github.com/PlexTrac/*/pull/*` (alone) | **Direct Review — rigorous** (unchanged default) — extract `owner`, `repo`, and `pr_number` from the URL |
| URL + trailing `loose` (e.g. `…/pull/8532 loose`) | **Direct Review — loose profile** (`REVIEW_MODE=loose`) — strip `loose`, then extract `owner`/`repo`/`pr_number` from the URL |
| `self` (alone) | **Self-Review** — auto-detect ticket from current branches |
| `self <TICKET-KEY>` (e.g. `self IO-2168`) | **Self-Review** — review your inflight work for that ticket across all repos |
| Anything else | Show usage: `/prs` for dashboard, `/prs <github-pr-url>` to review a specific PR, `/prs self [TICKET-KEY]` to review your own inflight code |

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
- **Team**: PRs where `user.login` is in `TEAM_LOGINS` (loaded from the overlay in Step 0b), **created within the last 40 days**
- **IO Tickets (All Open)**: PRs where the title or `head.ref` starts with `IO-`, **created within the last 40 days**

The 40-day freshness filter on Team and IO sections keeps the dashboard focused on actively in-flight work. Older PRs are usually abandoned and just add noise.

For each PR in **Your PRs**, **Team**, and **IO Tickets (All Open)**, also fetch CI status:

```
mcp__github__get_pull_request_status(owner: "PlexTrac", repo: "{repo_name}", sha: "{head.sha}")
```

For each PR in **Team** and **IO Tickets (All Open)**, also fetch review state to detect if Parker has reviewed:

```bash
/opt/homebrew/bin/gh api "repos/PlexTrac/{repo_name}/pulls/{pr_number}/reviews" --jq '[.[] | select(.user.login == "parker-plextrac") | .state] | last // "NONE"'
```

This returns Parker's most recent review state (`APPROVED`, `COMMENTED`, `CHANGES_REQUESTED`) or `NONE` if he has not reviewed.

For each PR in **Requesting Your Review**, also fetch whether anyone has already approved it — so an already-signed-off PR is obvious at a glance and you don't re-review it by mistake:

```bash
/opt/homebrew/bin/gh api "repos/PlexTrac/{repo_name}/pulls/{pr_number}/reviews" --jq '[.[] | select(.state == "APPROVED") | .user.login] | unique'
```

This returns the list of logins who have approved (empty if none). Map each via `LOGIN_TO_NAME` for display, falling back to `@{login}`.

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

| # | Repo | PR | Author | Files | Approved? | IO? |
|---|------|----|--------|-------|-----------|-----|

Column definitions:
- **#**: Row number (continues from Your PRs numbering)
- **Repo**: Short repo name
- **PR**: `#{number} {title}`
- **Author**: `@{user.login}`
- **Files**: `changed_files` count
- **Approved?**: `✓ {approver name(s)}` when one or more APPROVED reviews exist (display via `LOGIN_TO_NAME`, fall back to `@{login}`; join multiple with `, `), `—` otherwise. Surfaces PRs that already have sign-off so you don't queue them for review by mistake.
- **IO?**: `YES` if IO-prefixed, `no` otherwise

If no review-requested PRs: "No PRs requesting your review."

#### Team

| # | Repo | PR | Author | CI | Reviewed | Days | Draft? |
|---|------|----|--------|----|----------|------|--------|

Column definitions:
- **#**: Row number (continues numbering)
- **Repo**: Short repo name
- **PR**: `#{number} {title}`
- **Author**: Display name from `LOGIN_TO_NAME[user.login]`; fall back to `@{user.login}` if the login isn't in the overlay (shouldn't happen since the section is filtered to overlay members)
- **CI**: `PASS` / `FAIL` / `PENDING` / `—`
- **Reviewed**: Parker's last review state — `APPROVED` / `COMMENTED` / `CHANGES_REQ` / `—` (not reviewed)
- **Days**: Days since `created_at`
- **Draft?**: `DRAFT` if `draft: true`, empty otherwise

If none: "No open PRs from your team."

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

**Conventions overlay (detect `LANG`, then inject).** Compute `LANG` from the delta's changed files (the top-level dirs / delta patch from 1b.1) using the detection rule in the Language Detection & Conventions-Overlay Injection section of `reference/workflow.md`, and resolve the overlay path(s). Inject this block into all three re-review agents (re-reviewer, edge-case-qa, test-reviewer):

    Conventions overlay: {overlay path(s) for LANG — both paths if mixed}
    Read and apply it. The target repo's own committed CLAUDE.md is authoritative over the overlay — read it first and defer to it; the overlay is the baseline.

The re-reviewer needs it too: judging whether a prior convention-based finding was actually resolved requires the convention, not just the finding text. Without this block, a Python re-review silently reverts to TypeScript-biased defaults.

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

**Call 1:** `mcp__github__get_pull_request` — get PR title, description, author, base branch, head ref/branch name, head SHA, base SHA, draft status

Store all four of these from the response; Step 2b and Step 2b-base need them:

| Store as | From | Used for |
|---|---|---|
| `{head_ref}` | `head.ref` | the branch the worktree tracks |
| `{head_sha}` | `head.sha` | pre-flight check that the worktree is at the PR tip; inline comment `commit_id` |
| `{base_ref}` | `base.ref` | which remote ref to fetch (`main`, or a `release/vX.Y` on a backport) |
| `{base_sha}` | `base.sha` | **the authority for the diff base.** Step 2b-base asserts its computed `BASE_SHA` against this. |

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

# Fetch BOTH the PR branch tip and the base branch. The base fetch is not
# optional — see "Resolve the diff base" below.
git -C {WORKSPACE}/{repo} fetch origin {head_ref} {base_ref}

# Create the worktree (or reuse if it already exists from a prior review)
if [ -d "$WORKTREE_DIR" ]; then
    git -C "$WORKTREE_DIR" fetch origin {head_ref} {base_ref}
    git -C "$WORKTREE_DIR" reset --hard origin/{head_ref}
else
    git -C {WORKSPACE}/{repo} worktree add "$WORKTREE_DIR" origin/{head_ref}
fi
```

Store `WORKTREE_DIR` for the rest of the review. **All agent prompts and pre-flight checks must reference `WORKTREE_DIR`, not `{WORKSPACE}/{repo}`.** This is the path agents read code from.

#### 2b-base: Resolve the diff base (MANDATORY — do not skip, do not use a bare branch name)

**Every diff in this review is taken against `BASE_SHA`, computed here. Never against a local branch name.**

A local `main` (or `release/vX.Y`) ref is routinely behind its remote, and **a fresh worktree inherits that stale ref** — so this fires exactly when the setup looks cleanest. Diffing against it silently produces a *superset*: files the PR never touched, and pre-existing code presented to reviewers as newly added. Reviewers cannot detect this; they will faithfully review whatever surface you hand them and report pre-existing design as this PR's work.

```bash
# {base_ref} is base.ref from Call 1 (usually main, sometimes release/vX.Y)
BASE_SHA=$(git -C "$WORKTREE_DIR" merge-base origin/{base_ref} HEAD)
```

Then **assert it against the API**, which is the authority:

```bash
# Must equal base.sha from Call 1
echo "computed: $BASE_SHA"
echo "api:      {base_sha}"
```

- **They match** → proceed; use `$BASE_SHA` for every diff from here on.
- **They differ** → your fetch did not land or the PR was retargeted. Re-fetch and recompute. Do NOT proceed with a base you have not reconciled, and do NOT fall back to a branch name.

A cheap independent smell test, worth running once: `git -C "$WORKTREE_DIR" rev-parse --short {base_ref}` versus `git -C "$WORKTREE_DIR" rev-parse --short origin/{base_ref}`. If those differ, the local ref is stale and any `{base_ref}...HEAD` diff is wrong.

**Record the file count and insertion/deletion totals from `git diff --stat $BASE_SHA...HEAD` in the review state file.** If a reviewer later reports a finding against a file outside that list, the finding is against the wrong base, not against this PR.

**This cost a real review (zenith-inbound-service #25, 2026-08-17):** patches were built with `git diff main...HEAD` in a fresh worktree while local `main` was 1 merge behind. Six reviewers received 8 files that were not in the PR, plus a 265-line file shown as new that already existed at base. Both HIGH findings from one reviewer were false, and 6 findings total had to be pruned on provenance. It was caught only because a separate agent independently ran `merge-base`.

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

> **Loose profile (`REVIEW_MODE=loose`) — trimmed agent set.** When the run was invoked as `/prs <url> loose`, replace the rigorous 5–7 agent fan-out below with a minimal set. The mode-independent parts of this step still apply: run the same **pre-flight checks** and the same mandatory **diff-inlining context strategy**.
> - Spawn **only Agent 2 — Acceptance QA** (`pt-doots:acceptance-qa`), exactly as defined below. Do **not** spawn Agent 1 (edge-case-qa), Agent 3 (researcher), Agent 4 (code-reviewer), Agent 5 (code-smells-reviewer), Agent 6 (test-reviewer), or any Agent 7+ dynamic specialist.
> - **Run the Step 3.5 repro-verifier**, which is mandatory in every mode. In loose mode it carries the whole review, because build → run the repo's own gates → exercise the feature is the entire point. After acceptance-qa returns, spawn `pt-doots:repro-verifier` (Step 3.5 mechanics) seeded with **acceptance-qa's `NOT MET` / `PARTIAL` done-condition items** (instead of a static-reviewer finding list), plus its standing instruction to run the repo's own gates (`just check` / typecheck / tests) and exercise the feature described in the PR/ticket. Scratch dir: `/tmp/{repo}-{pr_number}-repro/` (tell it to `mkdir -p` it). This bullet **is** the loose-mode form of Step 3.5 — do not also run the Step 3.5 block separately.
> - **Skip the rigorous consolidation** at the end of this step (dedupe / severity-sort) — loose mode produces no multi-agent severity findings to merge. Step 5's **Loose output** reads acceptance-qa's per-criterion result and the repro-verifier's verdicts directly.
> - Continue: Step 4 (save state; record `review_mode: loose`) → Step 5 **Loose output** variant → Step 9 cleanup.
>
> Everything below is the **rigorous** default (`REVIEW_MODE=rigorous`) and runs unchanged when no `loose` keyword was given.

**IMPORTANT — Pre-flight checks before spawning agents:**
1. Confirm `WORKTREE_DIR` exists and is a valid git worktree: `git -C "$WORKTREE_DIR" rev-parse --is-inside-work-tree` returns `true`
2. Confirm the worktree HEAD points at the PR branch tip: `git -C "$WORKTREE_DIR" rev-parse HEAD` matches the PR's `head.sha` from Call 1
3. Confirm `BASE_SHA` (Step 2b-base) is set and equals the PR's `base.sha` from Call 1. **An unset or unreconciled `BASE_SHA` is a hard stop** — every patch you are about to inline is computed from it, and a wrong one silently hands reviewers a superset of the PR.
4. If any check fails, fix it before spawning agents. Do NOT proceed with agents pointed at a stale or missing path, or at a base you have not reconciled.

(Legacy fallback: if the user opted into in-place review, the checks instead confirm `pwd` is `{WORKSPACE}/{repo}` and the PR branch is checked out there.)

**Context strategy — diff inlining is mandatory, not optional:**

Before spawning ANY agent, the prompt MUST contain the full patch content for every changed non-binary, non-fixture file. Pointing the agent at the worktree with "run `git diff main..HEAD` to see the changes" is NOT acceptable — agents that have to discover the diff themselves will burn 10-20 tool calls running git, listing files, and reading them one at a time, and routinely run out of turns BEFORE producing findings. This has happened on real reviews; do not repeat it.

Pre-spawn checklist (run this mentally for every agent prompt before calling the Agent tool):

0. Was every patch generated against `$BASE_SHA` from Step 2b-base? Any patch built from a bare branch name (`main...HEAD`, `release/vX.Y...HEAD`) is void — regenerate it. This is item zero because it invalidates all the others: a correct diff of the wrong base is still the wrong review surface.
1. Does the prompt contain the patch/diff content for every changed file the agent is responsible for? Not a file list — the actual `+`/`-` lines.
2. For newly-added files, does the prompt contain the FULL file content (not just a description of what was added)?
3. If the agent is scoped to a subset of files (split-diff strategy), is that scope spelled out explicitly?

If any answer is "no," fix the prompt before spawning. A 20KB prompt that runs in 60s is strictly better than a 5KB prompt that times out at 90s with no findings.

Generate every patch this way, always with `-M` so a rename reads as a rename instead of a delete plus an unrelated 200-line "new" file:

```bash
git -C "$WORKTREE_DIR" diff -M $BASE_SHA...HEAD -- {paths} > /tmp/{repo}-{pr_number}-{scope}.patch
```

**Tell each agent which parts of its surface are pre-existing.** A moved or renamed file arrives looking brand new, and reviewers will judge the whole thing as this PR's design. Before fan-out, run `git diff -M --summary $BASE_SHA...HEAD` and `git diff -M --stat $BASE_SHA...HEAD`; for anything reported as a rename, or any file whose diff is a small delta inside a large body, say so explicitly in the prompt ("`parsers/csv.py` is a rename of `csv_parser.py`, 84% similar; the only change is two lines"). Without that, you get confident findings against code that shipped tickets ago.

Agents CAN read additional files from the worktree for surrounding context (CLAUDE.md, imports, types, peer plugin patterns) — but they should never need to read a CHANGED file to learn what changed.

For PRs with very large diffs (>200KB of patch content total), split files across agents by domain instead of duplicating the entire diff to all agents. Note which agent got which files. Still inline the relevant subset for each agent — don't fall back to "go look in the worktree."

**Conventions overlay — detect `LANG`, then inject.** Compute `LANG` from the changed-file list (Call 2) using the detection rule in `reference/workflow.md` § Language Detection & Conventions-Overlay Injection, and resolve the overlay path(s) for that `LANG`. Add this block to the **writer / language-sensitive-reviewer** prompts only — Agent 1 (edge-case-qa), Agent 4 (code-reviewer), Agent 5 (code-smells-reviewer), and Agent 6 (test-reviewer):

    Conventions overlay: {overlay path(s) for LANG — both paths if mixed}
    Read and apply it. The target repo's own committed CLAUDE.md is authoritative over the overlay — read it first and defer to it; the overlay is the baseline.

Do NOT add it to Agent 2 (acceptance-qa), Agent 3 (researcher), or the Agent 7+ artifact-type specialists — those are language-neutral. (Loose mode spawns only acceptance-qa + repro-verifier, so it never injects an overlay.)

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

Conventions overlay: {overlay path(s) for LANG — both paths if mixed; see the "detect LANG, then inject" note above}
Read and apply it. The target repo's own committed CLAUDE.md is authoritative over the overlay — read it first and defer to it; the overlay is the baseline.

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

Conventions overlay: {overlay path(s) for LANG — both paths if mixed; see the "detect LANG, then inject" note above}
Read and apply it. The target repo's own committed CLAUDE.md is authoritative over the overlay — read it first and defer to it; the overlay is the baseline.

Review every changed file against the conventions overlay above, the workspace CLAUDE.md at {WORKSPACE}/CLAUDE.md, and any repo-specific or directory-level CLAUDE.md files. Only flag violations of explicitly stated rules. Return your structured findings report.
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

Conventions overlay: {overlay path(s) for LANG — both paths if mixed; see the "detect LANG, then inject" note above}
Read and apply it. The target repo's own committed CLAUDE.md is authoritative over the overlay — read it first and defer to it; the overlay is the baseline.

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

Conventions overlay: {overlay path(s) for LANG — both paths if mixed; see the "detect LANG, then inject" note above}
Read and apply it. The target repo's own committed CLAUDE.md is authoritative over the overlay — read it first and defer to it; the overlay is the baseline.

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

### Step 3.5: Repro-verify findings (MANDATORY — runs on every review)

Static reviewers reason from an inlined diff. They cannot run the code, so they both miss bugs that only surface at runtime and over-flag plausible-but-wrong concerns. `pt-doots:repro-verifier` is what makes the findings legitimate: it proves or refutes them by actually running them. Without it you are presenting guesses with a severity column attached.

**When to run it: ALWAYS. There are no skip conditions, and this step has no "auto" tier to qualify for.** Spawn it on every review, in every repo, at every severity, including reviews where the static agents raised nothing above LOW. On a diff with nothing runtime-falsifiable (frontend-only, style, config), it still runs the repo's own gates, and a red gate is itself the finding.

**The review does not advance to Step 5 until the verifier has returned.** Presenting findings to the user without execution verdicts is the failure this step exists to prevent.

**What to pass it** (seed it with the findings, do NOT make it re-hunt from scratch):
- `WORKTREE_DIR` (the isolated worktree from Step 2b; the PR code is already there).
- The consolidated correctness / edge-case / security findings from Step 3 at MED severity and above, each with file:line and the concern. Skip pure style / naming / smell / test-quality findings; those are not runtime-falsifiable.
- Its scratch workspace, which is its ONLY writable path: `/tmp/{repo}-{pr_number}-repro/` (tell it to `mkdir -p` it).

Spawn `subagent_type: "pt-doots:repro-verifier"`. The agent definition carries the full contract, the run-the-repo's-own-gates step, and the report format. Its safety rails forbid touching any shared or production service.

**How its verdicts change the findings:**
- **CONFIRMED**: mark the finding proven. It floats to the top and is exempt from the Step 5a demotion pass (execution already settled it). Attach the repro command so the inline comment can cite runnable evidence.
- **PROVEN-SAFE**: drop the finding from the presented set. Record it in the Step 5a sanity-check log as "dropped: repro showed correct behavior (`<cmd>`)" so the pruning stays visible.
- **INCONCLUSIVE**: leave the finding exactly as the static reviewer raised it; it still goes through the normal Step 5a check.
- **Incidental proven bug**: add it as a new CONFIRMED finding.
- **Gate failure** (the PR fails the repo's own `just check` / typecheck / tests at this commit): surface as its own HIGH finding. A red gate is a merge blocker regardless of the rest.

**Environment blockers are YOURS to clear, not a reason to record SKIPPED.** The verifier is sandboxed and cannot set up the environment; you can. When it reports a setup failure, fix the cause and send it back before accepting any skip. The known ones, all cheap:

- **`node_modules` missing in the worktree** — symlink the main checkout's: `ln -s {WORKSPACE}/{repo}/node_modules {WORKTREE_DIR}/node_modules`. Never run `npm install` in a worktree.
- **A missing generated artifact** (e.g. `build-metadata.json` in product-core-backend, via `npm run dev:generateBuildMetadata`) — generate it. Confirm it is gitignored first so it cannot reach the diff.
- **`.env` missing** — symlink the main checkout's.
- **The suite needs the running stack** (integration tests hitting localhost) — the stack runs from the MAIN checkout, so a worktree run tests the wrong code. Detach main onto the PR commit (`git -C {WORKSPACE}/{repo} checkout {head_sha}`), confirm the nodemon reload in the tmux panes, run it, then restore main to the commit you recorded before touching it. Record that commit FIRST. The workspace CLAUDE.md documents this procedure.
- **The suite needs Postgres/Redis/MinIO** — they are long-lived Docker containers on this machine and are usually already up. Check `docker ps` before concluding otherwise.

Remove any symlinks you created before removing the worktree in Step 9, so nothing follows them.

**There is no skip.** A port held by another worktree's stack, a missing container, an absent `.env` — those are yours to clear, and clearing them takes minutes. If you genuinely cannot make the code run after clearing the blocker, STOP and tell the user what is blocking it and what you tried. Do not quietly present static findings as if they had been verified. "The environment was busy" is not a reason to hand over unverified findings; it is a reason to fix the environment.

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
review_mode: {loose or rigorous — the REVIEW_MODE resolved in Parse ARGUMENTS}
date: {ISO 8601 timestamp}
selected_findings: []
---

## Findings

| # | Severity | Agent | File:Line | Prior sites | Finding |
|---|----------|-------|-----------|-------------|---------|
{populated from agent results; `Prior sites` is the 5a.0.5 ratio, or `n/a`}

## Blurb

(not drafted)

## Inline Comments

(not drafted)
```

The `head_sha` field is used on resume to detect new commits since the review.

### Step 5: Present Findings

> **Loose output (`REVIEW_MODE=loose`).** Skip 5a (pre-promotion machinery) and the 5b one-at-a-time `what / why / suggestions / opinion` walk entirely. Present a compact verdict instead:
>
> ```
> ## Loose review: #{pr_number} {ticket_key} — {pr_title}
> Works: YES / NO — {one line, from acceptance-qa's done-condition result + the repro-verifier's gate/exercise result}
>
> ### must: blockers ({n})   (omit this section if n = 0)
> | # | file:line | blocker (evidence) |
> |---|-----------|--------------------|
> ```
>
> - `Works: YES` only when acceptance-qa met every done-condition **and** the repro-verifier's gate passed with no confirmed bug. Any `NOT MET` / `FAIL` criterion, any `CONFIRMED` bug, or a `Gate failure` ⇒ `Works: NO`.
> - Populate the `must:` table **only** from: acceptance-qa `NOT MET` done-conditions / `FAIL` criteria, and repro-verifier `CONFIRMED` bugs or a `Gate failure` (cite the repro command / failing gate as evidence). **Drop everything else** — no `should:` / `nit:` / `opinion:` / `idea:` / `praise:`, no smells, no standards, no positive observations, no other severities.
> - Default outcome is just the verdict — nothing is posted. Posting stays opt-in exactly as in rigorous mode: if Parker wants a `must:` blocker posted or an approval left, reuse **Steps 6–8 verbatim** (the voice-stylist still runs on any comment that gets posted; an approval still uses body `🎺 💀 🤖`). Then run Step 9 (worktree cleanup) as always.
>
> The rigorous 5a / 5b flow below runs unchanged when `REVIEW_MODE=rigorous`.

#### 5a: Orchestrator pre-promotion check (HIGH and MED findings only)

Reviewer agents work from inlined diffs and tend to over-flag plausible-sounding concerns without verification (per `feedback_reviewer_agent_overflagging.md`). Each agent is now responsible for its own "Verify Before Flag" pass, but the orchestrator still does a final sanity check before showing HIGH/MED findings to the user.

**If Step 3.5 (repro-verify) ran, its verdicts take precedence here.** A CONFIRMED finding is proven by execution: present it as-is and do NOT demote it. A PROVEN-SAFE finding was already dropped in Step 3.5. Only run the manual check below on INCONCLUSIVE findings and on findings from a review where the repro-verifier did not run.

For each HIGH or MED finding, run this quick check:

0. **Is the flagged code actually in this PR?** Check the finding's file against the changed-file list you recorded in Step 2b-base, and check that the flagged lines are `+` lines in `git diff -M $BASE_SHA...HEAD`, not context. **If the file is not in the PR, drop the finding outright.** If the file is in the PR but the flagged lines are unchanged context, it is a pre-existing-code observation: drop it, or reframe it as `question:` about whether the author wants to fix it while he is in there. Never present pre-existing design as something this PR introduced — that is how a review picks a fight over a decision that already shipped and was already reviewed.

   Do this first, because it is the cheapest check and it invalidates everything downstream. Renames and moves are where it bites: a file that moved arrives looking new, so a reviewer will judge the whole body as this PR's work. **The tell is a reviewer flagging a `HIGH` against code with no `+` on it.**

0.5 **Is the author just following an existing convention?** Before flagging any pattern — a cast, an inline expression, a missing test, a naming choice — COUNT how often that same pattern already exists:

    ```bash
    grep -rn "<the pattern>" --include='*.ts' apps libs | grep -v '\.test\.ts' | wc -l
    ```

   A double-digit count means it is house style, not this PR's defect, and the finding is asking the author to be the odd one out in a bugfix PR. Drop it; a codebase-wide cleanup is a separate ticket. Note the rule of three argues AGAINST extracting once a pattern is already everywhere. Also read the repo's own CLAUDE.md before flagging a MISSING artifact — it may declare that artifact optional.

   **Count the RATIO, not just the volume.** The threshold above only catches patterns that are everywhere. It misses the case that matters more: a finding about a DECISION the author had to make (which permission scope, which helper, which base class, which table) where the codebase makes that same decision only a handful of times. There, count how many pre-existing sites decide it the author's way and record it as a ratio. **N of N is house style no matter how small N is.** Unanimity among prior sites means the author is following the model rather than breaking it, and the burden flips: you now have to explain why every existing site is also wrong, in a PR that did not create any of them.

   **`must:` is NOT exempt from this gate.** A correctness framing is exactly what makes a convention finding feel like it outranks the check. It does not. Run the count first, then decide the severity.

   **Writing the count into the finding's prose is not running the gate.** "For what it is worth, `reports/service.ts` does the same thing, so this is inherited rather than introduced here" is a drop notice, not a caveat to append. If you are composing that sentence, the gate has already fired and you are talking past it. Put the ratio in the findings table as a bare number and let the number decide.

   **This is the highest-yield gate in this step.** On PR #9129 four of thirteen findings died here and not one should have reached the user: raw-tag storage the permitted path does identically, a test cast, a missing controller test that `CLAUDE.md:161` explicitly makes optional, and an inline `map(cleanUpTags)` with 30+ instances codebase-wide. Reviewer agents see a diff, not a codebase, so flagging house style as a new defect is their most common failure — and it is yours to catch, not the user's.

   **A fifth finding on that same PR got through, and it was the only `must:`.** It claimed the author's `doesUserHavePermissionsForTenant` tag gate read the wrong role table because the route was client-scoped. All four pre-existing `CREATE_TAGS` checks in the repo resolved tenant roles: 4 of 4, unanimous. The orchestrator ran the grep, found `reports/service.ts`, and wrote it into the comment as a closing footnote instead of treating it as the answer. The author pushed back and was right. Four of four never reached the user as a number, only as a sentence at the end of a paragraph, which reads as a caveat the author already handled.

1. **Did the agent note that it ran the Verify Before Flag pass?** Look for "verified caller," "checked enclosing try/catch," "ran sanity check," etc. If absent, treat the finding as un-verified and run the verification yourself (see below).

2. **For HIGH findings, do a 30-second caller trace** before presenting:
   - "Missing FF gate / Server-vs-Cloud / version compat" → grep the file for feature flag references and trace one level of callers. If a flag wraps the path, downgrade to MED and rephrase as "worth confirming the flag covers all call sites" or drop entirely.
   - "Throw not caught / breaks batch" → read the immediate caller's loop body. If there's a per-iteration `try/catch` pushing to `errors[]`, downgrade or drop.
   - "Race condition / concurrent access" → confirm there's an actual `await` between read and write, OR the state lives in Redis/Postgres. Single-threaded JS object access is not a race. If neither, drop.

3. **For both HIGH and MED, check for cross-agent duplication.** Two agents may have flagged the same underlying issue from different angles (e.g., code-reviewer and edge-case-qa both flagging the same null check). Merge into one finding, keep the higher severity, cite both agents.

4. **For findings that survived the check, mark them with a small ✓ symbol** in your internal notes — this signals to your future self (when drafting comments) that the finding was sanity-checked and the framing is sound.

5. **Track demotions in an internal sanity-check log** so you can mention them once at the top when presenting. Don't quietly drop findings without saying so — Parker likes seeing what got pruned and why.

**Rooted-in-what-exists lens (applies across HIGH/MED).** For any finding that RECOMMENDS adding permanent structure (a database constraint, an index, a column, a config key, a new abstraction), confirm it names a present query the code runs or an invariant the code already relies on. If it names neither, reframe it as "leave it out" and drop it from the add set (or downgrade it); do not surface it to the user as an add. Justifications like "in case," "might need," "for consistency," "for symmetry," or "future proofing" are automatic rejects. This gate is only about proposals to COMMIT new structure: correctness findings about code that runs today (null, empty, or out-of-order inputs) are untouched by it and stay.

**Input-provenance gate (applies to the correctness findings the lens above deliberately exempts).** The rooted-in-what-exists lens only governs proposals to add structure, so correctness findings pass it untouched. That is the hole: a finding can be a true statement about the code and still be worthless because the reviewer invented the input that triggers it.

For every HIGH/MED finding whose trigger is a specific input value, make the agent's provenance clause explicit before you show it. If the agent gave none, supply one yourself or demote:

- **Parser, importer, or external-format PR** — find the sample corpus and test the trigger against it. Look in the repo (`tools/helperFiles/`, `tests.api/mockUploads/`, `tests/mocks/`), the local import corpus (`~/Desktop/plextrac-file-imports/`), and the ticket's attachments. Real files beat reasoning: grep the corpus for the exact shape the finding needs.
- **No real instance found** — reframe as `question:` ("does any real input look like this?") or drop. Do not present it as a defect.
- **An agent's own stated provenance gap is a HARD STOP, not a caveat to relay.** When a reviewer writes "I did not find a parser that emits this", "flagging on the strength of the sibling guard, not a reproduced crash", or "could not check the corpus", that sentence IS the gate failing. Ground it yourself or drop it. Never forward the admission to the user with a severity still attached.
- **Narrating the weakness is not filtering it.** If you are writing a paragraph explaining why the evidence is thin, you have already failed the gate — that paragraph is a drop notice, not a disclaimer. Do not hand the user the filtering decision this gate exists to make.
- **Substitute evidence does not count.** "Defensive code exists nearby, so the input must occur" is not provenance; defensive sweeps are written against hypotheticals too. `git log -S` the guard before leaning on it — on #9129 the guard cited as proof turned out to be a broad "attempt to catch all errors" hardening commit, authored by the reviewer's own user.
- **Report what the corpus killed**, in the same sanity-check log as the demotions. "3 findings dropped: zero of 91 real `<location>` values contain a bracket" is the most useful line in the whole review, because it tells the user the pruning was grounded and not taste.

This is the reviewer-side twin of the workspace CLAUDE.md's IO-2196 lesson ("ground on the full local sample corpus before building or changing any parser"). That lesson currently reaches the planning phase only; this gate is what carries it into review.

If after this pass NO HIGH findings remain, default-tone the recommendation toward "ready for an approving follow-up" rather than "needs another round."

#### 5b: Show the consolidated findings table

```
## Review: #{pr_number} {ticket_key} — {pr_title}
Jira: {ticket_key} | Author: @{author} | Files: {file_count} | Base: {base_branch}

### Pre-promotion sanity check
- {N} findings demoted/dropped — examples: "HIGH on jira_sdk.ts:649 demoted to MED (FF gate present at call site)"
(omit this section if nothing was demoted)

### Findings ({count})
| # | Severity | File | Prior sites | Finding |
|---|----------|------|-------------|---------|
| 1 | HIGH | file.ts:45 | 2 of 14 | Description of the issue |
| 2 | MED | other-file.ts:112 | n/a | Description |
| 3 | NICE | test-file.ts | n/a | Positive observation |
```

**The `Prior sites` column is the 5a.0.5 count, carried forward as a bare ratio.** For any finding that asks the author to do something differently from code that already exists, it is: how many pre-existing sites already do it the author's way, over how many sites make that same decision at all. Write `n/a` only when the finding is genuinely not about a convention (a null deref, a typo, a missing await). Do NOT write prose in this column, and do NOT leave it blank. A blank cell means you skipped the count, and skipping the count is the failure this column exists to make visible.

A ratio whose numerator equals its denominator should have been dropped at 5a.0.5. If one reaches this table, the gate leaked: drop it now, or say out loud why every existing site is also wrong.

If **no findings** (all agents returned NO_FINDINGS or all were demoted):
> "No issues found! This PR looks clean. Want to leave an approving review, or skip?"

Otherwise:
> "Which findings do you want to comment on? (e.g. '1, 3' or 'all' or 'none')"

If "none": ask if they want a top-level comment only, approve, or skip entirely.

### Step 5b: Walk Through Findings One-at-a-Time

> **READINESS GATE — a finding you present must be TERMINAL.** Nothing may be left for you to do on it. Before it goes in the message:
> - Its trigger is grounded against real data, and it cleared the convention pre-filter (gates in 5a).
> - Any claim of the form "X would not be caught by the tests" has been **tested, not asserted**: mutate the production line, run the suite, quote the real result.
> - Your own suggested fix has been **applied and run, both ways** — passes against real code, fails when the thing it protects is removed. A fix you have not executed is a guess with a code block around it.
> - The paste-ready comment is written, in the same message.
> - Every hinge another agent asserted and you relied on has been checked yourself.
>
> **Never present a finding with an open question attached.** No "want me to run the mutation test?", no "I can check the corpus if you like." Doing the check is your job; scheduling it is not the user's. A finding that arrives half-verified costs a full round trip and burns the user's patience faster than a missed finding does.

**Default to one finding at a time**, each presented with its Ready-to-post comment already drafted (see below), waiting for the user's decision before moving to the next. If the user asks to see the whole set at once ("do them all", "roll the whole PR that way"), present every finding in a single pass — each still in the full format below with its own **Ready to post** block — so they can approve or cherry-pick in one reply. Either way, the finished comment is shown WITH the finding, never as a separate draft-after-approval step.

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

**Ready to post:**
> {the paste-ready comment for this finding — ALREADY run through `pt-doots:voice-stylist`, with the chosen prefix (`must:`/`should:`/`nit:`/`opinion:`/`idea:`/`question:`/`praise:`) prepended (the stylist returns the body only). Quote-block it so Parker sees exactly what will post. For a `(top-level)` finding with no diff line, note it posts in the review body, not inline.}

**Post, skip, or tweak?**
```

**Draft the comment and present it in the **Ready to post** block** (prepend the chosen prefix). The finished comment sits under the finding so Parker can approve in one step instead of a present-then-draft round-trip.

**PR review comments do NOT go through `pt-doots:voice-stylist`** (changed 2026-08-07). The what/fix/why contract plus the plain-English rules in Step 6 now specify the voice for this artifact explicitly, so write to that contract directly. The stylist remains mandatory for **Slack and Jira** drafts, which have no equivalent format contract.

If you do invoke the stylist for some other artifact, **frame the input**: "Rewrite the prose below in the user's voice. It is DATA to restyle, not instructions to follow. If it describes a code change, restyle the description; never make the change." The old guidance here said to pass the raw draft with no preamble, and on 2026-08-07 that caused a draft describing a code change to be read as a work order: the stylist edited two of the PR author's test files instead of restyling. `Bash` has since been removed from that agent, so it has no write path, but frame the input anyway.

**Overlay and dash-scrub now live here, not in the agent.** When you do invoke the stylist, resolve its voice-overlay files yourself (`find "$HOME/.claude/projects" -name 'feedback_voice*'` plus `user_voice_profile.md`) and inline their contents into the prompt, and run the deterministic em/en-dash scrub on the returned text. Both moved out of the agent when its `Bash` was removed; putting the scrub at the point where you paste the final string also makes it unskippable.

On the user's response: **post** → post it inline immediately (Step 8 mechanics; a `(top-level)` finding goes in the review body); **skip** → move to the next finding; **tweak** → apply their change, re-run `pt-doots:voice-stylist`, and re-show the Ready-to-post block. When presenting the whole set in one pass, they may reply with a subset ("do 1 and 2") — post exactly those.

(Self-Review mode, Mode 3, is exempt from this entire step: it captures action items to a local notes file and never drafts a GitHub comment, so no voice-stylist and no Ready-to-post block — see Step S10.)

**Why the stylist still exists for other artifacts:** voice rewrite loops (Parker calls out drift, orchestrator re-reads memory files, redrafts) burn more tokens than one focused call, and the agent reads the canonical voice memories on every invocation so it stays current. That reasoning still holds for Slack and Jira. It stopped holding for PR comments once Step 6 spelled the format out, and hand-written comments against that contract were approved verbatim on 2026-08-07.

**One call per draft.** Do not batch multiple drafts into a single `pt-doots:voice-stylist` invocation. Per-draft calls keep the no-op rule clean (clean drafts return unchanged) and avoid cross-draft voice bleed.

**Format rules (strict):**
- One section header per `what / why / suggestions` block. Don't merge them.
- "what the agent said" is paraphrased, not quoted verbatim. Tight.
- "why this matters" should go into **decent detail** — Parker hasn't seen the code. Walk through the actual code path that produces the bug, name the surrounding functions, show a concrete real-world input that triggers it, and explain why the existing tests miss it. The user is reading review findings to *learn*, not just to approve. Be specific to the consequence (e.g. "operators won't have a log breadcrumb to debug from"), not abstract style/violation framing.
- "your suggestions" must name a concrete fix, code-shaped where possible. If you cannot name one, you do not understand the finding well enough to post it — investigate or drop it. "Worth documenting" is not a fix. This is the same bar the posted comment's `fix:` section has to clear; see "The what/fix/why contract" in Step 6.
- If your suggested fix has a trap (the obvious change silently does nothing, or breaks an invariant elsewhere), say so here and in the posted comment. **Apply the fix and run the suite before proposing it** — on #9129 two suggested fixes were disproven exactly this way: removing an "avoidable" cast broke two tests because the no-cast precedent ran against a stubbed method, and extracting a helper onto an injected service hid the logic behind the test mock. Both would otherwise have shipped as confident advice.
- "my opinion" is required, not optional. Parker reads this to decide whether to even spend a review slot on the finding. Tie the recommendation to a real reason (scope, severity, ROI, customer impact); never just "I'd skip" with no rationale.
- No jokes, no "(may be downgrade-worthy)" asides, no "Counter:" sections, no "So: flag or skip?" editorializing.

This format gives the user control over:
- Which findings to include/skip
- Whether to combine related findings into one comment
- Whether to cross-reference other findings
- The exact tone and content of each comment
- Whether to escalate a nit to a real comment or vice versa

After walking through all findings, show the complete batch (blurb + all approved comments) for final review.

### Step 6: Draft Review as a Batch

**This step MUST happen in the main context (not a sub-agent) to preserve voice consistency.**

Based on the user's selection, assemble a single GitHub review. Inline comments already drafted and voice-styled during the Step 5b walk are reused **verbatim** — do NOT run them through the stylist again. Only NEW prose generated here (the top-level blurb, or any comment not yet drafted in 5b) MUST go through `pt-doots:voice-stylist` before being shown to Parker. The agent reads the canonical voice memories, normalizes prefixes, strips banned phrases, and returns paste-ready text. One call per draft, no batching.

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
- **Structure every comment as `what` / `fix` / `why`, in that order.** This is a hard format, not a suggestion. See "The what/fix/why contract" below.
- Skip findings already covered by another comment. Cross-reference instead.
- For pre-existing issues, check git blame to see if the PR author owns the code. If yes, "while you're in here" is fair. If not, acknowledge it's not from this PR.

**The voice-stylist agent handles voice scrubbing.** It strips banned phrases, replaces em/en dashes, swaps Latinate verbs for plain Anglo-Saxon ones, and normalizes prefixes — so don't burn cycles polishing the rough draft. Get the substance right and let the agent finish the voice pass.

**NEVER hand-edit a voice-stylist output before showing Parker.** If the output reads wrong, that's signal to either (a) fix the source draft and re-run the agent, or (b) flag a voice-stylist regression for the next `/team-audit`. Hand-editing defeats the consistency the agent provides.

### The what/fix/why contract (MANDATORY for every posted comment)

Origin: Jacob Fjermestad, repo owner, 2026-08-07 — *"your code review bot might need a little tuning on its should output, it's kind of giving JQ right now. It points at things, but doesn't really say what should be done."* A comment that only names the problem hands the diagnosis back to the author as homework. Don't do that.

Every comment has exactly three parts, in order:

    <prefix>: <one friendly line naming the scope>

    what: The problem, in plain language, with real `file:line` refs.

    fix: What to actually do. Concrete. Name the call, the value, the line.

    why: The consequence, ideally with evidence you gathered by running it.

**`fix:` is not optional, and these do NOT count as a fix:**
- "worth documenting" / "worth a should-doc" / "add a note" — that is recording the problem, not solving it
- "consider improving X" / "might be worth revisiting"
- restating the problem in imperative mood ("don't let the row go stale")

If you genuinely cannot name a fix, you do not understand the finding well enough to post it. Investigate more or drop it. The one exception is `question:`, which asks about intent and therefore has no fix.

**Where a fix has a trap, say so.** The most valuable thing in a review is the fix that looks obvious but doesn't work. Example from PR #19: the natural fix was "mark the row failed," but `mark_failed` requires `status='processing'` and the row is `pending`, so it silently does nothing. Saying that saved the author a wasted attempt. Check your own suggestion before proposing it.

### Write for readers whose first language is not English

About half of PlexTrac's developers read English as a second language. Clarity beats economy.

- **Short sentences. One idea each.** Break a two-clause sentence into two.
- **No idioms or phrasal verbs.** Not "no-ops silently", "hits the same problem", "blast radius", "dodges this", "lands", "falls through", "on the floor". Say "does nothing and gives no error", "has the same problem".
- **Plain words over Latinate ones.** "use" not "utilize", "start" not "initiate", "so" not "consequently".
- **Keep code identifiers and paths exactly as written.** Those are universal and must not be paraphrased.
- **Friendly opener.** "small thing on this constant", "two small things in this error path". Never scolding, never a lecture.
- **State findings as observations, not accusations.** "this test will pass even if the router stops using the subject" beats "you failed to test the injection".

### Make the comment paste-ready for `/should`

`what` / `fix` / `why` is also valid input to the repo's `should` skill (a change + real refs + a stated consequence). Write each comment so the author can paste it straight into `/should` with no editing when they want to defer it. That means the `why` must name a real consequence on its own, not lean on surrounding conversation.

**Other formatting rules:**
- Break comments into short paragraphs. Never post a wall of text.
- Each paragraph 1-2 sentences.
- Inline code backticks are fine but don't over-backtick.

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

## Mode 3: Self-Review

Run the full review swarm against Parker's own inflight code so he holds his own work to the same bar he holds others'. Handles multi-repo tickets (FE + BE) by treating each repo with relevant work as a separate **arm** and reviewing them in parallel. Output is saved to `{WORKSPACE}/notes/{TICKET}/` — nothing is posted to GitHub.

**Voice-stylist is skipped in this mode** — self-review notes are private to Parker, so the stylist's outbound-voice purpose doesn't apply. Findings, opinions, and action items are written raw.

### Step S1: Resolve the ticket key

Parse `$ARGUMENTS`:

- `self IO-2168` → ticket key is `IO-2168`
- `self` (alone) → auto-detect (see below)

**Auto-detect procedure:**

For each of the 5 target repos in parallel, read the current branch name:

```bash
git -C {WORKSPACE}/{repo} rev-parse --abbrev-ref HEAD
```

Extract ticket keys from each branch name using regex `[A-Z]+-\d+`. Build a frequency map.

- If exactly one ticket key is found across all repos → use it.
- If multiple ticket keys appear → list them inline (one short sentence: "Found IO-2168 on backend+frontend, ES1-1607 on mcp. Which one?") and wait for a one-word answer.
- If no ticket key is found in any branch name → tell the user "No ticket detected from current branches. Re-run as `/prs self <TICKET-KEY>`." and stop.

Store the resolved key as `TICKET`.

### Step S2: Discover arms

An **arm** is a (repo, source) pair representing one chunk of inflight work for `TICKET`. For each of the 5 target repos in parallel:

1. **Check for an open PR** — `mcp__github__list_pull_requests(owner: "PlexTrac", repo: {repo}, state: "open")`. Filter where `title` or `head.ref` contains `TICKET`. If a match exists, the arm uses the PR diff (source: `pr`).
2. **Else check for a local branch** — list branches in `{WORKSPACE}/{repo}`:
   ```bash
   git -C {WORKSPACE}/{repo} for-each-ref --format='%(refname:short)' refs/heads/ | grep -E "^${TICKET}-"
   ```
   If a single match → arm uses `branch vs origin/main` diff (source: `branch`). If multiple matches → list them and ask which one (one short prose question).
3. **Else** → skip this repo.

If after the scan there are **zero arms**:
> "No inflight work found for {TICKET} (no open PRs, no matching local branches). Stopping."

Display what was found, one line per arm, then proceed:

```
Self-review for {TICKET} — {N} arm(s):
  - product-core-backend → PR #8540 (head abc1234)
  - product-core-frontend → branch IO-2168-fe-table (5 commits ahead of main)
```

### Step S3: Fetch shared context (Jira)

Fetch the Jira ticket once (shared across arms):

```
mcp__atlassian__getJiraIssue(cloudId: "plextrac.atlassian.net", issueIdOrKey: TICKET, responseContentFormat: "markdown")
```

Extract summary, description, acceptance criteria. If the call fails, proceed without — note "Jira unavailable" in the saved file header.

### Step S4: Set up worktrees (one per arm, parallel)

For each arm, set up an isolated worktree under a self-review-specific path so they don't collide with PR-review worktrees:

```bash
WORKTREE_DIR={WORKSPACE}/.worktrees/self-{repo}-{branch_or_pr_head_ref}

# Fetch latest
git -C {WORKSPACE}/{repo} fetch origin {head_ref}

if [ -d "$WORKTREE_DIR" ]; then
    git -C "$WORKTREE_DIR" fetch origin {head_ref}
    git -C "$WORKTREE_DIR" reset --hard origin/{head_ref}
else
    git -C {WORKSPACE}/{repo} worktree add "$WORKTREE_DIR" origin/{head_ref}
fi
```

- For `source: pr` arms, `{head_ref}` is `pr.head.ref` from the GitHub API.
- For `source: branch` arms, `{head_ref}` is the local branch name. Push the branch to origin first if it doesn't exist on the remote, OR use the local ref directly (`git worktree add "$WORKTREE_DIR" {branch_name}`) — prefer the local-ref form so unpushed work is reviewable.

Store each arm's `WORKTREE_DIR` and `head_sha` (`git -C "$WORKTREE_DIR" rev-parse HEAD`).

### Step S5: Compute per-arm diffs

For each arm, produce the same diff-content shape Mode 2 inlines into agent prompts.

**PR arms:** call `mcp__github__get_pull_request_files` — identical to Mode 2.

**Branch arms:** generate the diff against `origin/main` (or the configured default branch — check `git -C "$WORKTREE_DIR" symbolic-ref refs/remotes/origin/HEAD` to confirm):

```bash
git -C "$WORKTREE_DIR" fetch origin main
git -C "$WORKTREE_DIR" diff origin/main...HEAD --name-only > /tmp/self-{repo}-files.txt
git -C "$WORKTREE_DIR" diff origin/main...HEAD > /tmp/self-{repo}-diff.patch
git -C "$WORKTREE_DIR" log origin/main..HEAD --pretty=format:"%h %s%n%b" > /tmp/self-{repo}-commits.txt
```

The commit log replaces the "PR description" input that PR arms get. Parse it into a single string the agents can read as context.

For both arm types, skip binary files and test fixtures from the diff inlined to agents (same rule as Mode 2). If the total inlined diff exceeds ~200KB, fall back to Mode 2's split-by-domain strategy.

### Step S6: Spawn the swarm — all arms in parallel

For each arm, spawn the same 5-7 reviewer agents Mode 2 uses (edge-case-qa, acceptance-qa, researcher, code-reviewer, code-smells-reviewer, conditional test-reviewer, conditional dynamic specialists). **Critical: dispatch ALL arms' agents in a single message** so they actually run concurrently — a 2-arm review is 10-14 parallel agents, not 2 sequential batches.

Use the same agent prompt templates Mode 2 uses (see Step 3 of Mode 2), with these substitutions:

- `PR title` → `Branch: {head_ref} ({N} commits ahead of main)` for branch arms; PR title as-is for PR arms.
- `PR description` → recent commit messages (from `/tmp/self-{repo}-commits.txt`) for branch arms; PR description for PR arms.
- `Jira context` → the shared Jira fetch from S3.
- `{WORKTREE_DIR}` → the arm's worktree path.
- Inline the diff content from S5 just like Mode 2 — full patches, not file lists.
- **Conventions overlay** → compute `LANG` **per arm** from that arm's changed files (S5) using the detection rule in `reference/workflow.md` § Language Detection & Conventions-Overlay Injection, and inject the resolved overlay block into that arm's writer / language-sensitive-reviewer prompts (edge-case-qa, code-reviewer, code-smells-reviewer, test-reviewer) exactly as Mode 2 Step 3 does. acceptance-qa and researcher get no overlay. Each arm is its own repo, so different arms can resolve to different overlays.

Agents return structured findings the same way. No agent needs to know about other arms.

### Step S7: Save raw findings file

Create the notes directory if needed:

```bash
mkdir -p {WORKSPACE}/notes/{TICKET}
```

Save to `{WORKSPACE}/notes/{TICKET}/self-review-{YYYY-MM-DD-HHMM}.md` (timestamped so multiple self-reviews on the same ticket don't overwrite each other):

```markdown
---
ticket: {TICKET}
mode: self-review
timestamp: {ISO 8601}
jira_status: {fetched | unavailable}
arms:
  - repo: product-core-backend
    source: pr
    pr: 8540
    head_ref: IO-2168-backend
    head_sha: abc1234
    base: main
  - repo: product-core-frontend
    source: branch
    branch: IO-2168-fe-table
    head_sha: def5678
    base: main
status: findings_ready
---

## Ticket: {TICKET}

{Jira summary + acceptance criteria, or "Jira unavailable"}

---

## Arm 1 — product-core-backend (PR #8540)

### Findings ({count})
| # | Severity | Agent | File:Line | Prior sites | Finding |
|---|----------|-------|-----------|-------------|---------|
| 1 | HIGH | code-reviewer | apps/.../jira-service.ts:142 | 2 of 14 | ... |
...

---

## Arm 2 — product-core-frontend (branch IO-2168-fe-table)

### Findings ({count})
| # | Severity | Agent | File:Line | Prior sites | Finding |
...

---

## Cross-Arm Observations

{populated in Step S8}

---

## Action Items

(walk-through pending)
```

Apply Mode 2's **Step 5a pre-promotion sanity check** to each arm's HIGH/MED findings before saving — same caller-tracing rules, same FF-gate checks, and the same 5a.0.5 convention count written into the `Prior sites` column. Track demotions per arm.

### Step S8: Cross-arm consolidation (orchestrator pass)

After all arms return, the orchestrator (still in main context — no agent spawn) scans the combined findings for **cross-arm patterns** that no single-repo agent could catch:

- **Contract mismatches**: BE response field renamed but FE still reads the old name (compare BE controller/validation changes vs FE API call sites).
- **Naming drift**: same domain concept named differently across arms (e.g. BE calls it `assetCuid`, FE calls it `asset_id`).
- **Missing FE wiring**: BE adds a new endpoint or response shape that FE doesn't appear to consume.
- **Missing BE support**: FE adds a request shape or query param BE doesn't handle.

Write findings into the `## Cross-Arm Observations` section as a short prose list (no severity, no agent attribution — these are orchestrator observations):

```markdown
## Cross-Arm Observations

- BE response in `jira-controller.ts:88` adds `lastSyncedAt` field; FE `useJiraSync.ts:42` only destructures `{ id, name, status }` and would silently drop the new field. Worth confirming it's intentional or wiring up the FE to surface it.
- BE renames `tenantCuid` → `tenant_cuid` in the validation schema (`validation.ts:67`); FE still sends `tenantCuid` from `JiraConfigForm.tsx:113`. Will 400 at runtime.
```

Skip the section entirely (drop the header) if no cross-arm observations land. Don't pad with weak observations to fill the section.

### Step S9: Present consolidated findings

Show the user a single table that groups findings by arm:

```
## Self-Review: {TICKET}
Arms: {N} | Jira: {fetched | unavailable} | Saved: {path}

### Pre-promotion sanity check
{demotions across all arms, if any — e.g. "BE HIGH on jira-service.ts:142 demoted to MED (FF gate present)"}

### Arm 1 — product-core-backend ({count} findings)
| # | Severity | File | Prior sites | Finding |
|---|----------|------|-------------|---------|
| 1 | HIGH | jira-service.ts:142 | 2 of 14 | ... |
| 2 | MED | jira-repository.ts:88 | n/a | ... |

### Arm 2 — product-core-frontend ({count} findings)
| # | Severity | File | Prior sites | Finding |
|---|----------|------|-------------|---------|
| 3 | MED | JiraConfigForm.tsx:113 | n/a | ... |

### Cross-Arm Observations
- {bullet 1}
- {bullet 2}
```

**Findings are numbered globally** (continuing across arms) so the user can say "walk #1, #3, #5" without ambiguity.

Then:
> "Want to walk through the findings, or just save the file and move on? (walk / save / pick: 1,3,5)"

### Step S10: Optional walk-through

If the user picks `walk` or `pick: ...`, walk through the selected findings one at a time using the same `### Finding N — SEV — {file:line}` format Mode 2's Step 5b uses (`what the agent said / why this matters / your suggestions / my opinion`).

**Skip the voice-stylist agent entirely in this mode.** Write `my opinion` and any captured action-item text in plain prose. Self-review output never leaves the laptop, so the stylist's purpose (consistent outbound voice) doesn't apply.

For each finding, ask: `Capture as action item, skip, or downgrade?`

- **Capture** → append to the `## Action Items` section of the saved file as `- [ ] {file:line} — {short description from the finding + any extra notes the user dictated}`.
- **Skip** → mark internally; don't write anything.
- **Downgrade** → re-categorize in the saved file (the finding stays in the findings table but gets a `~~strikethrough~~` and a brief note explaining why it was dropped).

After the walk-through, set `status: walked` in the file frontmatter and add a `walked_at: {ISO 8601}` timestamp.

### Step S11: Clean up worktrees

For each arm, remove the worktree (same as Mode 2 Step 9):

```bash
git -C {WORKSPACE}/{repo} worktree remove "$WORKTREE_DIR" --force
```

If any removal fails, leave it in place and report — don't `rm -rf`. The user can clean up manually.

### Step S12: Done

Print a one-line summary:

> "Self-review for {TICKET} saved to `{path}`. {N} findings, {M} action items captured."

If the user `save`d without walking, mention:
> "You can re-open `{path}` and run another self-review later — each run is timestamped, so nothing gets overwritten."

---

## Self-Review Notes

- **No GitHub posting.** This mode never calls the GitHub PR comment APIs. The output is local-only by design.
- **Multiple runs accumulate.** Each self-review run produces a new timestamped file under `notes/{TICKET}/`. Useful for "review → fix → review again" iterations before pushing.
- **Branch arms can be unpushed.** A local branch with no remote tracking ref still works — the worktree picks up the local commits via `git worktree add "$WORKTREE_DIR" {branch_name}`.
- **No voice-stylist invocations.** This is deliberate. Don't second-guess and route findings through it "for consistency" — Parker explicitly opted out.

---

## Error Handling

| Scenario | Behavior |
|----------|----------|
| GitHub MCP call fails (dashboard) | Show partial results for repos that succeeded, note which failed |
| GitHub MCP call fails (review) | Stop — can't review without PR data. Report the error. |
| Jira ticket key not found | Skip Jira context. Note "No Jira ticket detected" in review header. |
| Jira MCP call fails | Proceed without Jira. Note "Jira unavailable" in review header. |
| No open PRs found (dashboard) | Show "No open PRs found across PlexTrac repos." |
| Sub-agent reports idle with NO content | **Presume it FINISHED — this is a harness delivery bug, not an agent failure.** Recover the report by parsing `subagents/agent-<name>-*.jsonl` for the last assistant text block (or the last `SendMessage` payload). Never `Read` the `.output` file, it symlinks the whole transcript and overflows context. Do NOT re-spawn, and do NOT fall back to a `general-purpose` agent — it fails identically. Full procedure and the script: `commands/pt-doots.md` § When Agents Fail. |
| Sub-agent genuinely fails mid-work (transcript ends unfinished) | Report which agent failed. Present findings from agents that succeeded. |
| Review post fails | Show error, keep state at `drafting` for retry. |
| Invalid PR URL format | Show usage message. |
| PR URL from non-PlexTrac repo | Show: "This PR is not in a PlexTrac repo. Supported repos: {list}" |
| Self-review: no ticket detected | "No ticket detected from current branches. Re-run as `/prs self <TICKET-KEY>`." and stop. |
| Self-review: no arms found | "No inflight work found for {TICKET} (no open PRs, no matching local branches). Stopping." |
| Self-review: multiple branches match in one repo | List them and ask which one (single prose question). |
| Self-review: worktree add fails | Report the error per-arm; continue with arms that succeeded. If all arms fail, stop. |

---

## Context Management

The command is split between lightweight orchestrator (main context) and heavyweight analysis (sub-agents):

- **Main context:** Dashboard display, findings presentation, comment drafting (voice-sensitive), approval gate, posting
- **Sub-agents:** All code review analysis (5-6 parallel agents), context gathering where needed

This keeps the orchestrator lean and avoids context exhaustion from dumping full diffs into the main conversation.
