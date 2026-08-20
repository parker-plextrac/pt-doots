#!/usr/bin/env python3
"""Convert a set of repo markdown docs into Confluence storage-format pages.

Reads a manifest, writes one .storage.xml per page plus a plan.tsv for the
publish step. Handles the parts of the conversion that are easy to get wrong:

  * The markdown converter drops fenced-code languages. Confluence needs an
    explicit <ac:parameter ac:name="language">, so languages are re-injected by
    pairing opening fences with code macros in document order.
  * The converter reflows long lines, so a placeholder can be split across a
    newline. Marker recovery is DOTALL and normalises whitespace.
  * The converter HTML-escapes angle brackets unevenly ("<<" becomes "&lt;<"),
    so the placeholder alphabet is letters only.
  * Links between docs become real Confluence page links, matched on page title.
  * Links to source files become repo-root relative text. They are dead links on
    Confluence by design; they are paths a reader looks up in the repo.

Usage:
    build_confluence_pages.py --manifest m.tsv --repo /path/to/repo --out ./build

Manifest is TSV, one page per line, FIRST LINE IS THE PARENT:
    <repo-relative markdown path>\t<Confluence page title>
"""
import argparse
import os
import re
import subprocess
import sys

# Only ever invoked with `md-to-storage`, which is a read. Publishing is done by
# an explicit command in the transcript so the approval guard can see it.
HELPER = os.path.expanduser("~/.claude/scripts/atlassian.sh")

# Letters only. Anything with punctuation gets mangled or escaped by the converter.
MARK = ("CFLINKAAA", "CFLINKBBB", "CFLINKCCC")


def read_manifest(path):
    rows = []
    for line in open(path):
        line = line.rstrip("\n")
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        src, title = line.split("\t", 1)
        rows.append((src.strip(), title.strip()))
    if not rows:
        sys.exit("manifest is empty")
    return rows


def rewrite_links(md, doc2title, skip):
    """Cross-doc links become markers; source-file links become repo-root paths."""
    def link(m):
        text, target = m.group(1), m.group(2)
        base = os.path.basename(target)
        if base in doc2title:
            a, b, c = MARK
            return f"{a}{doc2title[base]}{b}{doc2title[base]}{c}"
        if base in skip:
            return text          # page not published; keep the words, drop the link
        return m.group(0)
    md = re.sub(r"\[([^\]]+)\]\(([^)]+\.md)\)", link, md)
    # ../thing and ../../thing -> thing
    md = re.sub(r"\]\((?:\.\./)+([^)]*)\)", r"](\1)", md)
    return md


def md_to_storage(md_path):
    r = subprocess.run([HELPER, "md-to-storage", md_path],
                       capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"markdown conversion failed for {md_path}:\n{r.stderr}")
    return r.stdout


def inject_languages(md, storage):
    """Re-attach fenced-code languages, which the converter drops."""
    langs, inside = [], False
    for line in md.split("\n"):
        if line.startswith("```"):
            if not inside:
                langs.append(line.strip()[3:].strip() or None)
            inside = not inside
    macros = list(re.finditer(r'<ac:structured-macro[^>]*ac:name="code"[^>]*>', storage))
    if len(macros) != len(langs):
        print(f"    warn: {len(macros)} code macros vs {len(langs)} fences, "
              "leaving languages unset", file=sys.stderr)
        return storage
    out, last = [], 0
    for m, lang in zip(macros, langs):
        out.append(storage[last:m.end()])
        if lang:
            out.append(f'<ac:parameter ac:name="language">{lang}</ac:parameter>')
        last = m.end()
    out.append(storage[last:])
    return "".join(out)


def resolve_page_links(storage):
    a, b, c = MARK
    pattern = re.escape(a) + r"(.+?)" + re.escape(b) + r"(.+?)" + re.escape(c)

    def sub(m):
        title = " ".join(m.group(1).split())
        text = " ".join(m.group(2).split())
        return ('<ac:link><ri:page ri:content-title="%s" />'
                '<ac:plain-text-link-body><![CDATA[%s]]></ac:plain-text-link-body>'
                '</ac:link>' % (title, text))
    return re.sub(pattern, sub, storage, flags=re.S)


def slug(title):
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--repo", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--skip", default="",
                    help="comma-separated markdown filenames that are NOT published; "
                         "links to them are flattened to plain text")
    args = ap.parse_args()

    rows = read_manifest(args.manifest)
    doc2title = {os.path.basename(src): title for src, title in rows}
    skip = {s.strip() for s in args.skip.split(",") if s.strip()}
    os.makedirs(args.out, exist_ok=True)

    plan, failures = [], 0
    for i, (src, title) in enumerate(rows):
        full = os.path.join(args.repo, src)
        if not os.path.exists(full):
            sys.exit(f"missing source doc: {full}")
        md = rewrite_links(open(full).read(), doc2title, skip)

        s = slug(title)
        tmp = os.path.join(args.out, f"{s}.rewritten.md")
        open(tmp, "w").write(md)

        storage = resolve_page_links(inject_languages(md, md_to_storage(tmp)))

        leftover = storage.count(MARK[0])
        if leftover:
            print(f"    ERROR: {leftover} unresolved page links in {title}", file=sys.stderr)
            failures += 1

        open(os.path.join(args.out, f"{s}.storage.xml"), "w").write(storage)

        # Preview: what a human reads to approve the page, markers rendered as text.
        preview = re.sub(re.escape(MARK[0]) + r"(.+?)" + re.escape(MARK[1]) + r"(.+?)"
                         + re.escape(MARK[2]),
                         lambda m: '"' + " ".join(m.group(2).split()) + '" (linked page)',
                         md, flags=re.S)
        open(os.path.join(args.out, f"{s}.preview.md"), "w").write(preview)

        role = "parent" if i == 0 else "child"
        plan.append(f"{i:02d}\t{role}\t{s}\t{title}")
        print(f"  {role:6} {len(storage):>7}b  {title}")

    open(os.path.join(args.out, "plan.tsv"), "w").write("\n".join(plan) + "\n")
    if failures:
        sys.exit(f"{failures} page(s) have unresolved links; not safe to publish")
    print(f"\nwrote {len(rows)} pages to {args.out}")


if __name__ == "__main__":
    main()
