import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  createMember,
  deleteMember,
  downloadMemberTemplate,
  getOrgNodes,
  importMembers,
  listMembers,
  saveOrgNodes,
  searchBindableUsers,
  suggestOrgTree,
  updateMember,
} from "./enterpriseOrgService";
import type {
  EnterpriseMember,
  OrgNode,
  OrgTreeSuggestion,
} from "@/types/enterpriseOrg";

const { apiMock } = vi.hoisted(() => ({
  apiMock: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() },
}));

vi.mock("@/services/api", () => ({ default: apiMock }));

const NODE: OrgNode = {
  id: "d1",
  type: "dept",
  name: "生产部",
  parent_id: null,
  members: [],
};

const MEMBER: EnterpriseMember = {
  id: "m1",
  enterprise_id: "e1",
  user_id: "u2",
  email: "zhang@x.com",
  name: "张三",
  phone: null,
  org_node_id: "t1",
  position: "班组长",
  role: "team_leader",
  enabled: true,
};

function wrap<T>(data: T) {
  return { data: { code: 0, message: "ok", data } };
}

describe("enterpriseOrgService", () => {
  beforeEach(() => vi.clearAllMocks());

  it("getOrgNodes 调用 GET /org/nodes 并解包 data", async () => {
    apiMock.get.mockResolvedValue(wrap([NODE]));
    const result = await getOrgNodes("e1");
    expect(apiMock.get).toHaveBeenCalledWith("/enterprises/e1/org/nodes");
    expect(result).toEqual([NODE]);
  });

  it("saveOrgNodes 调用 PUT /org/nodes 携带整树", async () => {
    apiMock.put.mockResolvedValue(wrap([NODE]));
    const result = await saveOrgNodes("e1", [NODE]);
    expect(apiMock.put).toHaveBeenCalledWith("/enterprises/e1/org/nodes", {
      nodes: [NODE],
    });
    expect(result).toEqual([NODE]);
  });

  it("listMembers 调用 GET /org/members 并解包 data", async () => {
    apiMock.get.mockResolvedValue(wrap([MEMBER]));
    const result = await listMembers("e1");
    expect(apiMock.get).toHaveBeenCalledWith("/enterprises/e1/org/members");
    expect(result).toEqual([MEMBER]);
  });

  it("searchBindableUsers 调用 GET /org/members/search 携带 email 参数", async () => {
    apiMock.get.mockResolvedValue(wrap([{ id: "u2", email: "zhang@x.com", name: "张三" }]));
    const result = await searchBindableUsers("e1", "zhang");
    expect(apiMock.get).toHaveBeenCalledWith("/enterprises/e1/org/members/search", {
      params: { email: "zhang" },
    });
    expect(result).toEqual([{ id: "u2", email: "zhang@x.com", name: "张三" }]);
  });

  it("createMember 调用 POST /org/members 携带 payload", async () => {
    apiMock.post.mockResolvedValue(wrap(MEMBER));
    const result = await createMember("e1", { user_id: "u2", role: "team_leader" });
    expect(apiMock.post).toHaveBeenCalledWith("/enterprises/e1/org/members", {
      user_id: "u2",
      role: "team_leader",
    });
    expect(result).toEqual(MEMBER);
  });

  it("updateMember 调用 PUT /org/members/{id} 携带补丁", async () => {
    apiMock.put.mockResolvedValue(wrap({ ...MEMBER, position: "部长" }));
    const result = await updateMember("e1", "m1", { position: "部长" });
    expect(apiMock.put).toHaveBeenCalledWith("/enterprises/e1/org/members/m1", {
      position: "部长",
    });
    expect(result.position).toBe("部长");
  });

  it("deleteMember 调用 DELETE /org/members/{id}", async () => {
    apiMock.delete.mockResolvedValue(wrap({}));
    await deleteMember("e1", "m1");
    expect(apiMock.delete).toHaveBeenCalledWith("/enterprises/e1/org/members/m1");
  });

  it("importMembers 以 FormData 调用 POST /org/members/import 并解包结果", async () => {
    const resultData = { imported: 1, skipped: 0, errors: [] };
    apiMock.post.mockResolvedValue(wrap(resultData));
    const file = new File(["x"], "members.xlsx");
    const result = await importMembers("e1", file);
    expect(apiMock.post).toHaveBeenCalledWith(
      "/enterprises/e1/org/members/import",
      expect.any(FormData),
    );
    const fd = apiMock.post.mock.calls[0][1] as FormData;
    expect(fd.get("file")).toBe(file);
    expect(result).toEqual(resultData);
  });

  it("suggestOrgTree 调用 POST /org/ai-suggest 并解包 data", async () => {
    const suggestion: OrgTreeSuggestion = { available: true, nodes: [NODE] };
    apiMock.post.mockResolvedValue(wrap(suggestion));
    const result = await suggestOrgTree("e1");
    expect(apiMock.post).toHaveBeenCalledWith("/enterprises/e1/org/ai-suggest", {
      extra_requirements: "",
    });
    expect(result).toEqual(suggestion);
  });

  it("suggestOrgTree 透传补充要求", async () => {
    const suggestion: OrgTreeSuggestion = { available: true, nodes: [NODE] };
    apiMock.post.mockResolvedValue(wrap(suggestion));
    const result = await suggestOrgTree("e1", "补充：有 3 个车间");
    expect(apiMock.post).toHaveBeenCalledWith("/enterprises/e1/org/ai-suggest", {
      extra_requirements: "补充：有 3 个车间",
    });
    expect(result).toEqual(suggestion);
  });

  it("downloadMemberTemplate 以 blob responseType 请求模板并返回响应体", async () => {
    const response = { data: new Blob(["xlsx"]) };
    apiMock.get.mockResolvedValue(response);
    const result = await downloadMemberTemplate("e1");
    expect(apiMock.get).toHaveBeenCalledWith("/enterprises/e1/org/members/template", {
      responseType: "blob",
    });
    expect(result).toBe(response);
  });
});
