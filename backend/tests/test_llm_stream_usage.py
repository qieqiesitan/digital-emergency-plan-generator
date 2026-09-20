"""流式调用的 token 用量留痕（2026-09-20 真实额度验收发现的问题）。

现象：25 章批量生成产出了 10 万+ 字，但 `llm_call_logs` 里这些调用的
prompt/completion/total tokens **全是 NULL** —— 流式请求默认不返回 usage，
用量统计因此漏掉最贵的那部分（聊天 / 章节生成 / 报告）。

修复：① 对官方三家 provider 附加 `stream_options.include_usage`；
      ② 解析最后那个 `{"choices": [], "usage": {...}}` 分片并写进留痕；
      ③ 顺手修掉"choices 为空数组时会 IndexError 打断整条流"的隐患。
"""
import pytest

from app.services import llm_client


class _Cfg:
    api_key_encrypted = "00" * 16
    provider = "deepseek"
    base_url = "https://example.invalid/v1"
    model_name = "test-model"
    temperature = 0.7
    max_tokens = 100
    top_p = 1.0


class _Resp:
    status_code = 200

    def __init__(self, lines, payload_sink=None):
        self._lines = lines

    async def aread(self):
        return b""

    async def aiter_lines(self):
        for line in self._lines:
            yield line


class _Ctx:
    def __init__(self, resp):
        self._resp = resp

    async def __aenter__(self):
        return self._resp

    async def __aexit__(self, *a):
        return False


class _Client:
    def __init__(self, lines, sink):
        self._lines = lines
        self._sink = sink

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    def stream(self, _method, _url, **kwargs):
        if self._sink is not None:
            self._sink.update(kwargs.get("json") or {})
        return _Ctx(_Resp(self._lines))


def _patch(monkeypatch, lines, sink=None):
    monkeypatch.setattr(llm_client, "decrypt_api_key", lambda _: "sk-test")
    monkeypatch.setattr(llm_client.httpx, "AsyncClient", lambda *a, **k: _Client(lines, sink))


@pytest.mark.asyncio
async def test_stream_usage_chunk_is_recorded(monkeypatch):
    """include_usage 的 usage 分片必须进留痕，且不能让流崩掉。"""
    lines = [
        'data: {"choices":[{"delta":{"content":"你"}}]}',
        'data: {"choices":[{"delta":{"content":"好"}}]}',
        # 真实供应商在 include_usage 时最后一个分片长这样：choices 为空数组
        'data: {"choices":[],"usage":{"prompt_tokens":120,"completion_tokens":30,"total_tokens":150}}',
        "data: [DONE]",
    ]
    _patch(monkeypatch, lines)
    records = []

    async def fake_emit(record):
        records.append(record)

    monkeypatch.setattr(llm_client, "_emit_telemetry", fake_emit)

    gen = await llm_client.llm_chat_completion(
        [{"role": "user", "content": "hi"}], _Cfg(), stream=True
    )
    text = "".join([chunk async for chunk in gen])

    assert text == "你好"
    assert len(records) == 1
    assert records[0].success is True
    assert records[0].total_tokens == 150
    assert records[0].prompt_tokens == 120
    assert records[0].completion_tokens == 30


@pytest.mark.asyncio
async def test_stream_options_only_for_official_base(monkeypatch):
    """官方 base 才加 stream_options；自定义网关不加（避免严格 API 400）。"""
    sink: dict = {}
    _patch(monkeypatch, ["data: [DONE]"], sink)
    monkeypatch.setattr(llm_client, "_emit_telemetry", lambda *_: _noop())

    # 自定义 base_url（非官方）→ 不加
    gen = await llm_client.llm_chat_completion([{"role": "user", "content": "hi"}], _Cfg(), stream=True)
    _ = [chunk async for chunk in gen]          # 必须消费生成器才会真正发请求
    assert "stream_options" not in sink

    sink.clear()

    class _Official(_Cfg):
        base_url = None  # 走内置映射 → https://api.deepseek.com/v1

    gen = await llm_client.llm_chat_completion([{"role": "user", "content": "hi"}], _Official(), stream=True)
    _ = [chunk async for chunk in gen]
    assert sink.get("stream_options") == {"include_usage": True}


async def _noop():
    return None
