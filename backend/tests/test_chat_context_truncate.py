"""test_chat_context_truncate.py — 上下文 token 预算截断。"""
from app.routers.chat import truncate_by_token_budget, _estimate_tokens


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
