import api from "./api";
import type { ApiResponse } from "@/types/common";
import type {
  BindableUser,
  EnterpriseMember,
  ImportResult,
  OrgNode,
  OrgTreeSuggestion,
} from "@/types/enterpriseOrg";

type OrgMemberRole = "enterprise_admin" | "team_leader" | "member";

/** 新增成员载荷（对应后端 MemberCreate）。 */
interface MemberCreatePayload {
  user_id: string;
  org_node_id?: string | null;
  position?: string | null;
  role?: OrgMemberRole;
}

/** 编辑成员载荷（对应后端 MemberUpdate；role/enabled 显式 null 由后端 422 拦截）。 */
interface MemberUpdatePayload {
  org_node_id?: string | null;
  position?: string | null;
  role?: OrgMemberRole | null;
  enabled?: boolean | null;
}

/** 获取组织树节点。 */
export const getOrgNodes = (enterpriseId: string) =>
  api
    .get<ApiResponse<OrgNode[]>>(`/enterprises/${enterpriseId}/org/nodes`)
    .then(r => r.data.data);

/** 保存组织树节点（整树覆盖）。 */
export const saveOrgNodes = (enterpriseId: string, nodes: OrgNode[]) =>
  api
    .put<ApiResponse<OrgNode[]>>(`/enterprises/${enterpriseId}/org/nodes`, { nodes })
    .then(r => r.data.data);

/** 成员列表。 */
export const listMembers = (enterpriseId: string) =>
  api
    .get<ApiResponse<EnterpriseMember[]>>(`/enterprises/${enterpriseId}/org/members`)
    .then(r => r.data.data);

/** 按邮箱搜索可绑定为成员的已有账号。 */
export const searchBindableUsers = (enterpriseId: string, email: string) =>
  api
    .get<ApiResponse<BindableUser[]>>(`/enterprises/${enterpriseId}/org/members/search`, {
      params: { email },
    })
    .then(r => r.data.data);

/** 添加成员（绑定已有账号）。 */
export const createMember = (enterpriseId: string, payload: MemberCreatePayload) =>
  api
    .post<ApiResponse<EnterpriseMember>>(`/enterprises/${enterpriseId}/org/members`, payload)
    .then(r => r.data.data);

/** 编辑成员（岗位/角色/组织节点/启用状态）。 */
export const updateMember = (
  enterpriseId: string,
  memberId: string,
  patch: MemberUpdatePayload,
) =>
  api
    .put<ApiResponse<EnterpriseMember>>(`/enterprises/${enterpriseId}/org/members/${memberId}`, patch)
    .then(r => r.data.data);

/** 删除成员。 */
export const deleteMember = (enterpriseId: string, memberId: string) =>
  api
    .delete<ApiResponse<null>>(`/enterprises/${enterpriseId}/org/members/${memberId}`)
    .then(r => r.data.data);

/** Excel 批量导入成员。 */
export const importMembers = (enterpriseId: string, file: File) => {
  const fd = new FormData();
  fd.append("file", file);
  return api
    .post<ApiResponse<ImportResult>>(`/enterprises/${enterpriseId}/org/members/import`, fd)
    .then(r => r.data.data);
};

/** AI 建议组织树（available=false 时降级，不阻塞手动维护）。 */
export const suggestOrgTree = (enterpriseId: string) =>
  api
    .post<ApiResponse<OrgTreeSuggestion>>(`/enterprises/${enterpriseId}/org/ai-suggest`)
    .then(r => r.data.data);

/** 下载 Excel 成员导入模板（返回 blob 响应，DOM 下载由页面触发，与 exportControlList 惯例一致）。 */
export const downloadMemberTemplate = (enterpriseId: string) =>
  api.get(`/enterprises/${enterpriseId}/org/members/template`, {
    responseType: "blob",
  });
