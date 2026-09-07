"""思考要点加工：切句、筛选、截断、去重。仅供内存实时展示，不落库。"""
import re

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
    """累积一段推理文本，产出“最新一条尚未展示过的要点句”。"""

    def __init__(self, max_chars: int = 40):
        self._buffer = ""
        self._shown: set[str] = set()
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
            if is_key_point(sentence) and sentence not in self._shown:
                self._shown.add(sentence)
                return truncate_brief(sentence, self._max_chars)
        return None
