"""SSE 响应头守护：所有 SSE 构造点必须带 `SSE_HEADERS`（含 X-Accel-Buffering: no）。

背景（2026-09-19 部署审计）：nginx 默认 proxy_buffering on，会把 SSE 攒满缓冲才下发，
前端"流式生成"退化为"转圈到结束才出现"；而 nginx 原生尊重上游的
`X-Accel-Buffering: no`。为避免以后新增 SSE 端点漏带头部，这里做源码级守护。
"""

import re
from pathlib import Path

import pytest

from app.services.sse_utils import SSE_HEADERS, sse_headers

ROUTERS = Path(__file__).resolve().parents[1] / "app" / "routers"
SSE_PATTERNS = (re.compile(r"text/event-stream"), re.compile(r"EventSourceResponse\("))


def test_sse_headers_contract():
    assert SSE_HEADERS["X-Accel-Buffering"] == "no"
    assert SSE_HEADERS["Cache-Control"] == "no-cache"
    merged = sse_headers(**{"X-Custom": "1"})
    assert merged["X-Custom"] == "1" and merged["X-Accel-Buffering"] == "no"


def test_every_sse_response_carries_headers():
    offenders: list[str] = []
    checked = 0
    for path in sorted(ROUTERS.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        for pattern in SSE_PATTERNS:
            for match in pattern.finditer(text):
                checked += 1
                # 取构造点往后 3 行窗口，要求出现 SSE_HEADERS
                window = text[match.start(): match.start() + 400]
                if "SSE_HEADERS" not in window and "sse_headers(" not in window:
                    line = text[: match.start()].count("\n") + 1
                    offenders.append(f"{path.name}:{line}")
    assert checked > 0, "未扫描到任何 SSE 构造点（守护测试失效）"
    assert not offenders, "以下 SSE 响应缺少 SSE_HEADERS（网关可能缓冲）：" + ", ".join(offenders)


@pytest.mark.parametrize("name", ["chat.py", "generation.py", "risk_assessment.py", "resource_investigation.py"])
def test_sse_routers_import_shared_headers(name):
    text = (ROUTERS / name).read_text(encoding="utf-8")
    assert "SSE_HEADERS" in text, f"{name} 未使用统一 SSE 头"
