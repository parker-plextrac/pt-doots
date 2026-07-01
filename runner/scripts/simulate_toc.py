#!/usr/bin/env python3
"""
Two-pass WeasyPrint ToC simulation for pt-doots-harness --prove mode.

The harness's normal export flow runs through the BullMQ async worker in
product-core-backend.  For --prove mode we need to compare the FIX branch
(already verified via real export) against the MAIN branch.  The async worker
crashes (SIGSEGV) on main when the narrative contains anchored headings AND a
template that exposes level-2+ entries -- a separate bug from IO-2294.

This script bypasses the async worker entirely.  It reads the debug HTML that
was written by the fix-branch first-pass render, and re-runs inject_table_of_
contents using the currently checked-out version of product-services-export.

Switching between fix and main is done by the --prove orchestrator in proveMode.ts
via `git switch` before calling this script.  This script itself is branch-agnostic.

Usage:
  python simulate_toc.py \\
    --export-repo <path-to-product-services-export> \\
    --debug-html  <path-to-debug.html> \\
    --out-pdf     <output-pdf-path>

Exit codes:
  0  success
  1  error (printed to stderr)
"""
import argparse
import re
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--export-repo",
        required=True,
        help="Absolute path to the product-services-export checkout.",
    )
    parser.add_argument(
        "--debug-html",
        required=True,
        help="Path to the debug HTML written by the first-pass PDF render.",
    )
    parser.add_argument(
        "--out-pdf",
        required=True,
        help="Path where the simulated PDF will be written.",
    )
    args = parser.parse_args()

    export_repo = Path(args.export_repo).resolve()
    if not export_repo.is_dir():
        print(f"error: --export-repo does not exist: {export_repo}", file=sys.stderr)
        sys.exit(1)

    debug_html_path = Path(args.debug_html).resolve()
    if not debug_html_path.is_file():
        print(f"error: --debug-html not found: {debug_html_path}", file=sys.stderr)
        sys.exit(1)

    # Add the export repo to sys.path so we can import its modules.
    sys.path.insert(0, str(export_repo))

    try:
        from bs4 import BeautifulSoup  # type: ignore[import-untyped]
        from weasyprint import HTML  # type: ignore[import-untyped]
        from plextrac_exports.exporters.pdfs import PdfExporter  # type: ignore[import-untyped]
        from plextrac_exports.modules.table_of_contents import TableOfContentsBuilder  # type: ignore[import-untyped]
    except ImportError as exc:
        print(f"error: failed to import from {export_repo}: {exc}", file=sys.stderr)
        sys.exit(1)

    doc_html = debug_html_path.read_text(encoding="utf-8")

    # Extract the <style> block to use when rendering the standalone ToC page.
    soup = BeautifulSoup(doc_html, "html.parser")
    style_tag = soup.find("style")
    styles = re.sub(
        r"@page ?:first {",
        "@page :first {}\n#never {",
        str(style_tag) if style_tag else "",
    )

    # First WeasyPrint pass: build the bookmark tree.
    first_doc = HTML(string=doc_html).render()

    # Build the slug→level map from the actual heading tags in the HTML.
    # On the fix branch PdfExporter has _build_heading_level_map; on main it
    # does NOT exist (the method was added by the IO-2294 fix commit).
    # We detect its presence at runtime so this script works on both branches.
    build_level_map = getattr(PdfExporter, "_build_heading_level_map", None)
    level_map = build_level_map(doc_html) if callable(build_level_map) else None

    builder = TableOfContentsBuilder()
    tree = first_doc.make_bookmark_tree()

    # generate_outline_str gained a level_map keyword argument in the fix commit.
    # On main that parameter does not exist at all; detect it so we can call the
    # function correctly on both branches without breaking either.
    import inspect
    _gen_params = inspect.signature(builder.generate_outline_str).parameters
    _lm_kwargs: dict = {"level_map": level_map} if "level_map" in _gen_params else {}

    # Preliminary ToC render to count ToC pages.
    toc_prelim = builder.generate_outline_str(tree, 0, False, **_lm_kwargs)
    toc_prelim_doc = HTML(string=f"{styles}{toc_prelim}").render()

    # Final ToC with correct page-number offsets.
    toc_final = builder.generate_outline_str(
        tree, 0, False, len(toc_prelim_doc.pages), **_lm_kwargs
    )

    # Inject ToC at the top of the document body.
    html_with_toc = doc_html.replace("<body>", f"<body>{toc_final}", 1)

    final_doc = HTML(string=html_with_toc).render()
    out_path = Path(args.out_pdf).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    final_doc.write_pdf(str(out_path), presentational_hints=True)
    print(f"saved: {out_path}")


if __name__ == "__main__":
    main()
