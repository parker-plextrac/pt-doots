# pt-doots Codex Compatibility Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make every current `pt-doots` command and agent available in Codex from the live local checkout without changing the existing Claude Code workflow.

**Architecture:** Existing Claude command and agent files remain canonical during
Phase 1. A Codex skills plugin wraps all six commands, checked-in custom-agent
adapters load all 15 canonical agent prompts, and an idempotent onboarding
script installs direct named-agent `config_file` registrations plus the local
plugin. A parity validator derives both inventories from disk and fails on
missing, stale, duplicated, or invalid adapters.

**Tech Stack:** Markdown Agent Skills, Codex plugin JSON, Codex custom-agent
TOML, Python 3 standard library, TOML configuration updates, `unittest`, Codex
CLI validation.

---

### Task 1: Define compatibility contracts with failing tests

**Files:**
- Create: `tests/test_codex_compat.py`
- Create: `scripts/validate_codex_compat.py`
- Modify: `.gitignore`

**Step 1: Write inventory tests**

Derive commands from `commands/*.md` and agents from top-level `agents/*.md`. Assert each command has exactly one `skills/<name>/SKILL.md` and each agent has exactly one `codex/agents/<name>.toml`. Report the current six-command/15-agent counts diagnostically, but calculate parity from the filesystem.

**Step 2: Run the tests and verify failure**

Run: `python3 -m unittest tests/test_codex_compat.py -v`

Expected: FAIL because the Codex adapters do not exist.

**Step 3: Implement validator primitives**

Use the standard library for inventory discovery, Markdown frontmatter parsing, TOML parsing with `tomllib`, relative-reference validation, and actionable CLI errors. Add tests for malformed and missing adapters.

**Step 4: Run focused tests**

Expected: validator-unit tests pass while adapter-parity assertions still fail.

**Step 5: Commit**

```bash
git add tests/test_codex_compat.py scripts/validate_codex_compat.py .gitignore
git commit -m "test: define Codex compatibility contracts"
```

### Task 2: Add the Codex manifest and all command skills

**Files:**
- Create: `.codex-plugin/plugin.json`
- Create: `skills/{pt-doots,prs,bootstrap-team,team-audit,voice-profile,publish-docs}/SKILL.md`
- Modify: `tests/test_codex_compat.py`

**Step 1: Extend tests**

Assert valid manifest metadata, `skills: "./skills/"`, exact command-name parity, valid skill frontmatter, and one canonical `commands/<name>.md` reference per wrapper. Reject copied workflow bodies with a small wrapper-size ceiling.

**Step 2: Run and verify failure**

Expected: FAIL on missing manifest and skills.

**Step 3: Create the manifest and six wrappers**

Reuse the existing plugin identity/version. Each wrapper must read its canonical command file completely, load `reference/codex-compatibility.md`, preserve arguments and gates, and contain no duplicated workflow logic.

**Step 4: Validate**

```bash
python3 -m unittest tests/test_codex_compat.py -v
python3 "$HOME/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py" .
```

Expected: command/plugin checks pass; agent checks still fail.

**Step 5: Commit**

```bash
git add .codex-plugin skills tests/test_codex_compat.py
git commit -m "feat: add Codex command skills"
```

### Task 3: Add all named Codex agent adapters

**Files:**
- Create: `codex/agents/*.toml` for every top-level `agents/*.md`
- Modify: `tests/test_codex_compat.py`

**Step 1: Extend mapping tests**

For each canonical agent, assert:

- Matching name and description.
- `haiku → gpt-5.6-luna`, `sonnet → gpt-5.6-terra`, `opus → gpt-5.6-sol`.
- Reasoning effort is preserved.
- Read-only roles declare `sandbox_mode = "read-only"`; writers declare the minimum intended write sandbox. These declarations are forward-compatible intent metadata and are not a security boundary in the current runtime.
- `developer_instructions` names `pt-doots/agents/<name>.md`, requires reading it in full, states the original `maxTurns` interaction budget, and forbids autonomous continuation after a partial/blocked report.

