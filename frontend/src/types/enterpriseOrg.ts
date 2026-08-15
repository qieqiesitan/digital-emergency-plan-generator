// 企业组织与成员管理类型（对应 backend/app/schemas/enterprise_org.py）

export type OrgNodeType = "dept" | "team" | "position";

/** 组织树节点成员（org_structure 内联结构，向后兼容旧消费者）。 */
export interface OrgNodeMember {
  name: string;
  user_id?: string | null;
  position?: string | null;
}

/** 组织树节点：部门 dept → 班组 team → 岗位 position。 */
export interface OrgNode {
  id: string;
  type: OrgNodeType;
  name: string;
  parent_id?: string | null;
  members: OrgNodeMember[];
}

/** 企业成员（enterprise_members 表）。 */
export interface EnterpriseMember {
  id: string;
  enterprise_id: string;
  user_id: string;
  email: string | null;
  name: string | null;
  org_node_id: string | null;
  position: string | null;
  role: string;
  enabled: boolean;
}

/** Excel 导入结果汇总。 */
export interface ImportResult {
  imported: number;
  skipped: number;
  errors: Array<{ row: number; reason: string }>;
}

/** 按邮箱搜索到的可绑定已有账号。 */
export interface BindableUser {
  id: string;
  email: string;
  name: string;
}

/** AI 建树建议结果（available=false 时降级）。 */
export interface OrgTreeSuggestion {
  available: boolean;
  nodes?: OrgNode[];
  note?: string;
}
