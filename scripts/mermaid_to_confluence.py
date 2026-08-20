#!/usr/bin/env python3
"""Turn mermaid code blocks on a Confluence page into rendered diagrams.

A fenced ```mermaid block published to Confluence shows up as a wall of source
text, because Confluence has no idea what mermaid is. The Mermaid Diagrams for
Confluence app (macro name `mermaid-cloud`) renders them, but it does not read
the diagram from the page body. It reads it from a plain-text ATTACHMENT on the
page, and the macro only holds a pointer:

    filename   name of the plain-text attachment holding the diagram   required
    revision   version number of that attachment, 1 for a new one      required
    toolbar    "bottom" or "none"                                      optional

Source: Stratus Add-ons, "Programmatically adding Mermaid diagrams".
https://stratus-addons.atlassian.net/wiki/spaces/MDFC/pages/2449440769/

So converting a page is three steps, which is what this script does:

    1. find every code block whose language is mermaid
    2. upload each one's source as a plain-text attachment
    3. replace the code block with a mermaid-cloud macro pointing at it

A PNG is NOT needed for the diagram to render. The app only uses a PNG when
somebody exports the whole page to PDF, and if one is wanted it must be attached
alongside as "<diagram name>.png".

Credentials come from ~/.jira-attlasian-cred (KEY=VALUE lines) or the
environment: ATLASSIAN_EMAIL, ATLASSIAN_SITE, ATLASSIAN_API_TOKEN.

Usage:
    mermaid_to_confluence.py <page-id> [--dry-run] [--toolbar none]
"""
import argparse
import html
import json
import os
import re
import subprocess
import sys
import tempfile

CRED_FILE = os.path.expanduser(os.environ.get("ATLASSIAN_CRED", "~/.jira-attlasian-cred"))


def credentials():
    vals = {}
    if os.path.exists(CRED_FILE):
        for line in open(CRED_FILE):
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.rstrip("\n").split("=", 1)
                vals[k.strip()] = v.strip()
    for k in ("ATLASSIAN_EMAIL", "ATLASSIAN_SITE", "ATLASSIAN_API_TOKEN"):
        vals[k] = os.environ.get(k) or vals.get(k, "")
        if not vals[k]:
            sys.exit(f"missing {k}: set it in {CRED_FILE} or the environment")
    return vals


def curl(cred, *args):
    base = f"https://{cred['ATLASSIAN_SITE']}/wiki"
    cmd = ["curl", "-sS", "-u", f"{cred['ATLASSIAN_EMAIL']}:{cred['ATLASSIAN_API_TOKEN']}"]
    cmd += [a.replace("{BASE}", base) for a in args]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"request failed: {r.stderr.strip()}")
    return r.stdout


def as_json(raw, what):
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        sys.exit(f"{what}: expected JSON, got:\n{raw[:400]}")


def get_page(cred, page_id):
    d = as_json(curl(cred, "{BASE}/rest/api/content/" + page_id
                     + "?expand=body.storage,version,space"), "get page")
    if "body" not in d:
        sys.exit(f"could not read page {page_id}: {d.get('message', d)}")
    return d


CODE_MACRO = re.compile(
    r'<ac:structured-macro[^>]*ac:name="code".*?</ac:structured-macro>', re.S)


def is_mermaid(block):
    return re.search(r'ac:name="language">\s*mermaid\s*<', block) is not None


def diagram_source(block):
    m = re.search(r"<!\[CDATA\[(.*?)\]\]>", block, re.S)
    return html.unescape(m.group(1)).strip() if m else ""


def nearest_heading(storage, pos, fallback):
    """Name the diagram after the section it sits in, so attachments are legible."""
    hits = re.findall(r"<h[1-6][^>]*>(.*?)</h[1-6]>", storage[:pos], re.S)
    if not hits:
        return fallback
    text = html.unescape(re.sub(r"<[^>]+>", "", hits[-1])).strip()
    # Attachment names travel through a URL; keep them boring.
    text = re.sub(r"[^A-Za-z0-9 _-]", "", text).strip()
    return text or fallback


