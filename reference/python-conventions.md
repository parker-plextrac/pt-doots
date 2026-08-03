# Python conventions overlay

Loaded by pt-doots agents for Python code — the implementer and test-writer read this when
writing `.py`; the reviewers (code-reviewer, code-smells-reviewer, test-reviewer, edge-case-qa)
read it when the changed files are Python. It is the **baseline** conventions layer for all Python
in this workspace — see the precedence rule immediately below.

## Precedence — this is the baseline; the repo's committed standard wins

**This overlay is the baseline only.** When you work in a specific repo, that repo's **own
committed coding standard is authoritative and overrides this overlay for that repo.**

- **Read the target repo's `CLAUDE.md` first** — plus any committed standards doc or `.claude/rules`
  in the repo — and defer to it wherever it speaks. This overlay fills the gaps the repo's own
  standard leaves; it never displaces it.
- **Do not go rogue.** Never impose this overlay's version of a rule over a repo's committed
  standard. If the repo says something different, the repo is right for that repo — follow it and,
  if the divergence looks like a real gap, flag it rather than silently overriding.
- **zenith-inbound-service specifically:** the How-to-Code standard is encoded here from memory
  (`feedback_zenith_inbound_coding_standard.md`) as today's baseline, because it is not yet
  committed into that repo. It **will** land in the repo's `CLAUDE.md` / a rules doc. **Once it
  does, the committed repo copy is the source of truth** — always check the repo's `CLAUDE.md`,
  because the committed standard may have evolved past what is captured here. This is principle #7
  ("check the source, don't recall it") applied to the standard itself.

