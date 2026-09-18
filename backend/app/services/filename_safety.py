"""文件名安全化：把不可信输入（企业名/预案标题/票据号/上传名）压成安全的单段文件名。

2026-09-18 审计：多处用 `re.sub(r'[\\/*?:"<>|]', "_", name)` 或
`name.replace(" ", "_")` 直接拼落盘路径——

- 字符类里**漏了反斜杠**（Windows 下 `..\\..\\x` 会越出目录）；
- `resource_investigation` / `risk_assessment` 只替换空格，`../../x` 直接越界。

统一改为本模块的 `safe_filename()`：先归一化分隔符并取 basename，再过滤非法字符，
去掉前导点（避免 `..`/隐藏文件），保留中英文与常见符号，最后限长。
"""

import os
import re

_ILLEGAL = re.compile(r"[^\w.\-\u4e00-\u9fff]+")


def safe_filename(name: str | None, *, fallback: str = "file", max_len: int = 120) -> str:
    """返回可安全用于单段路径的文件名（不含目录分隔符，不会以点开头）。"""
    base = os.path.basename((name or "").replace("\\", "/")).strip()
    base = _ILLEGAL.sub("_", base).lstrip(". ")
    base = base.strip()
    if not base:
        base = fallback
    return base[:max_len]
