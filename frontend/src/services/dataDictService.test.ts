import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  createEnterpriseDict,
  createSystemDict,
  deleteEnterpriseDict,
  listEnterpriseDicts,
  listSystemDicts,
  updateEnterpriseDict,
  updateSystemDict,
} from "./dataDictService";
import type { DataDictItem } from "@/types/dataDict";

const { apiMock } = vi.hoisted(() => ({
  apiMock: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() },
}));

vi.mock("@/services/api", () => ({ default: apiMock }));

const ITEM: DataDictItem = {
  id: "d1",
  dict_type: "measure_factors",
  code: "fire",
  label: "火灾",
  value: { weight: 3 },
  scope: "system",
  enterprise_id: null,
  sort_order: 1,
  enabled: true,
  is_system: true,
  description: "评估因子",
};

describe("dataDictService", () => {
  beforeEach(() => vi.clearAllMocks());

  it("listSystemDicts 调用 GET /settings/data-dicts 并携带 dict_type 参数", async () => {
    apiMock.get.mockResolvedValue({ data: { code: 0, message: "ok", data: [ITEM] } });

    const result = await listSystemDicts("measure_factors");

    expect(apiMock.get).toHaveBeenCalledWith("/settings/data-dicts", {
      params: { dict_type: "measure_factors" },
    });
    expect(result).toEqual([ITEM]);
  });

  it("createSystemDict POST /settings/data-dicts 并解包返回", async () => {
    const payload = {
      dict_type: "measure_factors",
      code: "fire",
      label: "火灾",
      value: { weight: 3 },
    };
    apiMock.post.mockResolvedValue({ data: { code: 0, message: "ok", data: ITEM } });

    const result = await createSystemDict(payload);

    expect(apiMock.post).toHaveBeenCalledWith("/settings/data-dicts", payload);
    expect(result).toEqual(ITEM);
  });

  it("updateSystemDict PUT /settings/data-dicts/{id} 携带补丁", async () => {
    apiMock.put.mockResolvedValue({ data: { code: 0, message: "ok", data: ITEM } });

    const result = await updateSystemDict("d1", { label: "火灾（修订）" });

    expect(apiMock.put).toHaveBeenCalledWith("/settings/data-dicts/d1", {
      label: "火灾（修订）",
    });
    expect(result).toEqual(ITEM);
  });

  it("listEnterpriseDicts 调用 GET 企业合并视图端点并携带 dict_type 参数", async () => {
    apiMock.get.mockResolvedValue({ data: { code: 0, message: "ok", data: [ITEM] } });

    const result = await listEnterpriseDicts("e1", "hazard_type");

    expect(apiMock.get).toHaveBeenCalledWith("/enterprises/e1/data-dicts", {
      params: { dict_type: "hazard_type" },
    });
    expect(result).toEqual([ITEM]);
  });

  it("createEnterpriseDict POST 企业端点", async () => {
    const payload = {
      dict_type: "hazard_type",
      code: "fire",
      label: "火灾",
      value: {},
    };
    apiMock.post.mockResolvedValue({ data: { code: 0, message: "ok", data: ITEM } });

    const result = await createEnterpriseDict("e1", payload);

    expect(apiMock.post).toHaveBeenCalledWith("/enterprises/e1/data-dicts", payload);
    expect(result).toEqual(ITEM);
  });

  it("updateEnterpriseDict PUT 企业条目端点", async () => {
    apiMock.put.mockResolvedValue({ data: { code: 0, message: "ok", data: ITEM } });

    const result = await updateEnterpriseDict("e1", "d1", { enabled: false });

    expect(apiMock.put).toHaveBeenCalledWith("/enterprises/e1/data-dicts/d1", {
      enabled: false,
    });
    expect(result).toEqual(ITEM);
  });

  it("deleteEnterpriseDict DELETE 企业条目端点", async () => {
    apiMock.delete.mockResolvedValue({ data: { code: 0, message: "ok", data: {} } });

    const result = await deleteEnterpriseDict("e1", "d1");

    expect(apiMock.delete).toHaveBeenCalledWith("/enterprises/e1/data-dicts/d1");
    expect(result).toEqual({});
  });
});
