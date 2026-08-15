import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  aiRecordAssist,
  approveRecord,
  closeRecord,
  copyHazardTemplate,
  createHazardPlan,
  createHazardTemplate,
  createRecord,
  deleteHazardPlan,
  exportHazardLedger,
  fetchPublicHazard,
  getHazardDashboard,
  getHazardPublicity,
  getRecord,
  gradeRecord,
  listHazardPlans,
  listHazardTasks,
  listRecords,
  rectifyRecord,
  resetHazardPublicityToken,
  reviewRecord,
  submitPublicHazardReport,
  submitHazardTask,
  taskToRecord,
  updateHazardPlan,
} from "./hazardService";

const { apiMock } = vi.hoisted(() => ({
  apiMock: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() },
}));

vi.mock("@/services/api", () => ({ default: apiMock }));

function envelope<T>(data: T) {
  return { data: { code: 0, message: "ok", data } };
}

describe("hazardService records", () => {
  beforeEach(() => vi.clearAllMocks());

  it("listRecords 请求台账列表 URL 并透传筛选参数", async () => {
    apiMock.get.mockResolvedValue(envelope({
      items: [
        {
          id: "r1", enterprise_id: "e1", code: "HD-001", source_type: "report",
          title: "配电箱门破损", description: "门体变形", status: "rectifying",
          level: "major", status_label: "整改中", source_type_label: "上报",
          level_label: "重大",
        },
      ],
      stats: { total: 1, open: 1, major: 1, overdue: 0 },
    }));

    const result = await listRecords("e1", { status: "rectifying", scope: "overdue", q: "配电箱" });

    expect(apiMock.get).toHaveBeenCalledWith(
      "/enterprises/e1/hazard-inspection/records",
      { params: { status: "rectifying", scope: "overdue", q: "配电箱" } },
    );
    expect(result.items[0].status_label).toBe("整改中");
    expect(result.stats).toEqual({ total: 1, open: 1, major: 1, overdue: 0 });
  });

  it("getRecord 请求详情 URL 并解包 data", async () => {
    apiMock.get.mockResolvedValue(envelope({
      id: "r1", code: "HD-001", status_label: "整改中", object_name: "配电箱",
      measure_name: "每日巡检", rectifications: [], reviews: [], approvals: [],
      audit_logs: [],
    }));

    const result = await getRecord("e1", "r1");

    expect(apiMock.get).toHaveBeenCalledWith("/enterprises/e1/hazard-inspection/records/r1");
    expect(result.object_name).toBe("配电箱");
  });

  it("createRecord 请求登记 URL 并携带业务字段", async () => {
    apiMock.post.mockResolvedValue(envelope({ id: "r9", code: "HD-001", status: "registered" }));

    await createRecord("e1", {
      source_type: "inspection",
      title: "配电箱门破损",
      description: "门体变形",
      hazard_type: "equipment",
      location: "3 号车间",
    });

    expect(apiMock.post).toHaveBeenCalledWith(
      "/enterprises/e1/hazard-inspection/records",
      {
        source_type: "inspection",
        title: "配电箱门破损",
        description: "门体变形",
        hazard_type: "equipment",
        location: "3 号车间",
      },
    );
  });

  it("gradeRecord / rectifyRecord / reviewRecord / closeRecord 请求状态机 URL", async () => {
    apiMock.post.mockResolvedValue(envelope({ id: "r1", status: "rectifying" }));

    await gradeRecord("e1", "r1", { level: "major", grading_basis: "判定依据" });
    expect(apiMock.post).toHaveBeenCalledWith(
      "/enterprises/e1/hazard-inspection/records/r1/grade",
      { level: "major", grading_basis: "判定依据" },
    );

    await rectifyRecord("e1", "r1", { content: "已整改", reviewer_user_id: "u3" });
    expect(apiMock.post).toHaveBeenCalledWith(
      "/enterprises/e1/hazard-inspection/records/r1/rectify",
      { content: "已整改", reviewer_user_id: "u3" },
    );

    await reviewRecord("e1", "r1", { result: "pass", comment: "合格" });
    expect(apiMock.post).toHaveBeenCalledWith(
      "/enterprises/e1/hazard-inspection/records/r1/review",
      { result: "pass", comment: "合格" },
    );

    await closeRecord("e1", "r1", { comment: "销号" });
    expect(apiMock.post).toHaveBeenCalledWith(
      "/enterprises/e1/hazard-inspection/records/r1/close",
      { comment: "销号" },
    );
  });

  it("approveRecord 不传 body 时提交空对象", async () => {
    apiMock.post.mockResolvedValue(envelope({ id: "r1", status: "rectifying" }));
    await approveRecord("e1", "r1");
    expect(apiMock.post).toHaveBeenCalledWith(
      "/enterprises/e1/hazard-inspection/records/r1/approve",
      {},
    );
  });
});

