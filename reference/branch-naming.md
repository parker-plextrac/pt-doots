# PlexTrac Branch Naming

Use when creating a branch for a Jira ticket in the PlexTrac workflow.

## Standard

- **Pattern**: `{issue-key}-{short-kebab-description}`
- **Issue key**: Jira key, e.g. `IO-2097` (uppercase, as in Jira).
- **Short description**: 2–4 words in kebab-case, derived from ticket title. No need to repeat the key.

## Examples

- `IO-2097-export-to-csv`
- `IO-2098-login-timeout-error`
- `IO-2099-upgrade-react-deps`

## Rules

- Branch from the default branch (usually `main` or `master`) unless the user specifies otherwise.
- If the repo uses a different convention (e.g. `IO-2097/export-to-csv`), follow the repo’s existing pattern when visible in `git branch`; otherwise use this standard.
- Confirm the branch name with the user before creating if the ticket title is ambiguous.
