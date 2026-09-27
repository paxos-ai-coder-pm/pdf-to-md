"""Core PDF -> Markdown conversion, shared by the CLI and the web server."""

from __future__ import annotations

import os
from concurrent.futures import ProcessPoolExecutor
from concurrent.futures.process import BrokenProcessPool
from pathlib import Path

import pymupdf

from .ocr import needs_ocr, replace_with_ocr, tessdata_dir

# Below this many pages, process start-up costs more than parallelism saves.
PARALLEL_MIN_PAGES = 8
MAX_WORKERS = 8


def parse_pages(spec: str | None, page_count: int) -> list[int] | None:
    """Turn a 1-based spec like "1-3,7" into a sorted list of 0-based page indexes."""
    if not spec:
        return None
    pages: set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start_s, end_s = part.split("-", 1)
            start = int(start_s) if start_s else 1
            end = int(end_s) if end_s else page_count
        else:
            start = end = int(part)
        if start < 1 or end > page_count or start > end:
            raise ValueError(f"Page range '{part}' is outside 1-{page_count}")
        pages.update(range(start - 1, end))
    return sorted(pages)


def _open(source: bytes | str) -> pymupdf.Document:
    if isinstance(source, bytes):
        return pymupdf.open(stream=source, filetype="pdf")
    return pymupdf.open(source)


def _init_worker() -> None:
    """Pin each worker's ONNX layout model to one thread.

    onnxruntime defaults to one thread per core; with several workers that
    oversubscribes the CPU and made conversion ~4x slower in benchmarks.
    """
    try:
        import onnxruntime as ort
    except ImportError:
        return
    original_init = ort.InferenceSession.__init__

    def init(self, path_or_bytes, sess_options=None, *args, **kwargs):
        sess_options = sess_options or ort.SessionOptions()
        sess_options.intra_op_num_threads = 1
        original_init(self, path_or_bytes, sess_options, *args, **kwargs)

    ort.InferenceSession.__init__ = init


def _convert_chunk(job: tuple) -> str:
    """Convert one contiguous run of pages. Runs in a worker process for big PDFs."""
    # Imported here, not at module level: importing it loads the ONNX layout
    # model, which must happen after _init_worker has capped its threads.
    import pymupdf4llm

    source, pages, ocr_pages, ocr_language, tessdata, md_kwargs = job
    doc = _open(source)
    try:
        if ocr_pages:
            replace_with_ocr(doc, ocr_pages, ocr_language, tessdata)
        return pymupdf4llm.to_markdown(doc, pages=pages, **md_kwargs)
    finally:
        doc.close()


def convert(
    source: str | Path | bytes,
    *,
    pages: str | None = None,
    images: str = "none",
    image_dir: str | Path | None = None,
    page_separators: bool = False,
    ocr: str = "auto",
    ocr_language: str = "eng",
    workers: int | None = None,
) -> str:
    """Convert a PDF (path or raw bytes) to Markdown.

    images:  "none" drops images, "embed" inlines them as base64 data URIs,
             "files" writes them to image_dir and links to them.
    ocr:     "auto" OCRs only pages with no extractable text, "always" OCRs every
             selected page, "never" disables OCR.
    workers: processes to use for large PDFs (default: half the CPUs, max 8).
    """
    if not isinstance(source, bytes):
        source = str(source)
    filename = "document.pdf" if isinstance(source, bytes) else Path(source).name

    doc = _open(source)
    try:
        if doc.needs_pass:
            raise ValueError("PDF is password-protected")
        page_list = parse_pages(pages, doc.page_count)
        selected = page_list if page_list is not None else list(range(doc.page_count))
        if ocr == "always":
            to_ocr = set(selected)
        elif ocr == "auto":
            to_ocr = {n for n in selected if needs_ocr(doc[n])}
        elif ocr == "never":
            to_ocr = set()
        else:
            raise ValueError(f"Unknown ocr mode: {ocr!r}")
    finally:
        doc.close()

    md_kwargs: dict = {"page_separators": page_separators, "filename": filename}
    if images == "embed":
        md_kwargs["embed_images"] = True
    elif images == "files":
        if image_dir is None:
            raise ValueError("image_dir is required when images='files'")
        Path(image_dir).mkdir(parents=True, exist_ok=True)
        md_kwargs["write_images"] = True
        md_kwargs["image_path"] = str(image_dir)
    elif images != "none":
        raise ValueError(f"Unknown images mode: {images!r}")

    tessdata = tessdata_dir(ocr_language) if to_ocr else ""

    # Split into contiguous chunks so the joined output stays in page order.
    if workers is None:
        workers = min(MAX_WORKERS, max(1, (os.cpu_count() or 2) // 2))
    if len(selected) < PARALLEL_MIN_PAGES:
        workers = 1
    size = -(-len(selected) // workers)
    chunks = [selected[i:i + size] for i in range(0, len(selected), size)]
    jobs = [(source, c, sorted(to_ocr.intersection(c)), ocr_language, tessdata, md_kwargs) for c in chunks]

    parts = None
    if len(jobs) > 1:
        try:
            with ProcessPoolExecutor(len(jobs), initializer=_init_worker) as pool:
                parts = list(pool.map(_convert_chunk, jobs))
        except BrokenProcessPool:
            # On Windows this happens when the caller's script has no
            # `if __name__ == "__main__":` guard. Fall back to one process.
            parts = None
    if parts is None:
        parts = [_convert_chunk((source, selected, sorted(to_ocr), ocr_language, tessdata, md_kwargs))]

    md = "".join(parts)
    if not md.strip():
        raise ValueError("No text found in this PDF"
                         + (" (OCR is off)" if ocr == "never" else " (even after OCR)"))
    return md