describe("hazardService plans / tasks / templates / publicity / dashboard / ai / export", () => {
  beforeEach(() => vi.clearAllMocks());

  it("plans CRUD 请求对应 URL", async () => {
    apiMock.get.mockResolvedValue(envelope([{ id: "p1", name: "日常排查" }]));
    await listHazardPlans("e1");
    expect(apiMock.get).toHaveBeenCalledWith("/enterprises/e1/hazard-inspection/plans");

    apiMock.post.mockResolvedValue(envelope({ id: "p2", name: "专项" }));
    await createHazardPlan("e1", { name: "专项", category: "special", frequency: "monthly", zone_ids: ["z1"] });
    expect(apiMock.post).toHaveBeenCalledWith(
      "/enterprises/e1/hazard-inspection/plans",
      { name: "专项", category: "special", frequency: "monthly", zone_ids: ["z1"] },
    );

    apiMock.put.mockResolvedValue(envelope({ id: "p2", name: "专项改" }));
    await updateHazardPlan("e1", "p2", { name: "专项改" });
    expect(apiMock.put).toHaveBeenCalledWith(
      "/enterprises/e1/hazard-inspection/plans/p2",
      { name: "专项改" },
    );

    apiMock.delete.mockResolvedValue({ data: { code: 0 } });
    await deleteHazardPlan("e1", "p2");
    expect(apiMock.delete).toHaveBeenCalledWith("/enterprises/e1/hazard-inspection/plans/p2");
  });

  it("tasks 列表透传筛选参数、提交核对、一键转隐患 URL 正确", async () => {
    apiMock.get.mockResolvedValue(envelope([{ id: "t1", status: "pending" }]));
    await listHazardTasks("e1", { status: "pending", overdue: true });
    expect(apiMock.get).toHaveBeenCalledWith(
      "/enterprises/e1/hazard-inspection/tasks",
      { params: { status: "pending", overdue: true } },
    );

    apiMock.put.mockResolvedValue(envelope({ id: "t1", status: "done" }));
    await submitHazardTask("e1", "t1", { items: [{ item_id: "i1", result: "normal" }] });
    expect(apiMock.put).toHaveBeenCalledWith(
      "/enterprises/e1/hazard-inspection/tasks/t1",
      { items: [{ item_id: "i1", result: "normal" }] },
    );

    apiMock.post.mockResolvedValue(envelope({ id: "r1", source_type: "inspection" }));
    await taskToRecord("e1", "t1", { item_id: "i1", title: "异常项" });
    expect(apiMock.post).toHaveBeenCalledWith(
      "/enterprises/e1/hazard-inspection/tasks/t1/to-record",
      { item_id: "i1", title: "异常项" },
    );
  });

  it("templates 创建 / 复制 URL 正确", async () => {
    apiMock.post.mockResolvedValue(envelope({ id: "tpl1", source: "enterprise" }));
    await createHazardTemplate("e1", { name: "日常检查表", category: "daily", items: [{ content: "检查配电箱" }] });
    expect(apiMock.post).toHaveBeenCalledWith(
      "/enterprises/e1/hazard-inspection/templates",
      { name: "日常检查表", category: "daily", items: [{ content: "检查配电箱" }] },
    );

    await copyHazardTemplate("e1", "tpl0");
    expect(apiMock.post).toHaveBeenCalledWith("/enterprises/e1/hazard-inspection/templates/tpl0/copy");
  });

  it("publicity 列表与 token 重置 URL 正确", async () => {
    apiMock.get.mockResolvedValue(envelope([{ code: "HD-001", status: "整改中" }]));
    await getHazardPublicity("e1", "ongoing");
    expect(apiMock.get).toHaveBeenCalledWith(
      "/enterprises/e1/hazard-inspection/publicity",
      { params: { scope: "ongoing" } },
    );

    apiMock.post.mockResolvedValue(envelope({ token: "abc", link: "/h/abc" }));
    await resetHazardPublicityToken("e1");
    expect(apiMock.post).toHaveBeenCalledWith("/enterprises/e1/hazard-inspection/publicity-token");
  });

  it("getHazardDashboard 请求驾驶舱 URL 并解包 data", async () => {
    apiMock.get.mockResolvedValue(envelope({
      metrics: { open_hazards: 3, scan_pending: 1, overdue_count: 1 },
      charts: { type_distribution: [], monthly_trend: [], major_records: [], enterprise_comparison: [] },
      unread: { total: 2, mine: 1, by_type: { deadline: 2 } },
    }));

    const result = await getHazardDashboard("e1");

    expect(apiMock.get).toHaveBeenCalledWith("/enterprises/e1/hazard-inspection/dashboard");
    expect(result.metrics.open_hazards).toBe(3);
    expect(result.unread.total).toBe(2);
  });

  it("aiRecordAssist 请求 AI 摘要分类并解包建议", async () => {
    apiMock.post.mockResolvedValue(envelope({
      available: true,
      title: "配电箱门破损",
      hazard_type: "equipment",
      suggested_level: "一般",
      reason: "门体变形",
    }));

    const result = await aiRecordAssist("e1", { description: "配电箱门变形" });

    expect(apiMock.post).toHaveBeenCalledWith(
      "/enterprises/e1/hazard-inspection/ai/record-assist",
      { description: "配电箱门变形" },
    );
    expect(result.available).toBe(true);
    expect(result.title).toBe("配电箱门破损");
  });

  it("exportHazardLedger 以 blob responseType 请求导出 URL", async () => {
    apiMock.get.mockResolvedValue({ data: new Blob(["xlsx"]), headers: {} });
    await exportHazardLedger("e1");
    expect(apiMock.get).toHaveBeenCalledWith(
      "/enterprises/e1/hazard-inspection/export/ledger.xlsx",
      { responseType: "blob" },
    );
  });

  it("submitPublicHazardReport 请求免登录上报 URL 并携带 nonce", async () => {
    apiMock.post.mockResolvedValue(envelope({ message: "已提交，待企业管理员确认" }));

    const result = await submitPublicHazardReport("tok1", {
      description: "配电箱门破损",
      location: "3 号车间",
      photo_urls: ["data:image/png;base64,xxx"],
      nonce: "n-1",
    });

    expect(apiMock.post).toHaveBeenCalledWith(
      "/public/hazard/report/tok1",
      {
        description: "配电箱门破损",
        location: "3 号车间",
        photo_urls: ["data:image/png;base64,xxx"],
        nonce: "n-1",
      },
    );
    expect(result.message).toBe("已提交，待企业管理员确认");
  });

  it("fetchPublicHazard 请求公开公示 URL 并透传 scope、解包 data", async () => {
    apiMock.get.mockResolvedValue(envelope({
      enterprise_name: "甲**",
      items: [{ code: "HD-001", title: "配电箱", level: "major", status: "整改中", rectification: "整改中", source_type: "排查" }],
      generated_at: "2026-08-15T00:00:00Z",
      masked: true,
    }));

    const result = await fetchPublicHazard("tok1", "ongoing");

    expect(apiMock.get).toHaveBeenCalledWith(
      "/public/hazard/tok1",
      { params: { scope: "ongoing" } },
    );
    expect(result.enterprise_name).toBe("甲**");
    expect(result.masked).toBe(true);

    await fetchPublicHazard("tok1");
    expect(apiMock.get).toHaveBeenCalledWith("/public/hazard/tok1", { params: {} });
  });
});
