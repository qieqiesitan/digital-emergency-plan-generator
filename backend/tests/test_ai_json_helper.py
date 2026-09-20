"""共用 AI JSON 入口的语义（对齐重构前 8 处样板的行为）。"""

import pytest
from fastapi import HTTPException

from app.services import ai_json


class _Cfg:
    model_name = "m"


def test_strip_code_fence_variants():
    assert ai_json.strip_code_fence('```json\n{"a": 1}\n```') == '{"a": 1}'
    assert ai_json.strip_code_fence('```\n{"a": 1}\n```') == '{"a": 1}'
    assert ai_json.strip_code_fence('{"a": 1}') == '{"a": 1}'
    assert ai_json.strip_code_fence('  ```json\n[1,2]\n```  ') == "[1,2]"


@pytest.mark.asyncio
async def test_json_ok(monkeypatch):
    async def fake(messages, cfg, timeout=60, module=None):  # noqa: ARG001
        return '```json\n{"items": []}\n```'

    monkeypatch.setattr(ai_json, "llm_text_completion", fake)
    out = await ai_json.ai_json_completion([], _Cfg())
    assert out == {"items": []}


@pytest.mark.asyncio
async def test_bad_json_maps_to_readable_500(monkeypatch):
    async def fake(messages, cfg, timeout=60, module=None):  # noqa: ARG001
        return "这不是 JSON"

    monkeypatch.setattr(ai_json, "llm_text_completion", fake)
    with pytest.raises(HTTPException) as ei:
        await ai_json.ai_json_completion([], _Cfg())
    assert ei.value.status_code == 500 and "格式异常" in ei.value.detail


@pytest.mark.asyncio
async def test_llm_error_maps_to_readable_500(monkeypatch):
    async def fake(messages, cfg, timeout=60, module=None):  # noqa: ARG001
        raise RuntimeError("boom")

    monkeypatch.setattr(ai_json, "llm_text_completion", fake)
    with pytest.raises(HTTPException) as ei:
        await ai_json.ai_json_completion([], _Cfg())
    assert ei.value.status_code == 500 and "调用失败" in ei.value.detail


@pytest.mark.asyncio
async def test_http_exception_passthrough(monkeypatch):
    async def fake(messages, cfg, timeout=60, module=None):  # noqa: ARG001
        raise HTTPException(400, "系统未配置 AI 模型")

    monkeypatch.setattr(ai_json, "llm_text_completion", fake)
    with pytest.raises(HTTPException) as ei:
        await ai_json.ai_json_completion([], _Cfg())
    assert ei.value.status_code == 400


@pytest.mark.asyncio
async def test_db_connection_released_before_call(monkeypatch):
    released = {"called": False}

    async def fake_release(db):
        released["called"] = True
        return True

    async def fake(messages, cfg, timeout=60, module=None):  # noqa: ARG001
        return "{}"

    monkeypatch.setattr(ai_json, "release_request_connection", fake_release)
    monkeypatch.setattr(ai_json, "llm_text_completion", fake)
    await ai_json.ai_json_completion([], _Cfg(), db=object())
    assert released["called"] is True


def test_parse_items_shape_errors_are_readable():
    class M:
        def __init__(self, **kw):
            if "name" not in kw:
                raise ValueError("name 必填")
            self.name = kw["name"]

    assert ai_json.parse_items({"items": [{"name": "a"}]}, "items", M)[0].name == "a"
    assert ai_json.parse_items({"items": "oops"}, "items", M) == []
    with pytest.raises(HTTPException) as ei:
        ai_json.parse_items({"items": [{}]}, "items", M)
    assert ei.value.status_code == 500 and "格式异常" in ei.value.detail


def test_routers_no_longer_hand_roll_the_boilerplate():
    """源码守护：8 处样板已收敛，路由里不应再出现裸 json.loads(raw) 那套。"""
    import pathlib

    root = pathlib.Path(__file__).resolve().parents[1] / "app" / "routers"
    for name in ("hazardous_chemicals.py", "surrounding_ai.py", "resources_ext.py", "risk_sources_ext.py"):
        src = (root / name).read_text(encoding="utf-8")
        assert "ai_json_completion(" in src, f"{name} 未改用共用入口"
        assert "json.loads(raw)" not in src, f"{name} 仍在手写 JSON 解析样板"
