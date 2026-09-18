"""LLM 供应商异常行为模拟：429 / 500 / 401 / 超时 / 流中断 / 正常流。

用本地 mock 服务器替代真实供应商（零费用），逐一验证 llm_client 的重试、退避、
错误映射与流式截断行为。

用法（容器内）: python /app/exports/_llm_resilience_probe.py
"""

import asyncio
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace

import httpx
from fastapi import HTTPException

from app.services.llm_client import (
    LLMError,
    _stream_response,
    llm_chat_completion,
    llm_text_completion,
)
from app.services.secret_utils import encrypt_secret

PORT = 8899
ATTEMPTS = {"count": 0}


def _sse(obj: dict) -> bytes:
    return f"data: {json.dumps(obj)}\n\n".encode()


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):  # 静默
        return

    def _mode(self):
        return self.path.split("/")[1]

    def do_POST(self):
        ATTEMPTS["count"] += 1
        mode = self._mode()
        length = int(self.headers.get("Content-Length", 0) or 0)
        if length:
            self.rfile.read(length)
        if mode == "429":
            body = b'{"error":"rate limited"}'
            self.send_response(429)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if mode == "500":
            body = b'{"error":"server error"}'
            self.send_response(500)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if mode == "401":
            body = b'{"error":"invalid key"}'
            self.send_response(401)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if mode == "slow":
            time.sleep(3)
            body = b'{"choices":[{"message":{"content":"late"}}]}'
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if mode == "ok-stream":
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "close")
            self.end_headers()
            for piece in ("A", "B", "C"):
                self.wfile.write(_sse({"choices": [{"delta": {"content": piece}}]}))
                self.wfile.flush()
                time.sleep(0.15)
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()
            return
        if mode == "cut-stream":
            # 只发 2 块后直接断开（无 [DONE]、无 Content-Length、非 chunked 终止）
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            self.wfile.write(_sse({"choices": [{"delta": {"content": "X1"}}]}))
            self.wfile.write(_sse({"choices": [{"delta": {"content": "X2"}}]}))
            self.wfile.flush()
            self.close_connection = True
            try:
                self.connection.shutdown(2)
            except Exception:  # noqa: BLE001
                pass
            return
        body = b"{}"
        self.send_response(404)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def cfg(mode):
    return SimpleNamespace(
        provider="mock", base_url=f"http://127.0.0.1:{PORT}/{mode}",
        api_key_encrypted=encrypt_secret("mock-key"),
        model_name="mock-model", temperature=0.1, max_tokens=32, top_p=1.0,
    )


async def run():
    out = []

    async def case(name, mode, *, stream=False, timeout=5, max_retries=2, use_text_completion=False):
        ATTEMPTS["count"] = 0
        t0 = time.time()
        res = {"case": name, "mode": mode}
        try:
            if stream:
                pieces = []
                gen = await llm_chat_completion([{"role": "user", "content": "hi"}], cfg(mode),
                                                stream=True, timeout=timeout)
                async for piece in gen:
                    pieces.append(piece)
                    if len(pieces) > 20:
                        break
                res["pieces"] = pieces
                res["piece_count"] = len(pieces)
                res["duplicated_prefix"] = len(pieces) > 2 and pieces[:2] == pieces[2:4]
            elif use_text_completion:
                text = await llm_text_completion([{"role": "user", "content": "hi"}], cfg(mode), timeout=timeout)
                res["text"] = text
            else:
                data = await llm_chat_completion([{"role": "user", "content": "hi"}], cfg(mode),
                                                 stream=False, timeout=timeout,
                                                 payload_overrides={"max_retries": max_retries})
                res["content"] = data.get("choices", [{}])[0].get("message", {}).get("content")
            res["outcome"] = "success"
        except LLMError as exc:
            res["outcome"] = "LLMError"
            res["llm_status"] = exc.status_code
            res["llm_text"] = str(exc)[:160]
        except HTTPException as exc:
            res["outcome"] = f"HTTPException({exc.status_code})"
            res["detail"] = str(exc.detail)[:160]
        except Exception as exc:  # noqa: BLE001
            res["outcome"] = f"{type(exc).__name__}"
            res["error"] = str(exc)[:160]
        res["attempts"] = ATTEMPTS["count"]
        res["elapsed_s"] = round(time.time() - t0, 2)
        out.append(res)
        print(json.dumps(res, ensure_ascii=False), flush=True)

    await case("429 限流：默认重试 3 次后抛错", "429")
    await case("500 服务端错误：重试后抛错", "500", max_retries=1)
    await case("401 无效 Key：不应重试", "401")
    await case("超时：timeout=1 客户端超时", "slow", timeout=1, max_retries=1)
    await case("超时经 llm_text_completion 的错误映射", "slow", timeout=1, use_text_completion=True)
    await case("正常流式：3 块 + [DONE]", "ok-stream", stream=True)
    await case("流中断（2 块后断连）", "cut-stream", stream=True, max_retries=1)

    print("\n==== 汇总 ====")
    for r in out:
        print(f"{r['case']:38s} attempts={r['attempts']} elapsed={r['elapsed_s']}s -> {r['outcome']}"
              f"{' status=' + str(r.get('llm_status')) if r.get('llm_status') is not None else ''}"
              f"{' pieces=' + str(r.get('piece_count')) if r.get('piece_count') is not None else ''}"
              f"{' dup=' + str(r.get('duplicated_prefix')) if r.get('duplicated_prefix') is not None else ''}")
    return out


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    result = asyncio.run(run())
    with open("/app/exports/e2e-20260917/llm-resilience.json", "w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=1)
    server.shutdown()
