"""Tiny web UI: pdf2md-web [--host HOST] [--port PORT]

Stdlib-only HTTP server. The browser POSTs the raw PDF bytes to /convert
(query params carry the options) and gets Markdown back.
"""

from __future__ import annotations

import argparse
import json
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from urllib.parse import parse_qs, urlparse

from .converter import convert

MAX_UPLOAD_MB = 100
INDEX_HTML = files("pdf2md").joinpath("static/index.html").read_bytes()


class Handler(BaseHTTPRequestHandler):
    server_version = "pdf2md"

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _error(self, status: int, msg: str) -> None:
        self._send(status, json.dumps({"error": msg}).encode(), "application/json")

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            self._send(200, INDEX_HTML, "text/html; charset=utf-8")
        elif path == "/health":
            self._send(200, b"ok", "text/plain")
        else:
            self._error(404, "Not found")

    def do_POST(self) -> None:
        url = urlparse(self.path)
        if url.path != "/convert":
            return self._error(404, "Not found")

        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return self._error(400, "Empty upload")
        if length > MAX_UPLOAD_MB * 1024 * 1024:
            return self._error(413, f"File exceeds {MAX_UPLOAD_MB} MB limit")

        data = self.rfile.read(length)
        if not data.startswith(b"%PDF"):
            return self._error(400, "That doesn't look like a PDF file")

        q = {k: v[0] for k, v in parse_qs(url.query).items()}
        images = q.get("images", "none")
        if images not in ("none", "embed"):  # "files" makes no sense over HTTP
            return self._error(400, "images must be 'none' or 'embed'")

        ocr = q.get("ocr", "auto")
        if ocr not in ("auto", "always", "never"):
            return self._error(400, "ocr must be 'auto', 'always' or 'never'")

        try:
            md = convert(
                data,
                pages=q.get("pages") or None,
                images=images,
                page_separators=q.get("separators") == "1",
                ocr=ocr,
            )
        except ValueError as e:
            return self._error(400, str(e))
        except Exception as e:
            return self._error(500, f"Conversion failed: {e}")

        self._send(200, md.encode("utf-8"), "text/markdown; charset=utf-8")

    def log_message(self, fmt: str, *args) -> None:
        print(f"[{self.log_date_time_string()}] {fmt % args}", flush=True)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="pdf2md-web", description="Run the PDF to Markdown web UI.")
    ap.add_argument("--host", default="127.0.0.1",
                    help="Use 0.0.0.0 to let others on your network use it (default: 127.0.0.1)")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-browser", action="store_true", help="Don't open a browser tab on start")
    args = ap.parse_args(argv)

    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    url = f"http://{'localhost' if args.host in ('127.0.0.1', '0.0.0.0') else args.host}:{args.port}"
    print(f"pdf2md web UI running at {url}  (Ctrl+C to stop)", flush=True)
    if not args.no_browser:
        webbrowser.open(url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
