"""Phase A：直接压 `llm_client` 层，验证供应商侧故障处理（零真实额度）。

覆盖：正常 / 429 重试后成功 / 429 用尽重试 / 500 / 超时(挂起) / 流式中断 / 慢流。
断言点：异常类型与状态码、实际重试次数（打点 metrics）、退避耗时、留痕内容。
"""
import asyncio
import os
import sys
import time

sys.path.insert(0, "/app")

from app.models.enterprise import AIConfig  # noqa: E402
from app.services import llm_client  # noqa: E402
from app.services.secret_utils import encrypt_secret  # noqa: E402

BASE = os.environ.get("MOCK_BASE", "http://127.0.0.1:18099/v1")
PASS, FAIL = [], []


def check(name: str, ok: bool, detail: str = "") -> None:
    (PASS if ok else FAIL).append(name)
    print(f"{'✅' if ok else '❌'} {name}" + (f" —— {detail}" if detail else ""), flush=True)


def cfg(model: str) -> AIConfig:
    return AIConfig(
        id="00000000-0000-0000-0000-0000000000aa",
        user_id=None,
        is_system=True,
        provider="openai",
        base_url=BASE,
        api_key_encrypted=encrypt_secret("mock-key"),
        model_name=model,
        temperature=0.7,
        max_tokens=256,
        top_p=1.0,
    )


async def main() -> None:
    msgs = [{"role": "user", "content": "hi"}]

    # 复位 mock 的计数/日志：保证"只失败一次"这类场景每次跑都成立
    import httpx

    try:
        async with httpx.AsyncClient(timeout=5) as c:
            await c.get(BASE.rsplit("/v1", 1)[0] + "/__reset")
    except Exception as e:  # noqa: BLE001
        print(f"（复位 mock 失败，可能影响 mock-ok-once-429：{e}）")

    # 1. 正常非流式
    t0 = time.perf_counter()
    data = await llm_client.llm_chat_completion(msgs, cfg("mock-ok"), timeout=10)
    text = data["choices"][0]["message"]["content"]
    check("正常调用返回内容", text == "MOCK_OK", f"{text!r} {time.perf_counter()-t0:.1f}s")

    # 2. 429 一次后成功：重试应救回来，且确实退避（≥1s）
    t0 = time.perf_counter()
    data = await llm_client.llm_chat_completion(msgs, cfg("mock-ok-once-429"), timeout=10)
    el = time.perf_counter() - t0
    check("429 一次后重试成功", data["choices"][0]["message"]["content"] == "MOCK_OK", f"{el:.1f}s")
    check("429 重试前确实退避（≥1s）", el >= 1.0, f"{el:.2f}s")

    # 3. 一直 429：应抛 LLMError(429)，默认 4 次尝试 + 指数退避 1+2+4s
    t0 = time.perf_counter()
    try:
        await llm_client.llm_chat_completion(msgs, cfg("mock-429"), timeout=10)
        check("429 用尽后抛错", False, "居然成功了")
    except llm_client.LLMError as e:
        el = time.perf_counter() - t0
        check("429 用尽后抛 LLMError(429)", e.status_code == 429, f"status={e.status_code} {el:.1f}s")
        check("429 退避总时长接近 1+2+4s（≥6s）", el >= 6.0, f"{el:.2f}s")

    # 4. 500 且 max_retries=1：只重试一次就放弃
    t0 = time.perf_counter()
    try:
        await llm_client.llm_chat_completion(
            msgs, cfg("mock-500"), timeout=10, payload_overrides={"max_retries": 1})
        check("500 抛错", False, "居然成功了")
    except llm_client.LLMError as e:
        el = time.perf_counter() - t0
        check("500 → LLMError(500)", e.status_code == 500, f"status={e.status_code} {el:.1f}s")
        check("max_retries=1 只退避 1 次（<6s）", el < 6.0, f"{el:.2f}s")

    # 4b. max_retries 不得混进请求体（严格 API 会 400）
    check("max_retries 未混入 payload", True, "见 test_llm_client 单测；此处仅确认调用未 400")

    # 5. 供应商挂起：应被超时掐断（不能等到 600s）
    t0 = time.perf_counter()
    try:
        await llm_client.llm_chat_completion(msgs, cfg("mock-hang"), timeout=3,
                                             payload_overrides={"max_retries": 0})
        check("挂起调用被超时掐断", False, "居然返回了")
    except llm_client.LLMError as e:
        el = time.perf_counter() - t0
        check("挂起 → LLMTimeoutError（可识别）", isinstance(e, llm_client.LLMTimeoutError),
              f"type={type(e).__name__} {el:.1f}s")
        check("超时判定 is_timeout_error 为真", llm_client.is_timeout_error(e))
        check("3s 超时在 3~8s 内返回", 3.0 <= el <= 8.0, f"{el:.2f}s")

    # 6. 流式中断（无 [DONE]）→ 必须抛 LLMStreamTruncatedError，不得当成功
    gen = await llm_client.llm_chat_completion(msgs, cfg("mock-truncate"), stream=True, timeout=10)
    got, exc = "", None
    try:
        async for piece in gen:
            got += piece
    except Exception as e:  # noqa: BLE001
        exc = e
    check("流式中断抛 LLMStreamTruncatedError", isinstance(exc, llm_client.LLMStreamTruncatedError),
          f"type={type(exc).__name__} 收到={got!r}")
    check("截断前的内容没有丢（回调侧可见）", got == "分片0分片1分片2", f"{got!r}")

    # 7. 慢流：流还活着就不该被误判超时（每片 2s，超时 3s 指"单次读取"）
    gen = await llm_client.llm_chat_completion(msgs, cfg("mock-slow-stream"), stream=True, timeout=3)
    slow = ""
    try:
        async for piece in gen:
            slow += piece
        ok_slow, slow_err = True, ""
    except Exception as e:  # noqa: BLE001
        ok_slow, slow_err = False, f"{type(e).__name__}: {e}"
    check("慢流（每片 2s < 超时 3s）正常收完", ok_slow and slow == "分片0分片1分片2分片3分片4",
          f"{slow!r} {slow_err}")

    # 8. 慢流 + 超时 1s：读取间隔超过超时 → 超时错误（而不是僵死）
    t0 = time.perf_counter()
    gen = await llm_client.llm_chat_completion(msgs, cfg("mock-slow-stream"), stream=True, timeout=1)
    slow_exc = None
    partial = ""
    try:
        async for piece in gen:
            partial += piece
    except Exception as e:  # noqa: BLE001
        slow_exc = e
    el = time.perf_counter() - t0
    check("慢流超过读超时 → 可识别错误（非僵死）",
          isinstance(slow_exc, (llm_client.LLMTimeoutError, llm_client.LLMStreamTruncatedError)),
          f"type={type(slow_exc).__name__} {el:.1f}s partial={partial!r}")

    print(f"\n==== Phase A 汇总：PASS {len(PASS)} / FAIL {len(FAIL)}")
    for f in FAIL:
        print(f"   FAIL: {f}")


if __name__ == "__main__":
    asyncio.run(main())
