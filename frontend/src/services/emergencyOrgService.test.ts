import { beforeEach, describe, expect, it, vi } from "vitest";
import { getEmergencyOrg, saveEmergencyOrg } from "./emergencyOrgService";
import type { EmergencyUnit } from "@/types/emergencyOrg";

const { apiMock } = vi.hoisted(() => ({
  apiMock: { get: vi.fn(), put: vi.fn() },
}));

vi.mock("@/services/api", () => ({ default: apiMock }));

const UNIT: EmergencyUnit = {
  id: "u1",
  parent_id: null,
  name: "应急组织机构",
  duties: "",
  roles: [],
};

describe("emergencyOrgService", () => {
  beforeEach(() => {
    apiMock.get.mockReset();
    apiMock.put.mockReset();
  });

  it("getEmergencyOrg 调用应急组织 GET 并解包 data", async () => {
    apiMock.get.mockResolvedValue({ data: { data: [UNIT] } });
    const out = await getEmergencyOrg("e1");
    expect(apiMock.get).toHaveBeenCalledWith("/enterprises/e1/emergency-org");
    expect(out).toEqual([UNIT]);
  });

  it("saveEmergencyOrg PUT 整树（字段名 units）并透传 skipGlobalError", async () => {
    apiMock.put.mockResolvedValue({ data: { data: [] } });
    await saveEmergencyOrg("e1", [], { skipGlobalError: true });
    expect(apiMock.put).toHaveBeenCalledWith(
      "/enterprises/e1/emergency-org",
      { units: [] },
      { skipGlobalError: true },
    );
  });

  it("saveEmergencyOrg 不传 config 时也发 PUT 且不带第三参", async () => {
    apiMock.put.mockResolvedValue({ data: { data: [UNIT] } });
    const out = await saveEmergencyOrg("e2", [UNIT]);
    expect(apiMock.put).toHaveBeenCalledWith("/enterprises/e2/emergency-org", { units: [UNIT] });
    expect(out).toEqual([UNIT]);
  });
});
