import { afterEach, describe, expect, it, vi } from "vitest";
import { dedupeInflight, resetInflight } from "./inflight";

afterEach(() => {
  resetInflight();
});

describe("dedupeInflight", () => {
  it("并发的同名请求只执行一次，且都拿到同一个结果", async () => {
    const factory = vi.fn(async () => "报告");
    const [a, b] = await Promise.all([
      dedupeInflight("risk:e1", factory),
      dedupeInflight("risk:e1", factory),
    ]);
    expect(factory).toHaveBeenCalledTimes(1);
    expect(a).toBe("报告");
    expect(b).toBe("报告");
  });

  it("不同 key 不互相合并", async () => {
    const factory = vi.fn(async () => "x");
    await Promise.all([dedupeInflight("risk:e1", factory), dedupeInflight("risk:e2", factory)]);
    expect(factory).toHaveBeenCalledTimes(2);
  });

  it("请求落地后再调用会重新发起（不缓存结果）", async () => {
    const factory = vi.fn(async () => "报告");
    await dedupeInflight("risk:e1", factory);
    await dedupeInflight("risk:e1", factory);
    expect(factory).toHaveBeenCalledTimes(2);
  });

  it("失败的请求也从在途表移除，不吞掉 rejection", async () => {
    const factory = vi.fn(async () => {
      throw new Error("boom");
    });
    await expect(dedupeInflight("risk:e1", factory)).rejects.toThrow("boom");
    const retry = vi.fn(async () => "ok");
    await expect(dedupeInflight("risk:e1", retry)).resolves.toBe("ok");
    expect(retry).toHaveBeenCalledTimes(1);
  });
});
