---
name: publish-docs
description: >
  Publish a repo's markdown doc set to Confluence as a parent page with children.
  Converts markdown to storage format, keeps code-block languages, turns cross-doc
  links into real Confluence page links, and pre-flights before spending the
  single-use publish approval.
  Triggers: "publish these docs to confluence", "put the doc set on confluence",
  "/publish-docs".
argument-hint: "[repo-path]"
---

# Publish a doc set to Confluence

Turns a set of repo markdown files into a Confluence page tree: one parent page,
the rest nested under it. Use it for handoff documentation that has to live
somewhere non-engineers can read.

**Do not hand-roll the conversion.** Every step below has a failure mode that is
invisible until the page renders wrong, and one of them costs a publish approval
each time you get it wrong.

## Steps

### 1. Decide the tree

One parent, the rest as children. Confluence page titles must be **unique across
the whole space**, so prefix children with the subsystem name:

```
Export Service Architecture Overview        <- parent
  Export Service: Word Pipeline             <- children
  Export Service: PDF Pipeline
```

Leave out reference dumps and anything describing another team's code. Say what
you excluded when you show the user the plan.

### 2. Write the manifest

TSV, repo-relative path and page title. **First line is the parent.**

```
docs/export-service.md<TAB>Export Service Architecture Overview
.claude/docs/Word.md<TAB>Export Service: Word Pipeline
```

### 3. Build

```bash
python3 <plugin-dir>/scripts/build_confluence_pages.py \
  --manifest m.tsv --repo /path/to/repo --out ./build \
  --skip "NotPublished.md,AlsoNotPublished.md"
```

Writes per page: `<slug>.storage.xml` to publish, `<slug>.preview.md` to show the
user, and `plan.tsv`. It exits non-zero if any cross-doc link failed to resolve,
so a clean run means the links are real.

`--skip` lists docs that are NOT being published. Links to them are flattened to
plain text rather than left dangling.

### 4. Pre-flight, before asking for approval

The approval token is single-use. A validation error burns it and the user has to
approve again, so check everything first:

```bash
# title collision (a duplicate title is a 400)
atlassian.sh wiki GET "/rest/api/content/search?cql=space%3DIN%20and%20title%3D%22<TITLE>%22"

# what already lives under the parent
atlassian.sh wiki GET "/rest/api/content/<PARENT_ID>/child/page?limit=25"
```

Also scan the built markdown for anything that must not leave the company:
customer names, credentials, internal ticket keys, `notes/` paths.

### 5. Show the user the preview and get approval

Send `<slug>.preview.md`. Cross-doc links appear as `"Page Title" (linked page)`.
Wait for a real answer, then ask them to run:

```
! touch ~/.claude/.publish-approved
```

### 6. Publish, parent first

The parent must exist before the children, or their `ac:link` targets resolve to
nothing.

```bash
atlassian.sh confluence-create <SPACE> <PARENT_ID> "<Title>" build/<slug>.storage.xml
```

It prints the new page id and URL. Feed the parent's id in as `<PARENT_ID>` for
each child. To revise a published page, use `confluence-update <page_id> "<Title>"
<file>`, which bumps the version for you.

## What breaks, and why

Learned by getting each one wrong.

- **Never pass `-H "Content-Type: application/json"`.** The helper already sets
  it. A duplicate header is rejected by Tomcat with an HTML `400` before
  Confluence sees the body, and it consumes the approval token. Use the
  `confluence-create` / `confluence-update` subcommands rather than a raw `POST`
  and there is no header to duplicate.
- **The markdown converter drops fenced-code languages.** Confluence needs an
  explicit `<ac:parameter ac:name="language">`. The script re-injects them.
- **The converter reflows long lines.** Any placeholder you put in the markdown
  can be split across a newline, so recovery has to be DOTALL. This silently left
  every link unconverted until it was caught by inspecting the generated storage
  rather than trusting a count.
- **The converter HTML-escapes angle brackets unevenly**, turning `<<` into
  `&lt;<`. Placeholders must be letters only.
- **Mermaid does not render.** House convention is a code macro with
  `language=mermaid`, so it shows as a highlighted block. Match it; do not convert
  diagrams to ASCII.
- **Links to source files are dead on Confluence, by design.** Repo-root relative
  paths are what a reader looks up in the checkout. Do not rewrite them to URLs.

## Rules

- **Never publish without showing the exact content first.** The approval is per
  page unless the user says otherwise.
- **One approval covers one command.** A chained command clears the whole line
  once the token validates, so if you intend to publish several pages in one shot,
  say so plainly and let the user choose. Do not let them discover it after.
- Match the conventions of pages already in the space. Read a sibling page's
  storage format (`?expand=body.storage`) before inventing a layout.
