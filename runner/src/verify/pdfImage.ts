// Best-effort visual proof: render the first page of the exported PDF to PNG
// using poppler's pdftoppm CLI. Returns null (never throws) if poppler is absent
// or the render fails for any reason. The structured gate (debugHtmlParser +
// verifyToc) is the authoritative verdict; this is supplementary evidence only.
import { execFileSync } from "node:child_process";
import { basename, extname, join } from "node:path";

// Returns the PNG path on success, or null if poppler is absent or rendering fails.
export function renderTocPng(pdfPath: string, outDir: string): string | null {
  try {
    const stem = basename(pdfPath, extname(pdfPath));
    const outBase = join(outDir, stem);
    // pdftoppm flags:
    //   -r 150        render at 150 DPI (legible, not huge)
    //   -l 1          stop after page 1
    //   -singlefile   no per-page numeric suffix in output filename
    //   -png          PNG output
    execFileSync("pdftoppm", ["-r", "150", "-l", "1", "-singlefile", "-png", pdfPath, outBase]);
    return `${outBase}.png`;
  } catch {
    // Poppler absent (ENOENT), or render error — treat as non-fatal
    return null;
  }
}
