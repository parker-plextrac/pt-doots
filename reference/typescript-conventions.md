# TypeScript conventions overlay

Loaded by pt-doots agents when implementing/reviewing TS code — the implementer and test-writer
read this when writing `.ts` / `.tsx`; the reviewers (code-reviewer, code-smells-reviewer,
test-reviewer, edge-case-qa) read it when the changed files are TypeScript. It is the **baseline**
conventions layer for the TypeScript/Node/React repos in this workspace (`product-core-backend`,
`product-core-frontend`) — see the precedence rule immediately below.

## Precedence — this is the baseline; the repo's committed standard wins

**This overlay is only a baseline snapshot of the TS repos' conventions.** When you work in a
specific repo, that repo's **own committed standard is authoritative and overrides this overlay for
that repo.**

- **Read the target repo's `CLAUDE.md` first** — the workspace-level `CLAUDE.md` *and* the repo-level
  one, plus any committed standards doc in the repo — and defer to it wherever it
  speaks. This overlay exists so the conventions are loaded even before you read, but the live repo
  doc wins whenever the two differ.
- **Do not go rogue.** Never impose this overlay's version of a rule over a repo's committed
  standard. If the repo says something different, the repo is right for that repo — follow it, and if
  the divergence looks like a real gap, flag it rather than silently overriding.
- The overlay fills the gaps the repo's own standard leaves; it never displaces it. Treat any
  drift between this file and a repo's committed `CLAUDE.md` as "the repo is newer" — check the repo.

---

## Type safety (product-core-backend)

**Absolute prohibitions.**

- **No `as any` — ever.** Use proper types, `unknown`, `Pick`, or narrowed interfaces instead.
- **No `as unknown as T`** — this is a last-resort escape hatch. Prefer narrowing the production type
  (e.g. `Pick<T, 'field'>`) so no cast is needed at all.
- When a function only uses a subset of a large type's fields, **narrow the parameter with
  `Pick<T, 'field1' | 'field2'>`** — makes the dependency explicit and avoids forced casts at call
  sites (especially in tests).

**Type-safety smells** (for the code-smells lens — each is a small type lie, flag new ones in new
code):

- **Index-signature escape hatch** — `[key: string]: unknown` or `[key: string]: any` on an
  interface/type used to bypass the type checker instead of properly typing the fields. If you know
  the shape, be explicit. An index signature says "I give up on typing this."
- **Type-assertion chains** — `as unknown as T`, or multiple `as` casts stacked to force a type.
  Usually means the source type is wrong or too broad.
- **Overly broad types** — `Record<string, any>`, `object`, or `unknown` where the actual shape is
  known. The code works but loses all type safety at that boundary.
- **`@ts-expect-error` / `@ts-ignore` proliferation** — new suppressions added in the PR. Each one is
  a small type lie. A few in legacy code is expected; new ones in new code are a smell.

---

## Forbidden-pattern audit (TypeScript)

When an agent's workflow calls for a forbidden-pattern audit (the implementer's Audit A), run these
against the **changed `.ts` files** and report **integer counts, not adjectives**. Empty findings are
a claim made under audit, not an exemption — report the number, not "all clean."

```bash
# Backend / TS prohibitions
grep -nE 'as any\b' <changed .ts files>           | wc -l
grep -nE 'as unknown as\b' <changed .ts files>    | wc -l
grep -nE 'as Buffer\b' <changed .ts files>        | wc -l

# Test hollowness heuristic — assertion counts in any new/modified test files
grep -cE 'expect\(|assert\.' <changed .test.ts files>

# External I/O without try/catch (heuristic — manual review)
grep -nE 'await .*\.(read|write|fetch|exec|query)' <changed files>
```

Report format:

```
## Forbidden-Pattern Audit
- `as any`: 0 occurrences
- `as unknown as`: 0 occurrences
- `as Buffer`: 0 occurrences
- Test assertion counts: foo.test.ts (4), bar.test.ts (7)
- Unwrapped external I/O calls: 0 (or list locations + justification)
```

- Any count above zero for a forbidden cast must be **fixed before reporting**, or carried with a
  per-occurrence inline justification. "All clean" is not acceptable phrasing — numbers only.
- **A test file with zero `expect(...)` / `assert.` calls is hollow.** Hollow tests are forbidden. If
  a test you created or touched has zero assertions, fix it or flag it.

---

## Backend layer rules (product-core-backend — TypeScript / Node.js)

**Routes** — gate access by **feature flag, license, and/or RBAC permission**. Access gating lives at
the route, not deeper.

