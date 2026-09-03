import { describe, expect, it, vi } from "vitest";
import { riskAssessmentAdapter } from "./reportAdapters";
import * as ra from "./riskAssessmentService";

describe("riskAssessmentAdapter", () => {
  it("load 返回统一 ReportDocument 结构（chapters 来自 summary.chapters）", async () => {
    vi.spyOn(ra, "getRiskAssessment").mockResolvedValue({
      id: "r1", enterprise_id: "e1", title: "T", content: "",
      status: "draft", generated_by: "ai", generated_at: null,
      created_at: "", updated_at: "",
      summary: { chapters: [{ key: "ch1", title: "一、辨识", content: "x" }] },
    } as never);
    const doc = await riskAssessmentAdapter.load("e1");
    expect(doc.chapters).toEqual([{ key: "ch1", title: "一、辨识", content: "x" }]);
  });
});