Three invariants hold everywhere **within this overlay** (they describe how this file is written;
they do not override a repo's committed standard):

- **One standard, no repo gating.** There are no "in repo X do this / in repo Y do that" blocks.
  The same calibration applies to every Python file regardless of which service it lives in.
- **No size caps.** There is no function-length, class-length, or method-count limit anywhere in
  this file. Readability is hops, not lines (see below). Do not flag or split code for being
  "too long."
- **Framework rules trigger on the framework the code actually uses**, never on which repo it is.
  If a file imports Pydantic, the Pydantic rules apply to it; if it does not, they do not. The
  same for structlog, orjson, respx, and pytest-asyncio.

---

## How to code (the calibration that comes first)

This is the team's "How to Code" philosophy and it governs everything below it. It deliberately
**inverts** the old size-cap / forced-decomposition rules — those are retired. When any guidance
elsewhere seems to pull toward more types or smaller units, this section wins.

- **Readability is hops, not lines.** Optimize for the number of jumps a reader makes to
  understand a change: fewer types, fewer files, fewer indirections. A cohesive 60-line class or a
  40-line function that reads straight through is *better* than four 15-line pieces the reader has
  to reassemble. **Never split a cohesive unit just for length — there is no length limit here.**
  Long is not a smell; scattered is.

- **A name must earn itself.** Introduce a new type, class, or abstraction only if you would say
  its name aloud while explaining the system. "The subscriber subscribes" earns no `Subscriber`
  type — it is just a function. Prefer fewer types; an extra name the reader must learn is a cost,
  not a courtesy.

- **Name modules for their subject, never their role.** Banned module names: `utils`, `helpers`,
  `common`, `shared`, `misc`, `base`. Test a module name by asking, from the name alone, whether
  you can tell what belongs in it. `retry`, `pagination`, `ocsf_mapping` pass; `helpers` fails
  because anything could land there.

- **Classes hold state.** Reach for a class when there is state or a lifecycle to own (a
  connection, a running task, a buffer) or real data to model. A one-method, no-state class is a
  function wearing a costume — write the function. A well-named module of free functions is good
  Python, not a design gap to "fix" by wrapping it in a class.

- **Model a closed set of strings as `Literal[...]`, not a `StrEnum`.** A fixed set of string
  constants — a `status` or a `job_type`, say — is a `Literal["open", "closed", ...]`, not a
  `StrEnum`, now that the old "consolidate strings into an enum" rule is retired.

- **Inject at the edges, construct in the middle.** The composition root wires only what crosses
  the process boundary — network, disk, clock, subprocess — plus anything pluggable by design.
  Logic you own is not injected: call it and test it directly. A `Callable` is a perfectly good
  injected dependency; a dependency need not be a class or an interface.

- **Mock behavior, build data.** Build DTOs, models, and value objects for real (or as small
  fakes); mock only behavior-carrying collaborators. Never invent a type just so a test can mock
  it. (Full testing form below.)

- **Check the library, don't recall it.** For unfamiliar or correctness-critical APIs — signatures,
  config keys, ack/retry/pagination semantics — pull the current docs via context7 rather than
  writing from memory. Getting the contract wrong is a bug the type checker will not catch.

---

## Python hygiene (universal)

Applies to every Python file.

- **Docstrings — PEP 257 shape.**
  - Public modules, classes, and methods/functions get a docstring. A one-line docstring is
    imperative ("Return the parsed report.", not "Returns…") and keeps its closing `"""` on the
    **same line** as the text.
  - Non-public (leading-underscore) methods do **not** get a docstring — put a `#` comment after
    the `def` line if anything needs saying.
  - Comments explain the non-obvious **why**, not the **what**. If a comment restates the code,
    delete it; if the code needs a comment to be understood, prefer clearer code first.
- **PEP 8** for layout and naming: `snake_case` for functions/variables, `UPPER_SNAKE_CASE` for
  constants, `PascalCase` for classes.
- **f-strings** for all string interpolation. No `%` formatting or `str.format` in new code.
- **Chain exceptions:** `raise NewError(...) from exc` on every re-raise so the original traceback
  survives. A re-raise that drops the cause is a defect.
- **No swallowing errors:** no bare `except:` and no `except Exception: pass`. Catch the narrowest
  exception you can act on; if you catch, either handle it, log it, or re-raise with `from`.
- **No `Any`.** Do not annotate with `: Any` or `-> Any` unless the type is genuinely
  unknowable at that boundary — and then narrow it as soon as you can (`object`, a `Protocol`, a
  `TypedDict`, or a real model is almost always better). `Any` disables the checker exactly where
  you need it.
- **Import order:** stdlib → third-party → local, grouped and blank-line separated. Explicit
  imports over wildcards.

---

## Testing

Tests are pytest. The bar is the same everywhere.

- **AAA + FIRST.** Each test is Arrange / Act / Assert with one main thing under assertion. Tests
  are Fast, Independent, Repeatable, Self-validating, and Timely — no ordering dependencies, no
  shared mutable state, no network or wall-clock reliance.
- **Descriptive names.** `test_should_<behavior>_when_<condition>` — e.g.
  `test_should_reopen_finding_when_file_status_is_open`. The name states the behavior, so a failure
  reads like a spec.
- **Parametrize, don't copy-paste.** Near-identical tests that differ only in inputs/expected
  outputs collapse into one `@pytest.mark.parametrize`. Reserve separate test functions for
  genuinely different behaviors.
- **Mock behavior, build data.** This is the load-bearing testing rule:
  - **Build** DTOs, models, and value objects for real, or as small hand-written fakes. They carry
    data, not behavior — a real one is clearer and safer than a mock.
  - **Mock** only behavior-carrying collaborators — connections, HTTP clients, repositories,
    subprocess runners — and mock them with `spec=` so a renamed or removed method fails the test
    instead of silently passing.
  - **Never invent a type just so a test can mock it.** If the only reason an interface exists is
    the test, delete the interface and test the real thing.
  - **A boundary mocked in a unit test also needs an integration test** against the real
    dependency. A unit test proving you called the mock correctly proves nothing about the mock
    matching reality.
- **No logic in tests.** No `if`/`for`/`while`/`try` steering assertions inside a test. A test with
  branching is testing itself. Push variation into `parametrize` and keep the body straight-line.

---

## Forbidden-pattern audit (Python)

When an agent's workflow calls for a forbidden-pattern audit, run these against the **changed
`.py` files** and report **integer counts, not adjectives**. Empty findings are a claim made under
audit, not an exemption — report the number, not "all clean."

```bash
# Bare / swallowing except
grep -nE 'except\s*:' <changed .py files>            | wc -l   # bare except:
grep -nEA1 'except[^:]*:' <changed .py files> | grep -cE '^\s*pass\b'   # except ...: pass

# Re-raise that drops the cause (heuristic — inspect each `raise` inside an `except` block:
# a re-raise with no `from` is a finding)
grep -nE '(^|\s)raise\b' <changed .py files>

# print() used as logging (each hit is a finding unless it is deliberate CLI stdout)
grep -nE '\bprint\(' <changed .py files>             | wc -l

# Any escape hatch
grep -nE ':\s*Any\b|->\s*Any\b' <changed .py files>  | wc -l
```

Also review by eye (not greppable) and report a count for:

- **Non-PEP-257 docstring shape** — one-line docstrings whose closing `"""` is on its own line, a
  docstring on a leading-underscore method, "Returns…"-style non-imperative one-liners, or a
  public module/class/method with no docstring at all.

Report format:

```
## Forbidden-Pattern Audit (Python)
- bare `except:`: 0 occurrences
- `except ...: pass`: 0 occurrences
- re-raise missing `from`: 0 (or list file:line)
- `print(` as logging: 0 (or list file:line + justification)
- `: Any` / `-> Any`: 0 occurrences
- non-PEP-257 docstrings: 0 (or list file:line)
```

Any count above zero must be fixed before reporting, or carried with a per-occurrence
justification. "All clean" is not acceptable phrasing — numbers only.

---

## Framework-conditional guidance

Apply a block **only when the changed code uses that framework** (detected from its imports), never
because of which repo the file lives in. A file that uses none of these gets none of them.

**Modern type-hint syntax (Python 3.10+).** Use pipe syntax for unions and optionals —
`str | None`, `int | str` — over `Optional[...]` / `Union[...]`. This is triggered by the Python
version the code targets, so it is the default on current interpreters.

**Pydantic v2 (code imports `pydantic`).**
- Validate with `Model.model_validate(data)` — never construct a model by passing a raw dict to
  `Model(**data)` for external input.
- Configure with `model_config = ConfigDict(...)` (e.g. `extra="forbid"` for request models,
  `extra="ignore"` for responses, `populate_by_name=True`), not an inner `class Config`.
- Mutable defaults use `Field(default_factory=list)` / `Field(default_factory=dict)` — never
  `Field(default=[])`.
- Map camelCase↔snake_case with `AliasChoices` (or `Field(alias=...)`), so an upstream JSON key and
  the Python attribute can differ without a manual remap.

**HTTP-boundary tests (code makes outbound HTTP; tests use pytest).**
- Mock the HTTP layer with **respx**, matching on method + URL, and assert on the request that was
  made — do not mock your own client wrapper.
- For `async def` code and tests, use **pytest-asyncio** (`@pytest.mark.asyncio` or the configured
  asyncio mode); do not drive coroutines by hand.

**Structured logging (code imports `structlog`).**
- Get a module-level logger with `get_logger(...)`, one per module — not stdlib `logging`.
- Event names are `snake_case`: past tense for a completed event (`report_imported`), present tense
  for an in-progress one (`retrying_request`).
- **No f-strings in the event string.** Pass data as keyword args — `log.info("finding_reopened",
  finding_id=cuid, count=n)`, not `log.info(f"reopened {cuid}")` — so fields stay queryable.
- Never log secrets, tokens, passwords, or full request/response bodies.

**JSON (any repo doing JSON I/O).** Prefer **orjson** over stdlib `json` for
serialization/deserialization; parse with `orjson.loads(...)` before handing to
`model_validate(...)`.