**Zod validation** — use **`strictObject`** for all Zod object definitions in validation schemas
(not `z.object`). Validation lives at the route layer (`rest/validation.ts`).

**Controllers** — thin. **No RBAC checks, no business logic.** Only "join" data across domains for the
response.

**Domain `types.ts`** — define `FindManyFilter` composing the input filter with access control
(`tenantCuid`, `clientCuid`).

**Services** —
- First parameter is **`actor: Credentials`** (unless the method is `__UNSAFE`).
- Perform RBAC checks via **`RBACService`**.
- Standard method names: `getByCuid`, `findMany`, `create` / `createMany`, `deleteByCuid` /
  `deleteMany`, `updateByCuid` / `updateMany`.
- **`__UNSAFE` methods** skip access control — only for offline / no-actor-context cases. They must
  **not** be called from routes with an active user session.

**Repositories** —
- Import filter types from the domain's **`FindManyFilter`** (in `types.ts`), **not** directly from
  validation.
- Can inject repositories; **must NOT inject services.**
- For Kysely array queries, prefer **`= ANY`** over **`in`** (avoids PostgreSQL max-parameter-count
  issues).

**DI (tsyringe)** — in tests, register mock tokens in **`beforeEach` inside `describe` blocks**, NOT
in a top-level `before()` (top-level hooks do not run reliably in parallel mocha mode).

---

## Frontend (product-core-frontend — TypeScript / React)

**Component structure** — Atomic Design: components in `_Atoms/`, `_Molecules/`, `_Organisms/`.

**State** — React hooks (`useState`, `useEffect`); **avoid Redux**. Ensure paged response collections.

**API calls** — use the **`useRequest`** hook; no direct `fetch`/`axios`. **REST only — avoid
GraphQL.**

**Styling** — Styled Components with **BEM** naming; use **theme variables**, not hardcoded
colors/sizes; responsive via media queries.

**Types** — TypeScript strict mode; **Zod** for runtime validation; typed API requests/responses.

**Testability** — DOM elements must include an **`id` or `class`** so they can be targeted in tests.

**Accessibility** — WCAG 2.1; semantic HTML; ARIA attributes.

**Security** — XSS protection; HTML sanitization; **no `dangerouslySetInnerHTML` without
sanitization.**

---

## Test frameworks

### Backend — product-core-backend (Mocha + Chai + Moq.ts)

- **Framework:** Mocha test runner, Chai assertions (`expect`), Moq.ts for mocking.
- **File placement:** co-located with source, **`.test.ts`** suffix (`service.ts` → `service.test.ts`
  in the same directory).
- **Test suites:** unit tests in `apps/plextracapi/**` run under the **`core`** suite; unit tests in
  other `apps/` and `libs/` run under the **`apps`** suite.
- **What to test:**
  - **Service layer** — the primary target: business logic, RBAC checks, data transformations, error
    handling.
  - **Controller layer** — optional; only when there is joining logic worth testing.
  - **Repository layer** — lives in **`tests.postgres-repositories/`**, not co-located; tests filters,
    access control, and null/undefined/empty-array handling. Only when the task explicitly includes
    repository changes.
  - **API tests** — live in **`tests.api/`**; contract tests only. Don't write unless explicitly
    asked.
- **Key patterns:**
  - tsyringe DI: register mock tokens in **`beforeEach` inside `describe`**, NOT top-level `before()`.
  - Mock dependencies with Moq.ts: `new Mock<ServiceType>()` with `.setup()` and `.returns()`.
  - First parameter to service methods is `actor: Credentials` — mock it appropriately.
  - Service methods follow the naming convention (`getByCuid`, `findMany`, `create`, `deleteByCuid`,
    `updateByCuid`, …).
- **Parser tests (integration-worker):** use **`createMockStream`** from
  `apps/integration-worker/src/tests/mock-utils` instead of `Readable.from()` directly — this is the
  established pattern across all parser tests.
- **Run command:** `npx mocha --grep "test name pattern"` for targeted runs, or scope to a file.

### Frontend — product-core-frontend (Jest + React Testing Library)

- **Framework:** Jest test runner, React Testing Library (RTL) for component tests.
- **File placement:** co-located with components, **`.test.tsx`** suffix (`MyComponent.tsx` →
  `MyComponent.test.tsx`).
- **Coverage target:** 80% minimum (but do not accept hollow tests to hit it).
- **What to test:** component rendering (renders without crashing); user interactions (click, type,
  submit); conditional rendering (loading/error/empty states); hook behavior (`useEffect` side
  effects, `useState` transitions); API integration with the `useRequest` hook (mock the hook, verify
  calls).
