import { describe, expect, it } from "vitest";
import { APP_BASE, buildPublicUrl, stripAppBase } from "./platform";

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

  it("兄弟前缀路径不剥离", () => {
    expect(
      stripAppBase("/emergency-plan-migration2/m/login", "/emergency-plan-migration"),
    ).toBe("/emergency-plan-migration2/m/login");
  });

  it("pathname 恰等于 appBase 时剥离为空串", () => {
    expect(stripAppBase("/emergency-plan-migration", "/emergency-plan-migration")).toBe(
      "",
    );
  });
});

describe("APP_BASE", () => {
  it("始终为字符串（根路径构建时为空串）", () => {
    expect(typeof APP_BASE).toBe("string");
  });
});

describe("buildPublicUrl", () => {
  it("根路径部署时不注入额外前缀", () => {
    expect(buildPublicUrl("/r/abc", { origin: "https://example.com", appBase: "" })).toBe(
      "https://example.com/r/abc",
    );
  });

  it("子路径部署时在 origin 后注入 APP_BASE", () => {
    expect(
      buildPublicUrl("/p/risk/xyz", {
        origin: "https://example.com",
        appBase: "/emergency-plan-migration",
      }),
    ).toBe("https://example.com/emergency-plan-migration/p/risk/xyz");
  });

  it("自动补全缺失的前导斜杠", () => {
    expect(
      buildPublicUrl("h/report/tok", {
        origin: "https://example.com",
        appBase: "/sub",
      }),
    ).toBe("https://example.com/sub/h/report/tok");
  });
});
