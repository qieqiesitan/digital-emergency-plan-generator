"""test_thinking_brief.py"""
from app.services.thinking_brief import (
    ThinkingBriefBuffer, is_key_point, split_sentences, truncate_brief,
)


def test_split_sentences_splits_on_chinese_punctuation_and_newline():
    text = "第一句。第二句！\n第三句？"
    assert split_sentences(text) == ["第一句", "第二句", "第三句"]


def test_is_key_point_requires_reasonable_length_and_keyword():
    assert is_key_point("需要结合火灾风险源分布确定处置分工")
    assert not is_key_point("嗯")
    assert not is_key_point("这是一个没有关键词但长度足够凑数的普通句子内容")


def test_truncate_brief_keeps_max_chars_with_ellipsis():
    sentence = "结合火灾风险源分布与应急组织架构确定报警与初起处置分工以及信息报告要素"
    out = truncate_brief(sentence, max_chars=20)
    assert out.endswith("…")


def test_buffer_returns_newest_key_point_once():
    buf = ThinkingBriefBuffer()
    out1 = buf.feed("需要结合火灾风险源分布确定分工。")
    assert out1 is not None and "风险源" in out1
    out2 = buf.feed("其次考虑组织架构。")
    assert out2 is not None and "组织" in out2
    assert buf.feed("需要结合火灾风险源分布确定分工。") is None


def test_buffer_returns_none_without_key_point():
    buf = ThinkingBriefBuffer()
    assert buf.feed("嗯嗯好的。") is None
