# pdf2md: PDF → Markdown converter

Convert PDFs to clean Markdown, including headings, bold and italic text, lists, tables, and optionally images.
It has two front ends:

- **Web UI**: drag and drop PDFs, preview, copy, and download `.md` files
- **CLI**: convert single files, several files, or whole folders

Conversion runs entirely on your machine (it uses [PyMuPDF4LLM](https://github.com/pymupdf/pymupdf4llm)). No files go to any cloud service.

## Install

Requires Python 3.10+.

```bash
pip install .            # from this folder
# or, to share: pip install git+https://github.com/paxos-ai-coder-pm/pdf-to-md
```

## Web UI

```bash
python -m pdf2md.server  # opens http://localhost:8765  (or: pdf2md-web)
```

> If `pdf2md` / `pdf2md-web` say "not recognized", pip put them in a folder that isn't on your PATH.
> The `python -m ...` forms always work.

Or double-click `run-web.bat` (Windows) / run `./run-web.sh` (macOS/Linux). They install on first run.

Options for the web UI: `--port 9000`, `--no-browser`, `--host 0.0.0.0` (lets others on your Wi-Fi/LAN use it via `http://<your-ip>:8765`).

## CLI

```bash
python -m pdf2md report.pdf                       # writes report.md next to it
python -m pdf2md report.pdf -o notes.md           # choose output file
python -m pdf2md a.pdf b.pdf -o out/              # several files into a folder
python -m pdf2md ./papers/                        # every PDF in a folder (recursive)
python -m pdf2md report.pdf --pages 1-3,7         # selected pages (1-based)
python -m pdf2md report.pdf --images files        # save images to report_images/ and link them
python -m pdf2md report.pdf --images embed        # inline images as base64
python -m pdf2md report.pdf --stdout | less       # print instead of writing
```

Python API:

```python
from pdf2md import convert
md = convert("report.pdf", pages="1-5")
```

## Sharing it with others

| Option | Good for |
|---|---|
| Send the folder / push to GitHub, and they run `pip install .` | Technical users |
| `pdf2md-web --host 0.0.0.0` on your machine | Teammates on the same network |
| Docker (below) on any server or VM | A hosted internal tool |
| Deploy the Docker image to Render, Fly.io, Railway, or Hugging Face Spaces (Docker SDK, port 8765) | A public URL |

```bash
docker build -t pdf2md .
docker run -p 8765:8765 pdf2md
```

The server caps uploads at 100 MB. It has **no authentication**, so put it behind a login or VPN before you expose it publicly.

## Scanned and image-only PDFs (OCR)

Pages with no extractable text get OCR'd automatically (`--ocr auto`, the default). This covers scans and "Microsoft Print to PDF" files, which draw every letter as a shape.
It uses the Tesseract engine built into PyMuPDF, so there is nothing extra to install. The English model (about 4 MB) downloads once to `~/.pdf2md/tessdata` on first use.

- `--ocr always` OCRs every page; `--ocr never` turns it off.
- `--ocr-lang deu` or `--ocr-lang eng+fra` selects other languages (each model downloads on first use).
- Speed: a 300-page scanned book takes about 2–3 minutes on an 8+ core machine. Large PDFs are split across CPU cores automatically.

## Limitations

- **Decorative drop caps** (a large first letter of a chapter) can garble the first line or two of that paragraph in OCR output.
- **Tables** are detected most reliably when they have ruled lines. Borderless tables may come out as plain text.
- **Password-protected** PDFs are rejected.

## License

PyMuPDF is AGPL-3.0, so this tool is also AGPL-3.0. That is fine for personal and internal use and for open-source sharing. If you offer it as a network service, you must make the source available to its users. Closed-source commercial use needs an Artifex commercial license.
