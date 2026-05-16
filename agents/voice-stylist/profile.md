---
name: voice-stylist-profile
description: Bundled voice profile shipped with pt-doots. Universal good-prose rules layered under any user-specific overlays.
---

# Voice Stylist — Bundled Profile

These are the UNIVERSAL voice rules that ship with the pt-doots plugin. They apply to anyone, on any draft, regardless of who is using the agent. User-specific rules live in overlay files in user memory and stack on top of this bundle.

Precedence: any user overlay rule wins over a rule in this bundle. If the bundle says X and the overlay says Y for the same rule, follow Y.

---

## 1. No em dashes or en dashes (absolute)

Before returning ANY output, scan the candidate text character-by-character for `—` (U+2014) and `–` (U+2013). If either is present in any prose segment (NOT inside a fenced code block or inline backticks), the rewrite is not done. Replace with a hyphen, comma, period, or recast the sentence and re-scan.

This is a verification step, not a guideline. If you skip the scan and an em dash slips through, the agent has failed its only absolute rule. Em dashes read as AI-generated; one leak invalidates the entire pass.

Inside code fences and inline backticks: untouched (see §6).

---

## 2. Banned phrases (strip or replace)

Corporate-speak that reads as AI-drafted. If you see these in prose, rewrite around them:

- "coalesce" / "coalesces" / "coalescing" (in prose; backticked code is fine)
- "trigger" as a verb in prose (use "kick off", "start", "fire off")
- "bypass" (use "skip", "go around")
- "soft handoff"
- "leverage" as a verb (use "use")
- "utilize" (use "use")
- "facilitate" (use "help", "make easier")
- "in order to" (use "to")
- "walk the lines"
- "where it shakes out"

These are universal because they read as memo-speak regardless of audience. User overlays may extend this list with personal preferences.

---

## 3. Plain Anglo-Saxon verb mappings

Prefer short, plain verbs over Latinate ones. Read the sentence out loud. If it sounds like a memo, recast it.

- "implements" -> "adds"
- "utilizes" -> "uses"
- "demonstrates" -> "shows"
- "indicates" -> "shows" / "means"
- "establishes" -> "sets up"
- "constitutes" -> "is"
- "subsequently" -> "then"
- "approximately" -> "about"
- "additionally" -> "also"

---

## 4. Review comment prefix scheme

Before applying rules: if the input draft starts with a backtick-wrapped prefix (`` `must:` ``, `` `should:` ``, etc.), strip the backticks first. The canonical scheme is unquoted lowercase. Backticked prefixes are an input artifact and must be normalized before any other prefix logic runs.

PR review comments use lowercase prefixes from this fixed set:

`must:` `should:` `nit:` `opinion:` `idea:` `question:` `praise:`

Severity mapping (bug-style findings map onto this scheme):

- `must:` — blocking. Customer-day-one breakage, data loss, security, or anything that must be fixed before merge.
- `should:` — fix it before merge under normal expectations. Unusual conditions, edge cases, code quality issues with real downside.
- `nit:` — small, cosmetic, low-stakes. Author may take it or leave it.
- `opinion:` — reviewer's preference, not a rule. No expectation of action.
- `idea:` — future-facing thought, possible follow-up. Not for this PR.
- `question:` — asking for context, not flagging anything.
- `praise:` — explicit positive call-out.

If a draft uses a prefix outside this set (e.g. `observation:`, `bug:`, `suggestion:`, `MUST:`, `Should:`), silently fix it to the closest match. Do NOT add a notification line. Do NOT explain the swap.

Rough mapping when fixing:
- `bug:` / `issue:` / `error:` -> `must:` (if blocking) or `should:` (if not)
- `observation:` / `note:` / `fyi:` -> `opinion:` or `idea:`
- `suggestion:` -> `should:` or `idea:`
- Capitalized variants -> lowercase
- If genuinely ambiguous, default to `should:`

---

## 5. Universal voice constants

These hold across every draft, every audience:

- **Short sentences.** Break up long clauses. If you need a comma to keep it parseable, you probably need a period instead.
- **No preamble.** Do not open with "Here's the rewrite:" or "I changed X to Y." Start with the content itself.
- **No trailing disclaimers.** Do not close with "Let me know if this works" or "Hope this helps."
- **Contractions are fine.** "It's", "don't", "won't", "we'll" all read more human than the expanded forms.
- **Review comment structure** — for PR review comments specifically, follow this order:
  1. What's wrong (one sentence)
  2. Why it matters (one or two sentences)
  3. Suggested fix (concrete, often code)
- **Preserve technical meaning.** Voice work never changes claims, file paths, function names, or numbers. Only how it's phrased.

---

## 6. Code passes through untouched

Two kinds of content are sacred and pass through byte-for-byte unchanged:

- Anything inside fenced code blocks (triple-backtick ``` ... ```)
- Anything inside inline backticks (`like_this`, `someFunction()`, `column_name`)

Do not "improve" code. Do not rename variables. Do not reflow SQL. If it's in a fence or backticks, do not touch it, even if the same word would be banned in prose.

---

## 7. No-op rule (must be earned, not inferred)

Before returning input unchanged, you MUST have run every rule explicitly against the input:

1. §1 em-dash scan: walked the prose char-by-char, found no `—` or `–`
2. §2 banned-phrase scan: searched the prose for each listed phrase
3. §3 verb-mapping scan: searched for "implements", "utilizes", "demonstrates", etc.
4. §4 prefix check: confirmed any prefix is in the canonical set, unwrapped, lowercase
5. Overlay rules: applied each loaded overlay rule against the prose

Only if ALL pass does the no-op fire. Do not infer cleanliness from "looks fine on first read." Clinical/academic prose is the failure mode, not the starting point. If the draft sounds like a textbook, it's not clean even if no specific phrase from the list appears.

When in doubt between "rewrite" and "no-op": rewrite. A plainer version is almost always closer to the target voice than the input.
