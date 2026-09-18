"""上传体积守卫：统一"按上限读取 + 超限 413"，避免把任意大文件读进内存。

背景（2026-09-18 审计）：多处上传处理器写成 ``data = await file.read()`` 再比较大小，
字节此时已经全部进内存——认证用户或误操作可以打出内存峰值。
与既有写法（``main.py:/upload``、``extraction``、``onboarding`` 的 read(MAX+1)）对齐。
"""

from fastapi import HTTPException, UploadFile

# 与 app/main.py 的 UPLOAD_MAX_BYTES 保持一致
DEFAULT_MAX_BYTES = 20 * 1024 * 1024


async def read_upload_capped(
    file: UploadFile,
    max_bytes: int = DEFAULT_MAX_BYTES,
    *,
    what: str = "文件",
) -> bytes:
    """读取上传内容，超过 max_bytes 抛 413（最多只读进 max_bytes+1 字节）。"""
    data = await file.read(max_bytes + 1)
    if len(data) > max_bytes:
        # 上限文案按量级选择单位（测试里会把上限调小，避免出现"0MB"）
        if max_bytes >= 1024 * 1024:
            limit_text = f"{max_bytes // (1024 * 1024)}MB"
        elif max_bytes >= 1024:
            limit_text = f"{max_bytes // 1024}KB"
        else:
            limit_text = f"{max_bytes} 字节"
        raise HTTPException(
            status_code=413,
            detail=f"{what}超过 {limit_text} 上限",
        )
    return data
