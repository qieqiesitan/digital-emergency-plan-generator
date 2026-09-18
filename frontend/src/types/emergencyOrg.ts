// 应急组织类型（对应 backend/app/schemas/emergency_org.py）

/** 应急角色下的人员简要信息（后端 load_emergency_org 展开返回）。 */
export interface EmergencyMemberBrief {
  id: string;
  name?: string | null;
  phone?: string | null;
  position?: string | null;
  email?: string | null;
  org_node_id?: string | null;
}

/** 组内应急角色（总指挥/副总指挥/组长/组员…）。 */
export interface EmergencyRole {
  id?: string;
  name: string;
  duties?: string | null;
  sort_order?: number;
  /** 质检必填角色（总指挥/副总指挥），企业可自定义角色名后仍能判定。 */
  is_required?: boolean;
  member_ids: string[];
  members?: EmergencyMemberBrief[];
}

/** 应急组织单元：应急指挥部 / 各应急小组，靠 parent_id 组树。 */
export interface EmergencyUnit {
  id?: string;
  parent_id?: string | null;
  name: string;
  duties?: string | null;
  sort_order?: number;
  roles: EmergencyRole[];
}

/** 可指派成员（复用 GET /org/members/available）。 */
export interface AssignableMember {
  id: string;
  name: string;
  email: string | null;
  role: string;
  position: string | null;
  org_path: string;
}
