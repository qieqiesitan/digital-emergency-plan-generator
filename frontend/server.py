import http.server
import urllib.request
import os
import json
import gzip
from io import BytesIO

BACKEND = os.environ.get("BACKEND_URL", "http://backend:8000")
PORT = int(os.environ.get("PORT", "8080"))
DIST_DIR = "/app/dist"

MIME_MAP = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css",
    ".js": "application/javascript",
    ".json": "application/json",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
    ".webmanifest": "application/manifest+json",
}

class ProxyHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIST_DIR, **kwargs)

    def do_GET(self):
        if self.path.startswith("/api/") or self.path.startswith("/uploads/"):
            self._proxy()
        else:
            self._serve_static()

    def do_POST(self):
        if self.path.startswith("/api/"):
            self._proxy()
        else:
            self.send_error(405)

    def do_PUT(self):
        if self.path.startswith("/api/"):
            self._proxy()
        else:
            self.send_error(405)

    def do_DELETE(self):
        if self.path.startswith("/api/"):
            self._proxy()
        else:
            self.send_error(405)

    def do_PATCH(self):
        if self.path.startswith("/api/"):
            self._proxy()
        else:
            self.send_error(405)

    def _proxy(self):
        target_url = f"{BACKEND}{self.path}"

        body = None
        content_len = int(self.headers.get("Content-Length", 0))
        if content_len > 0:
            body = self.rfile.read(content_len)

        req = urllib.request.Request(
            target_url,
            data=body,
            method=self.command,
        )

        skip_headers = {"host", "connection", "accept-encoding"}
        for key, val in self.headers.items():
            if key.lower() not in skip_headers:
                req.add_header(key, val)

        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                self.send_response(resp.status)
                # Forward response headers, preserving Transfer-Encoding for SSE
                for key, val in resp.headers.items():
                    key_lower = key.lower()
                    if key_lower in ("transfer-encoding",):
                        # Preserve chunked encoding for SSE streaming
                        self.send_header(key, val)
                    elif key_lower not in ("connection",):
                        self.send_header(key, val)
                self.end_headers()
                # Stream response body in chunks (critical for SSE)
                while True:
                    chunk = resp.read(8192)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    self.wfile.flush()
        except urllib.error.HTTPError as e:
            self.send_response(e.code)
            self.end_headers()
            self.wfile.write(e.read())
        except Exception as e:
            self.send_error(502, str(e))

    def _serve_static(self):
        path = self.path.split("?")[0]
        if path == "/":
            path = "/index.html"

        # SPA fallback for /m/ routes
        if path.startswith("/m/") or path.startswith("/m"):
            file_path = os.path.join(DIST_DIR, path.lstrip("/"))
            if not os.path.isfile(file_path) and not os.path.isdir(file_path):
                path = "/m.html"

        file_path = os.path.join(DIST_DIR, path.lstrip("/"))

        if os.path.isfile(file_path):
            ext = os.path.splitext(file_path)[1].lower()
            mime = MIME_MAP.get(ext, "application/octet-stream")

            with open(file_path, "rb") as f:
                content = f.read()

            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", len(content))
            if ext in (".html",):
                self.send_header("Cache-Control", "no-cache")
            else:
                self.send_header("Cache-Control", "public, max-age=31536000, immutable")
            self.end_headers()
            self.wfile.write(content)
        elif os.path.isdir(file_path):
            if os.path.isfile(os.path.join(file_path, "index.html")):
                self._serve_file(os.path.join(file_path, "index.html"))
            else:
                self._serve_file(os.path.join(DIST_DIR, "index.html"))
        else:
            # SPA fallback
            if path.startswith("/m"):
                self._serve_file(os.path.join(DIST_DIR, "m.html"))
            else:
                self._serve_file(os.path.join(DIST_DIR, "index.html"))

    def _serve_file(self, file_path):
        if os.path.isfile(file_path):
            ext = os.path.splitext(file_path)[1].lower()
            mime = MIME_MAP.get(ext, "application/octet-stream")
            with open(file_path, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", len(content))
            self.end_headers()
            self.wfile.write(content)


if __name__ == "__main__":
    server = http.server.HTTPServer(("0.0.0.0", PORT), ProxyHandler)
    print(f"Serving on port {PORT}, proxying API to {BACKEND}")
    server.serve_forever()
