import { describe, expect, it } from "vitest";
import { buildLoginPath, resolveRedirectTarget } from "./loginRedirect";

describe("resolveRedirectTarget", () => {
  it("空值返回 null", () => {
    expect(resolveRedirectTarget(null)).toBeNull();
    expect(resolveRedirectTarget(undefined)).toBeNull();
    expect(resolveRedirectTarget("")).toBeNull();
  });

  it("接受站内相对路径并保留 query", () => {
    expect(resolveRedirectTarget("/enterprises/abc/plans?page=2")).toBe(
      "/enterprises/abc/plans?page=2",
    );
  });

  it("拒绝协议相对路径（// 开头）", () => {
    expect(resolveRedirectTarget("//evil.example.com/steal")).toBeNull();
  });

  it("拒绝外部绝对 URL", () => {
    expect(resolveRedirectTarget("https://evil.example.com/steal")).toBeNull();
  });

  it("拒绝 javascript: 伪协议", () => {
    expect(resolveRedirectTarget("javascript:alert(1)")).toBeNull();
  });

  it("部署子路径前缀会被剥离成站内路径", () => {
    expect(
      resolveRedirectTarget("/emergency-plan-migration/dashboard", "/emergency-plan-migration"),
    ).toBe("/dashboard");
  });

  it("无子路径时普通站内路径原样保留", () => {
    expect(resolveRedirectTarget("/dashboard", "")).toBe("/dashboard");
  });
});

describe("buildLoginPath", () => {
  it("无回跳目标时为普通登录路径", () => {
    expect(buildLoginPath(null)).toBe("/login");
  });

  it("回跳目标被编码为 query", () => {
    expect(buildLoginPath("/plans/1/edit?enterprise_id=e1")).toBe(
      "/login?redirect=%2Fplans%2F1%2Fedit%3Fenterprise_id%3De1",
    );
  });

  it("非法回跳目标被丢弃", () => {
    expect(buildLoginPath("https://evil.example.com/x")).toBe("/login");
  });
});