def diagram_kind(src):
    """First real directive, skipping any %%{init: ...}%% theme block."""
    body = re.sub(r"%%\{.*?\}%%", "", src, flags=re.S).strip()
    return body.splitlines()[0].strip() if body else "?"


def macro(filename, toolbar):
    params = f'<ac:parameter ac:name="filename">{html.escape(filename)}</ac:parameter>'
    params += '<ac:parameter ac:name="revision">1</ac:parameter>'
    if toolbar:
        params += f'<ac:parameter ac:name="toolbar">{toolbar}</ac:parameter>'
    return (f'<ac:structured-macro ac:name="mermaid-cloud" ac:schema-version="1">'
            f'{params}</ac:structured-macro>')


def upload(cred, page_id, name, text):
    with tempfile.NamedTemporaryFile("w", suffix=".mmd", delete=False) as fh:
        fh.write(text)
        path = fh.name
    try:
        raw = curl(cred, "-X", "POST", "-H", "X-Atlassian-Token: nocheck",
                   "-F", f"file=@{path};filename={name};type=text/plain",
                   "-F", "minorEdit=true",
                   "{BASE}/rest/api/content/" + page_id + "/child/attachment")
    finally:
        os.unlink(path)
    d = as_json(raw, "upload attachment")
    r = (d.get("results") or [d])[0]
    if not r.get("id"):
        sys.exit(f"attachment upload failed: {d.get('message', d)}")
    return r


def put_page(cred, page, storage):
    payload = {
        "id": page["id"], "type": "page", "title": page["title"],
        "space": {"key": page["space"]["key"]},
        "version": {"number": page["version"]["number"] + 1,
                    "message": "Render mermaid diagrams via mermaid-cloud macro"},
        "body": {"storage": {"value": storage, "representation": "storage"}},
    }
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
        json.dump(payload, fh)
        path = fh.name
    try:
        raw = curl(cred, "-X", "PUT", "-H", "Content-Type: application/json",
                   "--data", f"@{path}", "{BASE}/rest/api/content/" + page["id"])
    finally:
        os.unlink(path)
    d = as_json(raw, "update page")
    if not d.get("id"):
        sys.exit(f"page update failed: {d.get('message', d)}")
    return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("page_id")
    ap.add_argument("--dry-run", action="store_true",
                    help="show what would change, touch nothing")
    ap.add_argument("--toolbar", choices=["bottom", "none"], default=None)
    args = ap.parse_args()

    cred = credentials()
    page = get_page(cred, args.page_id)
    storage = page["body"]["storage"]["value"]

    found = [(m.start(), m.group(0)) for m in CODE_MACRO.finditer(storage)
             if is_mermaid(m.group(0))]
    if not found:
        print(f"no mermaid code blocks on '{page['title']}', nothing to do")
        return

    print(f"page    : {page['title']}")
    print(f"version : {page['version']['number']}")
    print(f"diagrams: {len(found)}\n")

    replacements = []
    for i, (pos, block) in enumerate(found, 1):
        src = diagram_source(block)
        if not src:
            print(f"  {i}. EMPTY code block, skipping")
            continue
        name = nearest_heading(storage, pos, f"{page['title']} diagram {i}")
        print(f"  {i}. {name}")
        print(f"     {diagram_kind(src)}, {len(src)} chars")
        if not args.dry_run:
            att = upload(cred, args.page_id, name, src)
            print(f"     attached as version {att.get('version', {}).get('number', 1)}")
        replacements.append((block, macro(name, args.toolbar)))

    if args.dry_run:
        print("\ndry run, page not modified")
        return

    for old, new in replacements:
        storage = storage.replace(old, new, 1)
    d = put_page(cred, page, storage)
    print(f"\nupdated to version {d['version']['number']}")
    links = d.get("_links", {})
    print(f"URL: {links.get('base','')}{links.get('webui','')}")


if __name__ == "__main__":
    main()
