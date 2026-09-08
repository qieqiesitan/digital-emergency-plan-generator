"""报告章节尾部 JSON 摘要提取。

风险评估 ch5 / 资源调查 ch6 要求模型在正文末尾输出结构化 JSON 摘要
（含嵌套对象/数组）。旧实现用不含嵌套的正则，摘要永远解析失败；
这里用平衡大括号扫描 + json.loads 校验提取尾部 JSON 对象。
"""

import json
from typing import Optional


def extract_trailing_json(text: str) -> Optional[dict]:
    """提取文本末尾的 JSON 对象；不是对象或无法解析返回 None。"""
    if not text:
        return None
    stripped = text.rstrip()
    if not stripped.endswith("}"):
        return None

    depth = 0
    in_string = False
    escaped = False
    # 从尾部倒扫，遇到配平的顶层 "{" 即候选起点
    for i in range(len(stripped) - 1, -1, -1):
        ch = stripped[i]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == "}":
            depth += 1
        elif ch == "{":
            depth -= 1
            if depth == 0:
                candidate = stripped[i:]
                try:
                    parsed = json.loads(candidate)
                except Exception:
                    return None
                return parsed if isinstance(parsed, dict) else None
        elif ch == '"':
            in_string = True
    return None


def _match_json_object(text: str, start: int) -> int:
    """从 text[start]=='{' 开始找配平的 '}'，返回下标；找不到返回 -1。"""
    depth = 0
    in_string = False
    escaped = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return i
    return -1


def strip_trailing_json(text: str) -> tuple[str, Optional[dict]]:
    """从正文中剥离模型附加的 JSON 摘要，返回 (清理后的正文, 摘要 dict)。

    模型有时会在 JSON 之后追加说明文字（如“注：…”），此时不能用
    extract_trailing_json（要求 JSON 必须是文本末尾）。这里从右向左找
    最后一个能解析成 dict 的 JSON 对象，剥离它但保留其后正文。
    兼容模型误用全角引号（“ ”）的情况。
    """
    if not text:
        return text or "", None
    start_positions = [
        i for i, ch in enumerate(text)
        if ch == "{" and (i == 0 or text[i - 1].isspace())
    ]
    for start in reversed(start_positions):
        end = _match_json_object(text, start)
        if end < 0:
            continue
        candidate = text[start:end + 1]
        try:
            parsed = json.loads(candidate)
        except Exception:
            try:
                candidate_normalized = (
                    candidate.replace("“", '"').replace("”", '"')
                    .replace("‘", "'").replace("’", "'")
                )
                parsed = json.loads(candidate_normalized)
            except Exception:
                continue
        if isinstance(parsed, dict):
            head = text[:start].rstrip()
            tail = text[end + 1:].strip()
            cleaned = (head + "\n\n" + tail).strip() if tail else head
            return cleaned, parsed
    return text, None
