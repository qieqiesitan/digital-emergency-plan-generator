import { describe, expect, it } from "vitest";
import { omitFields } from "./omitFields";

describe("omitFields", () => {
  it("剥离指定字段且不改动原对象", () => {
    const row = { _key: "k1", _isNew: true, name: "某单位", distance: 120 };
    const cleaned = omitFields(row, ["_key", "_isNew"] as const);

    expect(cleaned).toEqual({ name: "某单位", distance: 120 });
    expect(row).toEqual({ _key: "k1", _isNew: true, name: "某单位", distance: 120 });
  });

  it("字段不存在时也返回等价副本", () => {
    const form = { category: "internal", name: "灭火器", _ext: "草稿" };
    expect(omitFields(form, ["_ext"] as const)).toEqual({
      category: "internal",
      name: "灭火器",
    });
  });
});