**Step 2: Run and verify failure**

Expected: FAIL for every missing adapter.

**Step 3: Create all adapters**

Keep them metadata-only. Each detects the PlexTrac workspace and reads the canonical definition from the sibling `pt-doots` checkout. Every spawn is one task turn. On budget exhaustion it returns the canonical structured output marked `PARTIAL` or `BLOCKED`; only the orchestrator may request a follow-up.

**Step 4: Run tests and commit**

```bash
python3 -m unittest tests/test_codex_compat.py -v
git add codex/agents tests/test_codex_compat.py
git commit -m "feat: add Codex agent adapters"
```

### Task 4: Codify runtime translation without copying the harness

**Files:**
- Create: `reference/codex-compatibility.md`
- Modify: all six `skills/*/SKILL.md`
- Modify: `tests/test_codex_compat.py`

**Step 1: Write failing mapping checks**

Require the compatibility reference to cover named-agent dispatch, model/budget mapping, canonical-file loading, inline context, pre-dispatch progress saves, flag-and-wait, the completion barrier, worktree behavior, tool-name differences, shared telemetry, and the canonical REST-over-Atlassian-MCP rule.

**Step 2: Run and verify failure**

Expected: FAIL because the mapping reference is missing.

**Step 3: Write only runtime-specific mappings**

Reference rather than repeat these harness contracts: orchestrator never reads/writes product code, synchronous persistence before dispatch, full inline context, parallel quality gate, wait for real reports, mandatory repro verification, mechanical documentation gate, and `${HOME}/.claude/pt-doots` shared Phase 1 telemetry.

**Step 4: Link every skill wrapper to the mapping**

Require canonical command first, compatibility mapping second, and canonical behavior on any non-runtime conflict.

**Step 5: Run tests and commit**

```bash
python3 -m unittest tests/test_codex_compat.py -v
git add reference/codex-compatibility.md skills tests/test_codex_compat.py
git commit -m "docs: define Codex orchestration mapping"
```

### Task 5: Build safe live-checkout onboarding

**Files:**
- Create: `scripts/setup_codex.py`
- Create: `tests/test_setup_codex.py`
- Create: `.agents/plugins/marketplace.json`

**Step 1: Write failing installer tests**

Against a temporary home, assert setup creates direct
`~/.codex/config.toml` named-agent `config_file` registrations for every
adapter, preserves unrelated TOML and agent registrations, fails closed on name
collisions, is idempotent, supports `--dry-run`, removes only installer-owned
registrations, validates parity before mutation, and can operate in
`--agents-only` mode.

**Step 2: Run and verify failure**

Run: `python3 -m unittest tests/test_setup_codex.py -v`

Expected: FAIL because setup is absent.

**Step 3: Implement setup/removal**

Resolve the checkout from `__file__`, never a Parker-specific path. Use
explicit `pathlib` targets. Fail closed on collisions. Run parity validation
first. Register every live adapter through direct named `config_file` entries,
then use supported Codex CLI commands for the repo-local marketplace/plugin
registration.

**Step 4: Add the local marketplace**

Create one repo-scoped local entry pointing to the checkout root with required policy/category metadata. This is development onboarding, not publishing.

**Step 5: Run tests twice and commit**

```bash
python3 -m unittest tests/test_setup_codex.py -v
python3 scripts/setup_codex.py --dry-run
python3 scripts/setup_codex.py --dry-run
git add scripts/setup_codex.py tests/test_setup_codex.py .agents/plugins/marketplace.json
git commit -m "feat: add live Codex onboarding"
```

### Task 6: Update repository and onboarding documentation

**Files:**
- Modify: `README.md`
- Modify: `CLAUDE.md`
- Modify: `OVERLAYS.md`
- Modify: `docs/plans/2026-09-03-codex-compatibility-design.md`
- Create: `docs/codex-onboarding.md`
- Modify: `tests/test_codex_compat.py`

