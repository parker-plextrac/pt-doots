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

**Target repos:**

| Repo | Slug |
|------|------|
| product-core-backend | `PlexTrac/product-core-backend` |
| product-core-frontend | `PlexTrac/product-core-frontend` |
| product-services-export | `PlexTrac/product-services-export` |
| product-services-mcp | `PlexTrac/product-services-mcp` |

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

Make **parallel** GitHub MCP calls across all 4 target repos. For each repo:

```
mcp__github__list_pull_requests(owner: "PlexTrac", repo: "{repo_name}", state: "open")
```

From the results, split into two lists:
- **Your PRs**: PRs where `user.login` is `parker-plextrac`
- **Requesting Your Review**: PRs where `requested_reviewers` includes `parker-plextrac`

For each PR in **Your PRs** only, also fetch CI status:

```
mcp__github__get_pull_request_status(owner: "PlexTrac", repo: "{repo_name}", sha: "{head.sha}")
```

Launch these status calls in parallel.

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
- If `status` is `posted`: ignore the file, start fresh
- If `status` is `findings_ready` or `drafting`:
  1. Get the current PR head SHA via `mcp__github__get_pull_request`
  2. Compare with the saved `head_sha` from the file
  3. If they differ, count new commits:
     ```bash
     /opt/homebrew/bin/gh api repos/{owner}/{repo}/compare/{saved_sha}...{current_sha} --jq '.ahead_by'
     ```
  4. Present the resume prompt:
     > "Found an in-progress review for #{pr_number} from {date} ({N} new commits since then). Status: {status}. Resume where you left off, or start fresh?"
  5. If "resume": always run Step 2 (Context Gathering) first — this includes both branch checkout (2b) and PR metadata (2a). The branch checkout ensures agents run on the correct code even if the user switched branches between sessions. Then jump based on status: `findings_ready` → Step 5, `drafting` → Step 6. Skip Step 3 (the expensive agent work) since findings are already saved.
  6. If "fresh": proceed to Step 2

If no file found, proceed to Step 2.

### Step 2: Context Gathering

#### 2a: Fetch PR metadata (lightweight — runs first)

**Call 1 must run before anything else** — it provides `{head_ref}` (the PR branch name) needed by Step 2b.

**Call 1:** `mcp__github__get_pull_request` — get PR title, description, author, base branch, head ref/branch name, head SHA, draft status

Store `{head_ref}` from the response's `head.ref` field. This is the branch name to checkout in Step 2b.

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

#### 2b: Checkout PR branch

The orchestrator may be in any directory. After Call 1 completes and `{head_ref}` is known:

```bash
# 1. Save current branch BEFORE changing anything
PREVIOUS_BRANCH=$(git -C {WORKSPACE}/{repo} rev-parse --abbrev-ref HEAD)

# 2. cd to the repo and checkout the PR branch
cd {WORKSPACE}/{repo}
git fetch origin {head_ref}
git checkout {head_ref}
```

**Order matters:** capture `PREVIOUS_BRANCH` before `cd` and `checkout` — otherwise you'll record the PR branch, and Step 9's restore will be a no-op.

If the checkout fails (e.g. local changes), report the error and ask the user — do NOT proceed with agents on the wrong branch.

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
1. Confirm `pwd` is `{WORKSPACE}/{repo}` — if not, `cd` there
2. Confirm the PR branch is checked out: `git rev-parse --abbrev-ref HEAD` should match `{head_ref}`
3. If either check fails, fix it before spawning agents. Do NOT proceed with agents on the wrong branch or in the wrong directory.

**Context strategy:** For each agent, prepare the full diff content from Call 2 and **inline it directly in the prompt**. Agents should NOT need to read files or run git commands to find the changed code — give them everything they need upfront. They CAN read additional files for surrounding context (e.g., CLAUDE.md, imports, types), but the diff itself must be in the prompt.

For PRs with very large diffs (>200KB of patch content), split files across agents by domain instead of duplicating the entire diff to all 4. Note which agent got which files.

Launch **4 parallel sub-agents** via the Agent tool. Each agent returns **structured findings ONLY** — no posting, no GitHub interaction.

