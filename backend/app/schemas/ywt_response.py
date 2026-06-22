from typing import Any
from fastapi import Request

# 中台标准成功码
YWT_SUCCESS_CODE = 200
# 独立模式成功码
STANDALONE_SUCCESS_CODE = 0


def is_ywt_mode(request: Request | None = None) -> bool:
    """判断当前请求是否为中台模式"""
    if request is None:
        return False
    return getattr(request.state, "is_ywt", False)


def ywt_response(data: Any = None, message: str = "操作成功", code: int | None = None, request: Request | None = None) -> dict:
    """统一响应包装，根据请求来源自动切换格式

    中台模式: {code: 200, message: "操作成功", data: ...}
    独立模式: {code: 0, message: "ok", data: ...}
    """
    ywt = is_ywt_mode(request)

    if code is not None:
        # 指定了 code，直接使用
        return {"code": code, "message": message, "data": data}

    if ywt:
        return {"code": YWT_SUCCESS_CODE, "message": message, "data": data}
    else:
        return {"code": STANDALONE_SUCCESS_CODE, "message": "ok", "data": data}


def ywt_error(message: str, code: int = 500, request: Request | None = None) -> dict:
    """统一错误响应"""
    ywt = is_ywt_mode(request)
    err_code = code if ywt else code
    return {"code": err_code, "message": message, "data": None}
