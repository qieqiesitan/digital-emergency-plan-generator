import { describe, expect, it } from "vitest";
import { getPageMeta } from "./pageMeta";

describe("getPageMeta", () => {
  it("工作台精确匹配", () => {
    expect(getPageMeta("/dashboard")).toEqual({
      title: "工作台",
      menuKey: "/dashboard",
    });
  });

  it("企业管理列表精确匹配", () => {
    expect(getPageMeta("/enterprises").menuKey).toBe("/enterprises");
  });

  it("企业驾驶舱按前缀匹配且高亮企业管理", () => {
    expect(getPageMeta("/enterprises/abc")).toEqual({
      title: "企业驾驶舱",
      menuKey: "/enterprises",
    });
  });

  it("企业预案列表优先于通用企业管理标题", () => {
    expect(getPageMeta("/enterprises/abc/plans")).toEqual({
      title: "企业预案",
      menuKey: "/enterprises",
    });
  });

  it("预案编辑器按前缀匹配且高亮预案列表", () => {
    expect(getPageMeta("/plans/p1/edit")).toEqual({
      title: "预案编辑器",
      menuKey: "/plans",
    });
  });

  it("预案导出预览有独立标题且高亮预案列表", () => {
    expect(getPageMeta("/plans/p1/preview").title).toBe("导出预览");
    expect(getPageMeta("/plans/p1/preview").menuKey).toBe("/plans");
  });

  it("设置页子路由返回精确菜单 key", () => {
    expect(getPageMeta("/settings/chemical-library")).toEqual({
      title: "化学品库管理",
      menuKey: "/settings/chemical-library",
    });
  });

  it("未知路径不产生菜单高亮与标题", () => {
    expect(getPageMeta("/no-such-page")).toEqual({
      title: "",
      menuKey: undefined,
    });
  });
});
