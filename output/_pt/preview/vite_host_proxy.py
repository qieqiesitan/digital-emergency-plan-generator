"""把 emergency-plan-frontend:5173 反代到本地端口，并把 Host 改成 localhost:5173
（绕过 Vite 的 host 校验 403）。仅用于本地截图，用完即停。"""
import sys
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

TARGET = "http://emergency-plan-frontend:5173"
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8099


class Proxy(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass

    def _proxy(self):
        body = None
        length = int(self.headers.get("Content-Length") or 0)
        if length:
            body = self.rfile.read(length)
        req = urllib.request.Request(TARGET + self.path, data=body, method=self.command)
        for k, v in self.headers.items():
            if k.lower() in ("host", "connection", "accept-encoding"):
                continue
            req.add_header(k, v)
        req.add_header("Host", "localhost:5173")
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                payload = resp.read()
                self.send_response(resp.status)
                for k, v in resp.headers.items():
                    if k.lower() in ("transfer-encoding", "connection", "content-encoding", "content-length"):
                        continue
                    self.send_header(k, v)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
        except urllib.error.HTTPError as e:
            payload = e.read()
            self.send_response(e.code)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        except Exception as e:  # noqa: BLE001
            msg = f"proxy error: {type(e).__name__}: {e}".encode()
            self.send_response(502)
            self.send_header("Content-Length", str(len(msg)))
            self.end_headers()
            self.wfile.write(msg)

    do_GET = do_POST = do_HEAD = do_PUT = do_DELETE = do_OPTIONS = _proxy


print(f"proxy on :{PORT} -> {TARGET}", flush=True)
ThreadingHTTPServer(("0.0.0.0", PORT), Proxy).serve_forever()
