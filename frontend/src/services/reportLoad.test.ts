/** 报告读取的空态契约：企业还没生成报告时，不该被当成"错误"处理。
 *
 * 回归背景：空报告时每个 tab 会发两次相同请求（StrictMode 双挂载）各返回 404，
 * 浏览器控制台留下重复红字、全局拦截器还会弹错误提示。
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { getRiskAssessment } from "./riskAssessmentService";
import { getResourceInvestigation } from "./resourceInvestigationService";
import { resetInflight } from "./inflight";
import { riskAssessmentAdapter, resourceInvestigationAdapter } from "./reportAdapters";

const { apiMock } = vi.hoisted(() => ({
  apiMock: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() },
}));

vi.mock("@/services/api", () => ({ default: apiMock }));

const EMPTY = { data: { code: 0, message: "ok", data: null } };

describe("报告读取空态（无数据不报错）", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    resetInflight();
    apiMock.get.mockResolvedValue(EMPTY);
  });

  afterEach(() => {
    vi.restoreAllMocks();
    resetInflight();
  });

  it("后端 data=null → 返回 null（空态），且请求不吞掉全局错误提示", async () => {
    await expect(getRiskAssessment("e1")).resolves.toBeNull();
    expect(apiMock.get).toHaveBeenCalledWith("/enterprises/e1/risk-assessment", {});
  });

  it("资源调查报告同理（空态 + 真故障仍会走全局提示）", async () => {
    await expect(getResourceInvestigation("e1")).resolves.toBeNull();
    expect(apiMock.get).toHaveBeenCalledWith("/enterprises/e1/resource-investigation", {});
  });

  it("自带失败态的调用方（如预览页编辑）可显式传 skipGlobalError", async () => {
    await getRiskAssessment("e1", { skipGlobalError: true });
    expect(apiMock.get).toHaveBeenCalledWith(
      "/enterprises/e1/risk-assessment",
      { skipGlobalError: true },
    );
  });

  it("并发同名读取只发一次请求（StrictMode 双挂载不再重复）", async () => {
    await Promise.all([getRiskAssessment("e1"), getRiskAssessment("e1")]);
    expect(apiMock.get).toHaveBeenCalledTimes(1);
  });

  it("适配器把空态转成 null 文档（工作台据此渲染「尚未生成」空态）", async () => {
    await expect(riskAssessmentAdapter.load("e1")).resolves.toBeNull();
    await expect(resourceInvestigationAdapter.load("e1")).resolves.toBeNull();
  });

  it("有报告时照常返回文档（空态改动没破坏正常路径）", async () => {
    apiMock.get.mockResolvedValue({
      data: {
        code: 0,
        message: "ok",
        data: {
          id: "r1",
          enterprise_id: "e1",
          title: "风险评估报告",
          content: "正文",
          status: "completed",
          generated_by: "ai",
          generated_at: null,
          created_at: "",
          updated_at: "",
          current_version: 2,
          summary: { chapters: [{ key: "ch1", title: "一、辨识", content: "x" }] },
        },
      },
    });
    const doc = await riskAssessmentAdapter.load("e1");
    expect(doc?.title).toBe("风险评估报告");
    expect(doc?.chapters).toEqual([{ key: "ch1", title: "一、辨识", content: "x" }]);
  });
});