**Step 1: Add failing documentation checks**

Require Claude onboarding, Codex onboarding, compatibility boundaries, live reloads, canonical ownership, model mappings, advisory budget limitation, parity validation, troubleshooting, and the deferred platform-neutral design.

**Step 2: Run and verify failure**

Expected: FAIL for missing sections.

**Step 3: Write documentation**

Preserve current Claude setup. Add a Codex quickstart, prerequisites, verification, reload/new-thread behavior, permissions/hooks, supported commands/agents, maintenance rules, and troubleshooting. State honestly that Codex cannot hard-enforce `maxTurns` in custom-agent metadata.

**Step 4: Apply README quality guidance**

Use the software-readme skill to check cold-start usability, examples, prerequisites, verification, and troubleshooting.

**Step 5: Run tests and commit**

```bash
python3 -m unittest discover -s tests -v
git add README.md CLAUDE.md OVERLAYS.md docs tests/test_codex_compat.py
git commit -m "docs: add Codex onboarding and maintenance"
```

### Task 7: Install and verify the live integration

**Files:**
- Modify if evidenced: adapter/setup/docs files only

**Step 1: Run all static validation**

```bash
python3 -m unittest discover -s tests -v
python3 scripts/validate_codex_compat.py
python3 "$HOME/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py" .
jq empty .claude-plugin/plugin.json .claude-plugin/marketplace.json .codex-plugin/plugin.json .agents/plugins/marketplace.json
python3 -m py_compile scripts/*.py
```

Expected: all commands pass.

**Step 2: Install from this checkout**

Run: `python3 scripts/setup_codex.py`

Expected: every owned named-agent `config_file` entry targets this checkout and
Codex reports the local plugin installed/enabled.

**Step 3: Verify discovery**

Using supported Codex inspection commands, confirm all six skills and every derived agent are visible from the PlexTrac workspace.

**Step 4: Smoke-test non-mutating paths in a fresh thread**

Exercise status/dry-run paths for `pt-doots`, `prs`, `team-audit`, `voice-profile`, `publish-docs`, and `bootstrap-team`. Confirm canonical files load, named agents route to the expected models and reasoning effort, and the orchestrator does not touch product code.

Run a reversible fresh-session canary with a uniquely registered temporary
agent and unpredictable response instruction. Confirm collaboration dispatch
selects that registered instruction and that runtime debug metadata identifies
the configured child model and reasoning effort independently from the parent.
Also test a restrictive child sandbox against a broader parent session. Record
the observed limitation without committing tokens, temporary paths, or
machine-specific values: the current runtime applies the named instructions,
model, and reasoning effort but does not enforce the child's `sandbox_mode`.

**Step 5: Verify Claude remains intact**

Validate existing Claude manifests and confirm no canonical command/agent behavior changed. The user's voice-stylist edits in the main checkout remain untouched.

**Step 6: Fix evidenced failures test-first**

For each failure, add/tighten a test, make the smallest adapter correction, and rerun Steps 1–5.

**Step 7: Commit verification fixes**

```bash
git add .
git commit -m "test: verify dual-runtime pt-doots support"
```

### Task 8: Final review and handoff

**Files:**
- Review: all branch changes

**Step 1: Audit scope**

Run: `git diff --stat main...HEAD && git status --short`

Expected: only adapters, setup/validation tooling, and documentation changed; worktree clean.

**Step 2: Repeat the full validation suite**

Record concise pass/fail evidence.

**Step 3: Check acceptance criteria**

Confirm all six commands, every canonical agent, model and reasoning routing,
bounded-agent instructions, the non-enforced per-agent sandbox limitation,
shared telemetry, live named-agent registrations, parity detection, and both
onboarding paths.

**Step 4: Prepare handoff**

Summarize commits, evidence, reload requirements, the advisory Codex budget limitation, and the deferred platform-neutral design. Do not merge into the main checkout without user approval.
