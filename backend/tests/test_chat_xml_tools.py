"""chat XML 工具调用兜底解析测试。"""
import json
from app.routers.chat import _extract_xml_tool_calls, _normalize_tool_calls


def test_extract_xml_tool_calls():
    content = (
        '<tool_calls>\n<invoke name="get_enterprise">\n'
        '<parameter name="name">西安宝岳空间科技有限公司</parameter>\n'
        "</invoke>\n</tool_calls>"
    )
    calls = _extract_xml_tool_calls(content)
    assert len(calls) == 1
    assert calls[0]["function"]["name"] == "get_enterprise"
    args = json.loads(calls[0]["function"]["arguments"])
    assert args["name"] == "西安宝岳空间科技有限公司"


def test_normalize_tool_calls_fallback():
    msg = {"role": "assistant", "content": '<invoke name="list_enterprises"><parameter name="keyword">测试</parameter></invoke>'}
    calls = _normalize_tool_calls(msg)
    assert len(calls) == 1
    assert calls[0]["function"]["name"] == "list_enterprises"
    assert msg["content"] is None  # XML 不再当正文


def test_normalize_keeps_openai_calls():
    msg = {"role": "assistant", "content": "查一下",
           "tool_calls": [{"id": "c1", "type": "function",
                           "function": {"name": "get_dashboard", "arguments": "{}"}}]}
    calls = _normalize_tool_calls(msg)
    assert len(calls) == 1 and calls[0]["id"] == "c1"
    assert msg["content"] == "查一下"


def test_normalize_plain_text_unchanged():
    msg = {"role": "assistant", "content": "普通回答"}
    assert _normalize_tool_calls(msg) == []
    assert msg["content"] == "普通回答"
