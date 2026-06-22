import functools
import time
import asyncio
import json
import logging
from fastapi import Request
from app.config import settings
from app.ywt_client import upload_oper_log

logger = logging.getLogger("ywt_log")


def _extract_request(*args, **kwargs) -> Request | None:
    """从函数参数中提取 FastAPI Request 对象"""
    for arg in args:
        if isinstance(arg, Request):
            return arg
    for v in kwargs.values():
        if isinstance(v, Request):
            return v
    return None


def _build_log_data(
    title: str,
    business_type: str,
    request: Request | None,
    result: object,
    error: Exception | None,
    cost_time: int,
) -> dict:
    """构建 OperLogDTO 日志数据"""
    oper_param = ""
    if request:
        try:
            oper_param = json.dumps(dict(request.query_params), ensure_ascii=False)
        except Exception:
            oper_param = str(request.query_params)

    json_result = ""
    if not error and result is not None:
        try:
            json_result = json.dumps(result, ensure_ascii=False, default=str)
        except Exception:
            json_result = str(result)

    return {
        "title": title,
        "operName": "",
        "operUrl": str(request.url.path) if request else "",
        "requestMethod": request.method if request else "",
        "operIp": request.client.host if (request and request.client) else "",
        "operParam": oper_param[:2000],  # 截断防止过长
        "jsonResult": json_result[:2000],
        "status": 1 if error else 0,
        "errorMsg": str(error)[:500] if error else "",
        "costTime": cost_time,
        "sysCode": settings.YWT_SYS_CODE,
        "businessType": business_type,
    }


def ywt_log(title: str, business_type: str = "OTHER"):
    """操作日志装饰器，自动上报到中台

    Usage:
        @router.post("/plans")
        @ywt_log(title="创建预案", business_type="INSERT")
        async def create_plan(request: Request, ...):
            ...
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            start = time.time()
            error = None
            result = None

            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                error = e
                raise
            finally:
                cost_time = int((time.time() - start) * 1000)
                request = _extract_request(*args, **kwargs)
                log_data = _build_log_data(title, business_type, request, result, error, cost_time)

                # 异步上报，不阻塞主流程
                asyncio.ensure_future(_safe_upload(log_data))

        return wrapper
    return decorator


async def _safe_upload(log_data: dict):
    """安全上报，异常不抛出"""
    try:
        await upload_oper_log(log_data)
    except Exception as e:
        logger.warning(f"YWT log upload failed (non-blocking): {e}")