- **Key patterns:**
  - `render()` from RTL for component mounting.
  - `screen.getByRole()`, `screen.getByText()`, `screen.getByTestId()` for queries — **prefer
    accessible queries** (`getByRole`, `getByText`) over `getByTestId`.
  - Use `userEvent` for interactions over `fireEvent`.
  - Use `waitFor()` for async assertions.
  - Mock API calls — don't make real HTTP requests.
  - DOM elements should have `id` or `class` for testability.
- **Run command:** `npx jest --testPathPattern="path/to/test"` for targeted runs.

### Moq.ts verify nuances (test-review lens)

- **`It.IsAny()` vs `It.Is<T>()`** — distinguish setup from verify. Moq.ts requires `It.IsAny()` on
  **setup** to satisfy the call; the strict matcher belongs in **`mock.verify(...)`** afterward. If
  the verify call uses `It.Is<T>(predicate)` to assert the actual arg shape, the setup's `It.IsAny()`
  is correct usage. Flag only when **both** setup AND verify use `It.IsAny()` on an arg that carries
  the test's behavior.
- **Tautological `not.be.undefined` guard** — sometimes an intentional clarity guard, because Moq.ts
  errors are confusing. The author is trading a useless assertion for a clearer failure message.
  Downgrade to `low` and frame as "remove for a tighter test, but understand why it's here" — don't
  flag at `high`.

### Framework misuse (test-review lens)

- **Top-level `before()` for DI** — tsyringe tokens registered in a top-level `before()` instead of
  `beforeEach` inside `describe` blocks. Causes flaky tests in parallel mocha mode.
- **`Readable.from()` in parser tests** — using `Readable.from()` directly instead of
  `createMockStream` from the shared mock-utils bypasses the established pattern.

### Existing test infrastructure to prefer (don't reinvent)

- **Backend:** `createMockStream` in `apps/integration-worker/src/tests/mock-utils`; shared mock
  patterns in neighboring test files.
- **Frontend:** shared render helpers, mock providers, and test utilities already in the repo.

---

## Import & module smells

- **Unnecessary re-export** — moving code to a new file but keeping `export { thing }` in the old
  location as a compat shim. Consumers should import from the new location directly. Look for
  `import { X } from './new-file'; export { X };` patterns.
- **Barrel-file bloat** — an `index.ts` that re-exports single items from many files, pulling
  everything into scope even when callers only need one export.
- **Import chain** — `A` imports from `B` which imports from `C`, when `A` could import from `C`
  directly. Each hop is a coupling point.

---

## Size & decomposition (TypeScript)

Some TS structures carry a soft size expectation; several are explicitly exempt. Apply these as the
size/decomposition calibration for TS files (do not assume a blanket cap):

- **Class size** — the ~200-line guideline applies to **services and domain classes**. **Route
  controllers can legitimately exceed 200 lines** (they have one method per route) — do not flag them
  for length. **Test fixtures** are also exempt.
- **Long method** — orchestration functions in route handlers and service entry points are
  legitimately procedural. If the method has clear top-level sections and they don't share state in
  confusing ways, it's a sequence, not a smell. Flag only when the method **mixes abstraction levels**
  (HTTP handling + business logic + DB calls in one body), not on raw length.
- **`Manager` / `Helper` / `Handler` / `Util` naming** — **not** a backend rule. The backend repo
  uses these names freely (`JobManager`, `RBACHandler`). (The prohibition on these names is a
  Python-services convention — it does not bind TypeScript files.)
- **Primitive obsession** — PlexTrac uses raw `string` for cuids, ids, and tenant identifiers
  throughout; that's the codebase's chosen primitive. Don't flag every `cuid: string` parameter as
  obsession — only flag when the primitive is genuinely ambiguous or used in math (e.g. a `string`
  that should be a typed currency value with cents handling).
- **Every exemption above covers CODE, never PROSE.** A controller that may exceed 200 lines, a
  procedural orchestration function, an exempt test fixture: none of that says anything about the
  comments inside them. Never read a size exemption across to comments or JSDoc. See *Comments &
  JSDoc* below.

---

## Comments & JSDoc (TypeScript)

- Comments explain the non-obvious **why**, not the **what**. If a comment restates the code, delete
  it; if the code needs a comment to be understood, prefer clearer code first.
