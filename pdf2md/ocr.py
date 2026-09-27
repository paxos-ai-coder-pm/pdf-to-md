"""OCR for pages that have no extractable text (scans, or "Print to PDF" files
where every glyph was drawn as vector outlines).

Uses the Tesseract engine built into PyMuPDF, so only the language model file is
needed. It is downloaded on first use to ~/.pdf2md/tessdata (or $PDF2MD_TESSDATA).
"""

from __future__ import annotations

import os
import sys
import urllib.request
from pathlib import Path

import pymupdf

MODEL_URL = "https://github.com/tesseract-ocr/tessdata_fast/raw/main/{lang}.traineddata"
OCR_DPI = 300


def tessdata_dir(language: str = "eng") -> str:
    folder = Path(os.environ.get("PDF2MD_TESSDATA") or Path.home() / ".pdf2md" / "tessdata")
    for lang in language.split("+"):
        model = folder / f"{lang}.traineddata"
        if model.exists():
            continue
        folder.mkdir(parents=True, exist_ok=True)
        print(f"Downloading OCR model '{lang}' (one-time)...", file=sys.stderr, flush=True)
        tmp = model.with_suffix(".part")
        urllib.request.urlretrieve(MODEL_URL.format(lang=lang), tmp)
        tmp.replace(model)
    return str(folder)


def needs_ocr(page: pymupdf.Page) -> bool:
    return not page.get_text().strip()


def replace_with_ocr(doc: pymupdf.Document, page_nos: list[int], language: str, tessdata: str) -> None:
    """Swap each listed page in place for one holding only its OCR'd text.

    The page image is removed after OCR: otherwise pymupdf4llm's layout step
    sees a full-page image and runs its own (slower, worse) OCR on it again.
    """
    for n in page_nos:
        ocr_pdf = doc[n].get_pixmap(dpi=OCR_DPI).pdfocr_tobytes(language=language, tessdata=tessdata)
        ocr_doc = pymupdf.open("pdf", ocr_pdf)
        page = ocr_doc[0]
        page.add_redact_annot(page.rect)
        page.apply_redactions(
            images=pymupdf.PDF_REDACT_IMAGE_REMOVE,
            graphics=pymupdf.PDF_REDACT_LINE_ART_NONE,
            text=pymupdf.PDF_REDACT_TEXT_NONE,
        )
        doc.delete_page(n)
        doc.insert_pdf(ocr_doc, start_at=n)

