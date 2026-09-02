"""test_chat_context_truncate.py — 上下文 token 预算截断。"""
from app.routers.chat import truncate_by_token_budget, _estimate_tokens


def _chat_msg(role, content=None, **extra):
    m = {"role": role}
    if content is not None:
        m["content"] = content
    m.update(extra)
    return m


def _tool_calls_assistant(call_id, fn_name):
    return _chat_msg("assistant", None, tool_calls=[
        {"id": call_id, "type": "function",
         "function": {"name": fn_name, "arguments": "{}"}},
    ])


def test_estimate_tokens_simple():
    assert _estimate_tokens([{"role": "user", "content": "安全生产"}]) > 0


def test_small_context_untouched():
    msgs = [{"role": "system", "content": "sys"},
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"}]
    out = truncate_by_token_budget(msgs, budget=10000)
    assert len(out) == 3


def test_large_context_truncated_keeps_recent_and_summary():
    msgs = [{"role": "system", "content": "sys"}]
    for i in range(30):
        msgs.append({"role": "user", "content": f"问题{i}：这是一段比较长的用户消息内容用于撑大上下文。"})
        msgs.append({"role": "assistant", "content": f"回答{i}：对应的一段较长回答内容。"})
    out = truncate_by_token_budget(msgs, budget=800)
    assert any(m.get("content", "").startswith("【历史摘要】") for m in out)
    assert any(m.get("content", "").startswith("问题29") for m in out)   # 最近轮保留
    assert _estimate_tokens(out) <= 800 * 1.2           # 近似预算（±20% 容差）


def test_truncate_removes_orphan_tool_at_window_start():
    """B7：截断窗口以 tool 消息开头（其 assistant 已被压缩）→ 孤儿 tool 必须被丢弃。"""
    text = "x" * 40
    msgs = [{"role": "system", "content": "sys"}]
    msgs += [
        _chat_msg("user", text), _chat_msg("assistant", text),
        _chat_msg("user", text), _chat_msg("assistant", text),
        _chat_msg("user", text), _chat_msg("assistant", text),
        _tool_calls_assistant("c1", "get_dashboard"),
        _chat_msg("tool", '{"ok": true}', tool_call_id="c1"),
        _chat_msg("user", text), _chat_msg("assistant", text),
    ]
    out = truncate_by_token_budget(msgs, budget=150)
    assert all(m.get("role") != "tool" for m in out)       # 无孤儿 tool 消息
    assert [m["role"] for m in out] == ["system", "system", "user", "assistant"]


def test_truncate_drops_dangling_assistant_tool_calls():
    """B7：窗口末尾 assistant(tool_calls) 的 tool 响应被切掉 → 该 assistant 必须被丢弃。"""
    text = "x" * 40
    msgs = [{"role": "system", "content": "sys"}]
    msgs += [
        _chat_msg("user", text), _chat_msg("assistant", text),
        _chat_msg("user", text), _chat_msg("assistant", text),
        _chat_msg("user", text), _chat_msg("assistant", text),
        _chat_msg("user", text), _chat_msg("assistant", text),
        _chat_msg("user", text),
        _tool_calls_assistant("c2", "list_enterprises"),
    ]
    out = truncate_by_token_budget(msgs, budget=150)
    assert all(not (m.get("role") == "assistant" and "tool_calls" in m) for m in out)
    assert [m["role"] for m in out] == ["system", "system", "assistant", "user"]


def test_truncate_keeps_complete_tool_call_pair():
    """B7：完整 assistant(tool_calls)+tool 配对落在窗口内 → 必须原样保留。"""
    text = "x" * 40
    msgs = [{"role": "system", "content": "sys"}]
    msgs += [
        _chat_msg("user", text), _chat_msg("assistant", text),
        _chat_msg("user", text), _chat_msg("assistant", text),
        _chat_msg("user", text), _chat_msg("assistant", text),
        _chat_msg("user", text),
        _tool_calls_assistant("c3", "get_dashboard"),
        _chat_msg("tool", '{"ok": true}', tool_call_id="c3"),
        _chat_msg("assistant", text),
    ]
    out = truncate_by_token_budget(msgs, budget=150)
    pairs = [(i, m) for i, m in enumerate(out)
             if m.get("role") == "assistant" and "tool_calls" in m]
    assert pairs, "完整 tool_calls 配对不应被截断误删"
    i, m = pairs[0]
    assert out[i + 1]["role"] == "tool"
    assert out[i + 1]["tool_call_id"] == m["tool_calls"][0]["id"]