- **Proportion: a comment must not outgrow the code it explains.** "It states a real why" is not a
  licence for any length; that test passes for an essay. A block comment longer than the code it
  sits on has to earn every line, and usually cannot. Keep the fact, cut the case for it.
- **Derivations, measurements, benchmarks, and rejected alternatives do not belong in source.** Keep
  the resulting number or decision plus one line of what it protects; the working belongs in the
  commit message, the PR, or the ticket.
- Don't state the same fact in both a JSDoc block and an adjacent inline comment. One keeps it.
- The bar for any individual line: **would omitting it let someone make a wrong change?** If not,
  it's commentary, not documentation.
- JSDoc belongs on exported/public surfaces and non-obvious logic, not on every function. An
  `@param` list that restates the signature adds maintenance and no information.

---

## PlexTrac backend edge cases (Node / Kysely / Redis / BullMQ / CK Editor)

Patterns specific to the PlexTrac TS backend that have historically caused issues. Check these when
the change touches the relevant system.

### Kysely / PostgreSQL

- **Empty array in `= ANY`** — `WHERE col = ANY($1)` with an empty array `[]` returns **zero rows,
  not all rows**. If the function should return all rows when no filter is provided, it must
  conditionally omit the `WHERE` clause instead of passing `[]`.
- **Parameter count limits** — `WHERE col IN (...)` with a very large array can hit PostgreSQL's max
  parameter count. Prefer `= ANY`, which passes a single array parameter.
- **Null in array filters** — `= ANY(ARRAY[null, 'a', 'b'])` will never match null rows. If nulls are
  valid, add a separate `OR col IS NULL` clause.

### Redis / ioredis

- **Key expiry during read** — a key can expire between checking its existence and reading its value.
- **Stream consumer group** — what happens if the consumer group does not exist yet?
- **Connection failures** — Redis operations should degrade gracefully. Check whether the function
  treats Redis as critical or as a cache that can be skipped.

### BullMQ

- **Job retries** — if a job fails and retries, is the handler **idempotent**? Will re-processing
  cause duplicate records, double-sends, or corrupted state?
- **Job stalling** — if a worker crashes mid-job, the job is retried. Does the handler handle partial
  completion from a previous attempt?
- **Concurrent workers** — if `concurrency > 1`, can two instances of the same job type conflict?

### CK Editor HTML

- **Malformed HTML** — CK Editor can produce unclosed tags, nested `<p><p>`, or empty elements. Does
  the parser handle these gracefully?
- **Script injection** — user-pasted content may include `<script>` tags or event-handler attributes.
- **Entity encoding** — `&amp;`, `&lt;`, `&gt;` may or may not be double-encoded depending on the
  source.

### Node file I/O (perf)

- Node file I/O has real performance characteristics: **streaming reads** (`createReadStream`, a
  streaming hash such as `getFileHash`) vs a **full-file `readFile`**. When only a prefix is needed
  (e.g. a bounded prefix-read for magic-byte detection), a bounded read avoids pulling multi-MB files
  into memory on every item — do not silently replace a chosen streaming/prefix path with a full-file
  read. (Origin: the IO-2204 plan-test-conflict; the perf choice was deliberate.)

---

## Verify-before-flag facts (PlexTrac TS backend)

Before promoting a finding, these PlexTrac/Node-specific facts often defuse a concern that looks real
in isolation:

- **Node is single-threaded for JS execution → no race without an `await`.** Two async ops on the
  same JS object can interleave only at `await` points. If a function reads-then-writes shared state
  with no `await` in the middle, there is no race in practice. Flag a race only when there is an
  actual `await` between the read and the write, OR the state lives in Redis/Postgres where multiple
  processes can write.
- **Zod validation lives at the route layer** (`rest/validation.ts`); service-layer functions trust
  their inputs. Before flagging "no validation on this service param," check whether the route's Zod
  schema already covers it. If it does, the service is correctly trusting validated input.
- **Feature flags are the gate.** PlexTrac's standard gating mechanism is feature flags
  (`launchDarkly.evaluate(...)` / `OVERRIDE_FLAG_NAME` env vars / `featureFlags.isEnabled(...)`). When
  a flag is referenced anywhere in the file, default to "this path is FF-gated" unless you can show
  otherwise. Do not flag a missing code-level integrationType / capability / Server-vs-Cloud check
  when an FF already gates the path.
- **BullMQ concurrency** — the job-idempotency / concurrent-worker race is only relevant if the
  queue's `concurrency > 1`. Default concurrency is 3, but many queues set it to 1. Check the queue
  config before flagging a job-handler race.
