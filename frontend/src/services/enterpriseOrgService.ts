import api from "./api";
import type {
  BindableUser,
  EnterpriseMember,
  ImportResult,
  OrgNode,
  OrgTreeSuggestion,
} from "@/types/enterpriseOrg";

/** 获取组织树节点。 */
export const getOrgNodes = (enterpriseId: string) =>
  api
    .get(`/enterprises/${enterpriseId}/org/nodes`)
    .then(r => r.data.data as OrgNode[]);

/** 保存组织树节点（整树覆盖）。 */
export const saveOrgNodes = (enterpriseId: string, nodes: OrgNode[]) =>
  api
    .put(`/enterprises/${enterpriseId}/org/nodes`, { nodes })
    .then(r => r.data.data as OrgNode[]);

/** 成员列表。 */
export const listMembers = (enterpriseId: string) =>
  api
    .get(`/enterprises/${enterpriseId}/org/members`)
    .then(r => r.data.data as EnterpriseMember[]);

/** 按邮箱搜索可绑定为成员的已有账号。 */
export const searchBindableUsers = (enterpriseId: string, email: string) =>
  api
    .get(`/enterprises/${enterpriseId}/org/members/search`, {
      params: { email },
    })
    .then(r => r.data.data as BindableUser[]);

/** 添加成员（绑定已有账号）。 */
export const createMember = (enterpriseId: string, payload: object) =>
  api
    .post(`/enterprises/${enterpriseId}/org/members`, payload)
    .then(r => r.data.data as EnterpriseMember);

/** 编辑成员（岗位/角色/组织节点/启用状态）。 */
export const updateMember = (
  enterpriseId: string,
  memberId: string,
  patch: object,
) =>
  api
    .put(`/enterprises/${enterpriseId}/org/members/${memberId}`, patch)
    .then(r => r.data.data as EnterpriseMember);

/** 删除成员。 */
export const deleteMember = (enterpriseId: string, memberId: string) =>
  api
    .delete(`/enterprises/${enterpriseId}/org/members/${memberId}`)
    .then(r => r.data.data);

/** Excel 批量导入成员。 */
export const importMembers = (enterpriseId: string, file: File) => {
  const fd = new FormData();
  fd.append("file", file);
  return api
    .post(`/enterprises/${enterpriseId}/org/members/import`, fd)
    .then(r => r.data.data as ImportResult);
};

/** AI 建议组织树（available=false 时降级，不阻塞手动维护）。 */
export const suggestOrgTree = (enterpriseId: string) =>
  api
    .post(`/enterprises/${enterpriseId}/org/ai-suggest`)
    .then(r => r.data.data as OrgTreeSuggestion);

/** 下载 Excel 成员导入模板（返回 blob 响应，DOM 下载由页面触发，与 exportControlList 惯例一致）。 */
export const downloadMemberTemplate = (enterpriseId: string) =>
  api.get(`/enterprises/${enterpriseId}/org/members/template`, {
    responseType: "blob",
  });
