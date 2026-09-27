"""Command-line interface: pdf2md FILE_OR_DIR [...]"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .converter import convert


def _collect(inputs: list[str]) -> list[Path]:
    files: list[Path] = []
    for raw in inputs:
        p = Path(raw)
        if p.is_dir():
            files.extend(sorted(p.rglob("*.pdf")))
        elif p.is_file():
            files.append(p)
        else:
            print(f"warning: {raw} not found, skipping", file=sys.stderr)
    return files


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="pdf2md",
        description="Convert PDF files to Markdown.",
    )
    ap.add_argument("inputs", nargs="+", help="PDF files or folders (folders are searched recursively)")
    ap.add_argument("-o", "--output", help="Output file (single input) or folder (multiple inputs). "
                    "Defaults to writing NAME.md next to each PDF.")
    ap.add_argument("--stdout", action="store_true", help="Print Markdown to stdout instead of writing files")
    ap.add_argument("-p", "--pages", help="Pages to convert, 1-based, e.g. '1-3,7'")
    ap.add_argument("--images", choices=["none", "embed", "files"], default="none",
                    help="none: drop images (default); embed: base64 inline; files: save next to the .md")
    ap.add_argument("--ocr", choices=["auto", "always", "never"], default="auto",
                    help="auto: OCR pages without text, e.g. scans (default); always; never")
    ap.add_argument("--ocr-lang", default="eng", help="Tesseract language code(s), e.g. 'eng', 'deu', 'eng+fra'")
    ap.add_argument("--page-separators", action="store_true", help="Insert a marker between pages")
    args = ap.parse_args(argv)

    files = _collect(args.inputs)
    if not files:
        print("error: no PDF files found", file=sys.stderr)
        return 1

    out = Path(args.output) if args.output else None
    single_file_out = out is not None and len(files) == 1 and out.suffix.lower() == ".md"

    failures = 0
    for pdf in files:
        if single_file_out:
            target = out
        elif out is not None:
            target = out / (pdf.stem + ".md")
        else:
            target = pdf.with_suffix(".md")

        try:
            md = convert(
                pdf,
                pages=args.pages,
                images=args.images,
                image_dir=target.parent / f"{target.stem}_images",
                page_separators=args.page_separators,
                ocr=args.ocr,
                ocr_language=args.ocr_lang,
            )
        except Exception as e:  # keep going on batch runs
            failures += 1
            print(f"error: {pdf}: {e}", file=sys.stderr)
            continue

        if args.stdout:
            sys.stdout.write(md)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(md, encoding="utf-8")
            print(f"{pdf} -> {target}", file=sys.stderr)

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
