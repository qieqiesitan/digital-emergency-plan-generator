"""思考要点加工：切句、筛选、截断、去重。仅供内存实时展示，不落库。"""
import re
import time as _time

_KEY_WORDS = (
    "分析", "结合", "需要", "根据", "确保", "考虑", "风险", "资源",
    "组织", "疏散", "法规", "火灾", "事故", "处置", "报告", "检查",
)
_SENTENCE_END = re.compile(r"[。！？!?；;\n]+")


def split_sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE_END.split(text or "") if s.strip()]


def is_key_point(sentence: str) -> bool:
    return 8 <= len(sentence) <= 60 and any(k in sentence for k in _KEY_WORDS)


def truncate_brief(sentence: str, max_chars: int = 40) -> str:
    sentence = (sentence or "").strip()
    if len(sentence) <= max_chars:
        return sentence
    return sentence[:max_chars].rstrip() + "…"


class ThinkingBriefBuffer:
    """累积一段推理文本，产出“最新一条要点句”（截断后）。去重与节流由 CaptionThrottle 负责。"""

    def __init__(self, max_chars: int = 40):
        self._buffer = ""
        self._max_chars = max_chars

    def feed(self, piece: str) -> str | None:
        self._buffer += piece or ""
        parts = split_sentences(self._buffer)
        if not parts:
            return None
        if not self._buffer.rstrip().endswith(("。", "！", "？", "!", "?", "；", ";")):
            self._buffer = parts.pop()
        else:
            self._buffer = ""
        for sentence in reversed(parts):
            if is_key_point(sentence):
                return truncate_brief(sentence, self._max_chars)
        return None


def fallback_caption(section_title: str) -> str:
    return f"正在分析「{section_title or '本章'}」所需的企业风险与法规信息…"


class CaptionThrottle:
    """对要点句做 >=min_interval 秒的节流 + 已展示去重；节流压下的句子进入待发队列。"""

    def __init__(self, section_title: str, min_interval: float = 1.5,
                 now=None, max_chars: int = 40):
        self._buffer = ThinkingBriefBuffer(max_chars=max_chars)
        self._pending: list[str] = []
        self._emitted: set[str] = set()
        self._min_interval = min_interval
        self._now = now or _time.time
        self._last_emit: float | None = None
        self.section_title = section_title

    def push(self, piece: str) -> str | None:
        caption = self._buffer.feed(piece)
        if caption and caption not in self._emitted:
            self._pending.append(caption)
        if not self._pending:
            return None
        now = self._now()
        if self._last_emit is not None and now - self._last_emit < self._min_interval:
            return None
        self._last_emit = now
        caption = self._pending.pop(0)
        self._emitted.add(caption)
        return caption
