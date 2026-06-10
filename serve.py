#!/usr/bin/env python3
"""
ARTIS prototype server — serves the web app AND accepts blueprint uploads.

Run:
    python serve.py            # serves on http://localhost:8800
    python serve.py 9000       # custom port

GET  /                       -> the app (prototype/index.html)
GET  /<file>                 -> static files from prototype/
POST /api/upload-blueprint   -> saves an uploaded .md blueprint into the
                                pipeline's intake folder; it is processed on the
                                next orchestration run and the client then appears
                                in the app alongside Doniphan Moore.

Body of the POST is the raw Markdown text; the original filename is passed in the
`X-Filename` header.
"""

import sys
import os
import re
import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
PROTOTYPE_DIR = os.path.join(HERE, "prototype")

# Where uploaded blueprints land — the pipeline's intake folder.
INTAKE_DIR = r"C:\Users\jenna\Downloads\ArtisContentResearchProject\Interior Professional Trends\Client Blueprints"


def safe_name(name):
    """Reduce an uploaded filename to a safe basename ending in .md."""
    base = os.path.basename((name or "").replace("\\", "/"))
    base = re.sub(r"[^A-Za-z0-9._-]", "_", base).strip("._") or "client-blueprint"
    if not base.lower().endswith((".md", ".markdown", ".txt")):
        base += ".md"
    if base.lower().endswith(".markdown"):
        base = base[: -len(".markdown")] + ".md"
    if base.lower().endswith(".txt"):
        base = base[: -len(".txt")] + ".md"
    return base


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=PROTOTYPE_DIR, **kwargs)

    def _json(self, code, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path.rstrip("/") != "/api/upload-blueprint":
            self._json(404, {"ok": False, "error": "unknown endpoint"})
            return
        need = os.environ.get("UPLOAD_TOKEN")
        if need and self.headers.get("X-Upload-Token") != need:
            self._json(401, {"ok": False, "error": "unauthorized"})
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            if length <= 0:
                self._json(400, {"ok": False, "error": "empty upload"})
                return
            raw = self.rfile.read(length)
            text = raw.decode("utf-8", errors="replace")
            fname = safe_name(self.headers.get("X-Filename", "client-blueprint.md"))

            os.makedirs(INTAKE_DIR, exist_ok=True)
            dest = os.path.join(INTAKE_DIR, fname)
            with open(dest, "w", encoding="utf-8") as f:
                f.write(text)

            print(f"[upload] saved blueprint -> {dest} ({len(text)} chars)")
            self._json(200, {"ok": True, "filename": fname})
        except Exception as e:
            self._json(500, {"ok": False, "error": str(e)})

    def end_headers(self):
        # No caching, so a rebuilt data.js is always picked up on refresh.
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, fmt, *args):
        sys.stderr.write("  " + (fmt % args) + "\n")


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8800
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"ARTIS app  ->  http://localhost:{port}/")
    print(f"Serving     {PROTOTYPE_DIR}")
    print(f"Uploads to  {INTAKE_DIR}")
    print("Ctrl+C to stop.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped.")


if __name__ == "__main__":
    main()