---

**Agent 1 — Bug Scanner**

```
You are reviewing PR #{pr_number} in {owner}/{repo} for bugs.

PR title: {title}
PR description: {description}

The repo is at {WORKSPACE}/{repo} on branch {head_ref}. You can read files for additional context.

Changed files and their diffs:
{paste file list and FULL diff/patch content from Call 2 — skip binary files and test fixtures}

Instructions:
1. Analyze each changed file's diff carefully
2. If you need surrounding context (imports, types, called functions), read those files — but do NOT re-read files whose diffs are already provided above
3. Look for bugs: logic errors, off-by-one, null/undefined access, race conditions, resource leaks
4. Focus on significant bugs — ignore things a linter or typechecker would catch
5. Ignore style issues, naming, formatting
6. For each bug found, return a line in this format:

FINDING | severity: HIGH/MED/LOW | file: path/to/file.ts | line: 45 | description

If no bugs found, return: NO_FINDINGS
```

---

**Agent 2 — Data Flow Analyzer (HIGHEST PRIORITY)**

```
You are reviewing PR #{pr_number} in {owner}/{repo} for data flow issues. This is the highest-priority review.

PR title: {title}
PR description: {description}
Jira context: {jira_summary_and_acceptance_criteria OR "No Jira ticket"}

The repo is at {WORKSPACE}/{repo} on branch {head_ref}. You can read files for additional context.

Changed files and their diffs:
{paste file list and FULL diff/patch content from Call 2 — skip binary files and test fixtures}

Instructions:
1. Identify the PR's core claim — what behavior does it say it changes?
2. Trace the data flow through ALL changed files, prioritizing:
   - Repository/data layer files (highest priority)
   - Service layer files
   - Mapping/cosmetic files (lowest priority)
3. Verify the PR's claims against the actual code — does the code do what the description says?
4. Look for these specific red flags:
   - .map() over items sharing a key/ID (stale state bug — should be .reduce() or sequential accumulation)
   - Promise.all() over items with shared mutable state
   - Upsert logic that drops fields or overwrites when it should merge
   - Tests that only use 1 item per key when production sends many
5. Check that tests match real data shapes, not just happy path
6. For each issue found, return a line in this format:

FINDING | severity: HIGH/MED/LOW | file: path/to/file.ts | line: 45 | description

If no issues found, return: NO_FINDINGS
```

---

**Agent 3 — History & Context**

```
You are reviewing PR #{pr_number} in {owner}/{repo} using git history context.

The repo is at {WORKSPACE}/{repo} on branch {head_ref}.

Changed files:
{list of changed file paths}

Instructions:
1. For each changed file, run git blame on the modified sections to understand history
2. Check for previous PRs that touched these files — look for recurring issues or patterns
3. Read code comments in the modified files — check if the changes comply with guidance in comments
4. Look for TODO/FIXME/HACK comments the PR should have addressed
5. For positive observations (good patterns, thorough tests), use severity "NICE"
6. For each issue or observation, return a line in this format:

FINDING | severity: HIGH/MED/LOW/NICE | file: path/to/file.ts | line: 45 | description

If no issues found, return: NO_FINDINGS
```

---

**Agent 4 — CLAUDE.md Compliance**

```
You are reviewing PR #{pr_number} in {owner}/{repo} for CLAUDE.md compliance.

The repo is at {WORKSPACE}/{repo} on branch {head_ref}. You can read files for additional context (especially CLAUDE.md files).

Changed files and their diffs:
{paste file list and FULL diff/patch content from Call 2 — skip binary files and test fixtures}

Instructions:
1. Read the workspace CLAUDE.md at {WORKSPACE}/CLAUDE.md — this is the authoritative cross-repo standards file. Also check for a repo-specific CLAUDE.md at {WORKSPACE}/{repo}/CLAUDE.md if it exists.
2. Read any CLAUDE.md files in directories containing changed files
3. Check changes against ONLY rules explicitly stated in those CLAUDE.md files
4. Do NOT invent rules — only flag violations of things the CLAUDE.md explicitly requires
5. Common things to check:
   - TypeScript: no `as any`, no `as unknown as T`, proper use of Pick for narrowing
   - Python: type hints, f-strings, SOLID principles
   - Testing patterns: co-location, naming, coverage
   - Layer rules: services don't import repositories from other domains, etc.
6. For each violation, return a line in this format:

FINDING | severity: MED/LOW | file: path/to/file.ts | line: 45 | description — CLAUDE.md says: "exact quote"

If no violations found, return: NO_FINDINGS
```

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

