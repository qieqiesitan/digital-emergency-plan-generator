import { describe, expect, it } from "vitest";
import {
  planEditorUrl,
  planPreviewUrl,
  planVersionsUrl,
  sanitizeEditorSearchParams,
} from "./planUrls";

describe("planEditorUrl", () => {
  it("无企业语境时只含预案 id", () => {
    expect(planEditorUrl("p1")).toBe("/plans/p1/edit");
  });

  it("携带企业语境与样章参数", () => {
    expect(planEditorUrl("p1", { enterpriseId: "e1", autoGenerate: "sample" })).toBe(
      "/plans/p1/edit?enterprise_id=e1&auto_generate=sample",
    );
  });

  it("企业 id 为空时不写空参数", () => {
    expect(planEditorUrl("p1", { enterpriseId: "" })).toBe("/plans/p1/edit");
  });
});

describe("planVersionsUrl / planPreviewUrl", () => {
  it("版本历史透传企业语境", () => {
    expect(planVersionsUrl("p1", { enterpriseId: "e1" })).toBe(
      "/plans/p1/versions?enterprise_id=e1",
    );
  });

  it("导出预览透传企业语境", () => {
    expect(planPreviewUrl("p1", { enterpriseId: "e1" })).toBe(
      "/plans/p1/preview?enterprise_id=e1",
    );
  });
});

describe("sanitizeEditorSearchParams", () => {
  it("仅删除 auto_generate，保留企业语境", () => {
    expect(sanitizeEditorSearchParams("?auto_generate=sample&enterprise_id=e1")).toBe(
      "?enterprise_id=e1",
    );
  });

  it("删除后无剩余参数时返回空串", () => {
    expect(sanitizeEditorSearchParams("?auto_generate=1")).toBe("");
  });

  it("保留与企业无关的其他参数", () => {
    expect(sanitizeEditorSearchParams("?auto_generate=sample&ai=1")).toBe("?ai=1");
  });
});
