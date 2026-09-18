import { describe, expect, it } from "vitest";
import { withRowKeys } from "./stableRowKey";

describe("withRowKeys", () => {
  it("用业务前缀 + 下标生成唯一 key，且不改动原数组", () => {
    const rows = [
      { zone: "罐区", object: "储罐", accident: "泄漏" },
      { zone: "罐区", object: "储罐", accident: "泄漏" },
    ];
    const keyed = withRowKeys(rows, r => `${r.zone}-${r.object}-${r.accident}`);
    expect(keyed).toHaveLength(2);
    expect(keyed[0].__rowKey).toBe("罐区-储罐-泄漏-0");
    expect(keyed[1].__rowKey).toBe("罐区-储罐-泄漏-1");
    expect(new Set(keyed.map(k => k.__rowKey)).size).toBe(2);
    expect(rows[0]).not.toHaveProperty("__rowKey");
  });

  it("保留原有字段供列 render 使用", () => {
    const keyed = withRowKeys([{ name: "甲", value: 1 }], r => r.name);
    expect(keyed[0].value).toBe(1);
    expect(keyed[0].__rowKey).toBe("甲-0");
  });
});