Show the consolidated findings table:

```
## Review: #{pr_number} {ticket_key} — {pr_title}
Jira: {ticket_key} | Author: @{author} | Files: {file_count} | Base: {base_branch}

### Findings ({count})
| # | Severity | File | Finding |
|---|----------|------|---------|
| 1 | HIGH | file.ts:45 | Description of the issue |
| 2 | MED | other-file.ts:112 | Description |
| 3 | NICE | test-file.ts | Positive observation |
```

If **no findings** (all agents returned NO_FINDINGS):
> "No issues found! This PR looks clean. Want to leave an approving review, or skip?"

Otherwise:
> "Which findings do you want to comment on? (e.g. '1, 3' or 'all' or 'none')"

If "none": ask if they want a top-level comment only, approve, or skip entirely.

### Step 6: Draft Review as a Batch

**This step MUST happen in the main context (not a sub-agent) to preserve voice consistency.**

Based on the user's selection, draft a single GitHub review:

#### Top-level blurb

Write a 2-3 sentence review comment that:
- Calls out what the PR does well (specific, not generic praise)
- Sets the tone for inline comments ("Left a couple small thoughts inline but nothing blocking")
- Sounds like Parker — warm, collaborative

#### Inline comments

For each selected finding, rewrite it as a review comment in Parker's voice:

**Voice rules:**
- Use: "Hey!", "Would it be worth...", "Just wanted to flag", "Just thinking out loud", "Totally not blocking"
- Frame feedback as observations: "feels a bit heavy-handed" NOT "you should change this"
- No CLAUDE.md citations — frame as personal observations
- For nits, use playful language
- Skip findings that would just add noise — fold them into the blurb if worth mentioning

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
- "approve" → event: `APPROVE`

### Step 8: Post Review

Build the review payload using Python to avoid all shell escaping issues.

Since review agents no longer produce diff positions, all findings are posted in the review body (not as inline comments). Format each finding as a body section with file:line reference:

```bash
python3 -c "
import json

# Build the body: blurb first, then each finding as a section
body_parts = [
    '''BLURB_TEXT_HERE''',
]

# Append each selected finding as a body section
# findings = [('path/to/file.ts', 45, 'comment text'), ...]
# for path, line, text in findings:
#     body_parts.append(f'**{path}:{line}** — {text}')

payload = {
    'event': 'COMMENT',  # or 'APPROVE' if user chose to approve
    'body': '\n\n'.join(body_parts),
}

with open('/tmp/pr-review.json', 'w') as f:
    json.dump(payload, f)
"
```

Substitute the actual blurb text and finding details into the Python script at dispatch time. The triple-quoted string handles newlines and special characters safely.

Post the review:
```bash
/opt/homebrew/bin/gh api repos/{owner}/{repo}/pulls/{pr_number}/reviews \
  --method POST \
  --input /tmp/pr-review.json
```

Clean up:
```bash
rm /tmp/pr-review.json
```

**If the post succeeds:**
- Update the review file: `status: posted`, add `posted_at` timestamp
- Tell the user: "Review posted! [View it here](https://github.com/{owner}/{repo}/pull/{pr_number})"

**If the post fails:**
- Show the error
- Keep review file at `status: drafting` for retry
- "Want to try posting again, or save the draft for later?"

### Step 9: Restore Original Branch

**This step runs ALWAYS** — after posting, after a failed post, or if the user skips posting at Step 7. The user should not be left on the PR branch after a review.

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
- **Sub-agents:** All code review analysis (4 parallel agents), context gathering where needed

This keeps the orchestrator lean and avoids context exhaustion from dumping full diffs into the main conversation.
