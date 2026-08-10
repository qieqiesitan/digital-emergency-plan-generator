import { describe, expect, it } from "vitest";
import { APP_BASE, stripAppBase } from "./platform";

describe("stripAppBase", () => {
  it("appBase 为空时原样返回 pathname", () => {
    expect(stripAppBase("/m/login", "")).toBe("/m/login");
  });

  it("剥离子路径前缀", () => {
    expect(
      stripAppBase("/emergency-plan-migration/m/login", "/emergency-plan-migration"),
    ).toBe("/m/login");
  });

  it("前缀不匹配时原样返回", () => {
    expect(stripAppBase("/other/m/login", "/emergency-plan-migration")).toBe(
      "/other/m/login",
    );
  });
});

describe("APP_BASE", () => {
  it("始终为字符串（根路径构建时为空串）", () => {
    expect(typeof APP_BASE).toBe("string");
  });
});
