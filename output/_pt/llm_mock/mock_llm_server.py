"""Mock LLM 供应商：按请求体里的 model 字段模拟各种供应商侧故障。

用途：验证本系统对「限流 / 5xx / 超时 / 流式中断」的处理（零真实额度消耗）。
行为由 model 名决定：
    mock-ok            正常非流式响应
    mock-ok-once-429   第一次 429，之后正常（验证退避重试真的能救回来）
    mock-429           永远 429
    mock-500           永远 500
    mock-hang          挂起 600s（验证超时映射）
    mock-slow-nonstream 非流式但先睡 6s（模拟长推理，并发压测用）
    mock-json          非流式，返回一个"什么字段都有、但都是空数组"的 JSON（AI 端点冒烟用）
    mock-truncate      流式：发 3 个分片后断开且不发 [DONE]
    mock-slow-stream   流式：每片间隔 2s，共 5 片（并发压测用）
所有请求都会写一行到 --log 指定的 jsonl（含时间戳、model、stream）。
"""
import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

LOG_PATH = sys.argv[2] if len(sys.argv) > 2 else "/tmp/mock_llm.jsonl"
_lock = threading.Lock()
_counters: dict[str, int] = {}


def log(entry: dict) -> None:
    with _lock, open(LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):  # 静音
        pass

    def do_GET(self):  # noqa: N802
        """控制端点：/__reset 清空计数与日志（让"只失败一次"可重复验证）。"""
        if self.path.rstrip("/").endswith("/__reset"):
            with _lock:
                _counters.clear()
                open(LOG_PATH, "w", encoding="utf-8").close()
            self._json(200, {"ok": True})
            return
        self._json(404, {"error": {"message": "unknown path"}})

    def _json(self, code: int, payload: dict) -> None:
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw or b"{}")
        except Exception:  # noqa: BLE001
            payload = {}
        model = str(payload.get("model") or "")
        stream = bool(payload.get("stream"))
        log({"ts": time.time(), "model": model, "stream": stream, "path": self.path})

        if not self.path.rstrip("/").endswith("/chat/completions"):
            self._json(404, {"error": {"message": "unknown path"}})
            return

        if model == "mock-429":
            self._json(429, {"error": {"message": "rate limit exceeded", "type": "rate_limit_error"}})
            return
        if model == "mock-500":
            self._json(500, {"error": {"message": "internal server error"}})
            return
        if model == "mock-hang":
            time.sleep(600)
            self._json(200, {})
            return
        if model == "mock-slow-nonstream":
            time.sleep(6)
            self._json(200, {
                "id": "mock-slow",
                "object": "chat.completion",
                "model": model,
                "choices": [{"index": 0, "message": {"role": "assistant", "content": "SLOW_OK"},
                             "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 5, "completion_tokens": 2, "total_tokens": 7},
            })
            return
        if model == "mock-json":
            generic = {
                "questions": [],
                "items": [],
                "objects": [],
                "events": [],
                "measures": [],
                "nearby_units": [],
                "sensitive_targets": [],
                "zones": [],
                "nodes": [],
                "levels": [],
                "traffic_info": "",
                "description": "",
                "summary": "",
            }
            self._json(200, {
                "id": "mock-json",
                "object": "chat.completion",
                "model": model,
                "choices": [{"index": 0, "message": {"role": "assistant",
                                                     "content": json.dumps(generic, ensure_ascii=False)},
                             "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 5, "completion_tokens": 5, "total_tokens": 10},
            })
            return
        if model == "mock-ok-once-429":
            with _lock:
                seen = _counters.get(model, 0)
                _counters[model] = seen + 1
            if seen == 0:
                self._json(429, {"error": {"message": "rate limit exceeded"}})
                return

        def stream_chunks(count: int, delay: float, finish: bool) -> None:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            try:
                for i in range(count):
                    data = {"choices": [{"delta": {"content": f"分片{i}"}, "index": 0}]}
                    self.wfile.write(f"data: {json.dumps(data, ensure_ascii=False)}\n\n".encode())
                    self.wfile.flush()
                    if delay:
                        time.sleep(delay)
                if finish:
                    self.wfile.write(b"data: [DONE]\n\n")
                    self.wfile.flush()
            except Exception:  # noqa: BLE001
                pass
            self.close_connection = True

        if stream and model == "mock-truncate":
            stream_chunks(3, 0.0, finish=False)
            return
        if stream and model == "mock-slow-stream":
            stream_chunks(5, 2.0, finish=True)
            return
        if stream:
            stream_chunks(3, 0.0, finish=True)
            return

        self._json(200, {
            "id": "mock-1",
            "object": "chat.completion",
            "model": model,
            "choices": [{"index": 0, "message": {"role": "assistant", "content": "MOCK_OK"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 11, "completion_tokens": 3, "total_tokens": 14},
        })


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 18099
    open(LOG_PATH, "w", encoding="utf-8").close()
    print(f"mock llm on :{port}, log={LOG_PATH}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()
