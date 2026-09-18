import { useMemo, useState } from "react";
import { Button, Input, Space, Table, message } from "antd";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import { getEmergencyOrg, saveEmergencyOrg } from "@/services/emergencyOrgService";
import { listMembers } from "@/services/enterpriseOrgService";
import { mergeEmergencyUnits } from "@/utils/emergencyOrgPreset";
import api from "@/services/api";
import type { EnterpriseMember } from "@/types/enterpriseOrg";
import type { EmergencyUnit } from "@/types/emergencyOrg";
import type { OrgGroup, OrgMember } from "@/types/enterprise";
import ImportDrawer from "./ImportDrawer";
import type { CandidateItem, ImportResult } from "@/types/onboarding";

interface Props {
  enterpriseId: string;
  onDone: () => void;
  onPrev: () => void;
  imported?: CandidateItem[];
  onAddImported?: (stepKey: string, items: CandidateItem[]) => void;
  onRemoveImported?: (stepKey: string, itemKey: string) => void;
}

// 后端候选额外返回组级职责描述，前端类型未声明该字段
type OrgCandidate = OrgGroup & { responsibilities?: string; source?: string; _key: string };

function toOrgCandidates(raws: CandidateItem[], fallbackSource: string): CandidateItem[] {
  const ts = Date.now();
  return raws.map((raw, i) => {
    const g = raw as unknown as OrgCandidate;
    return {
      ...g,
      group_key: String(raw.group_key || raw.group_name || `imp-org-${ts}-${i}`),
      group_name: String(raw.group_name || "导入组织"),
      members: Array.isArray(raw.members) ? (raw.members as OrgMember[]) : [],
      responsibilities: raw.responsibilities ? String(raw.responsibilities) : undefined,
      source: raw.source ? String(raw.source) : fallbackSource || undefined,
      _key: String(raw._key || `imp-org-${ts}-${i}`),
    };
  });
}

function normalizeMembers(members: OrgMember[] | undefined): OrgMember[] {
  return (members || []).map(m => ({
    ...m,
    name: m.name || "",
    phone: m.phone || "",
  }));
}

/** 请求错误：优先透出后端 detail（如 504「AI 响应超时」），其次 e.message，最后兜底文案。 */
function errorDetail(e: unknown, fallback: string): string {
  if (axios.isAxiosError(e) && e.response?.data?.detail) {
    return e.response.data.detail;
  }
  return e instanceof Error && e.message ? e.message : fallback;
}

/** 已采纳的应急组织 → 展示用分组（每组展示 角色/姓名/公司职位/电话）。 */
function unitsToCandidates(units: EmergencyUnit[]): OrgCandidate[] {
  return units
    .filter(u => u.parent_id)
    .map(u => ({
      group_key: u.id ?? u.name,
      group_name: u.name,
      responsibilities: u.duties ?? "",
      members: (u.roles ?? []).flatMap(role =>
        (role.members ?? []).map(m => ({
          role: role.name,
          name: m.name ?? "",
          position: m.position ?? "",
          phone: m.phone ?? "",
          responsibilities: role.duties ?? "",
        })),
      ),
      _key: u.id ?? u.name,
    }));
}

/** 候选分组 → 应急组织单元：角色取自候选成员的 role 文案，人员按姓名匹配企业成员档案。 */
function candidatesToUnits(groups: OrgCandidate[], members: EnterpriseMember[]): EmergencyUnit[] {
  const rootId = "onboarding-emergency-root";
  const memberIdByName = new Map<string, string>();
  members.forEach(m => {
    if (m.name) memberIdByName.set(m.name, m.id);
  });
  return [
    { id: rootId, parent_id: null, name: "应急组织机构", duties: "", roles: [] },
    ...groups.map((g, gi) => {
      const roleNames = Array.from(
        new Set((g.members ?? []).map(m => String(m.role || "").trim()).filter(Boolean)),
      );
      const effective = roleNames.length ? roleNames : ["组长", "组员"];
      return {
        id: `onboarding-${g.group_key || gi}`,
        parent_id: rootId,
        name: g.group_name,
        duties: g.responsibilities ?? "",
        sort_order: gi,
        roles: effective.map((roleName, ri) => ({
          id: `onboarding-${g.group_key || gi}-role-${ri}`,
          name: roleName,
          duties: "",
          sort_order: ri,
          is_required: roleName === "总指挥" || roleName === "副总指挥",
          member_ids: (g.members ?? [])
            .filter(m => String(m.role || "").trim() === roleName && m.name)
            .map(m => memberIdByName.get(String(m.name)))
            .filter((id): id is string => Boolean(id)),
        })),
      };
    }),
  ];
}

/**
 * 应急组织采纳步骤（Onboarding）。
 * 公司部门/班组/岗位在「组织与人员管理」页维护，本步骤只管应急组织。
 */
export default function StepOrg({
  enterpriseId,
  onDone,
  onPrev,
  imported,
  onAddImported,
  onRemoveImported,
}: Props) {
  const queryClient = useQueryClient();
  const [overview, setOverview] = useState("");
  const [candidates, setCandidates] = useState<OrgCandidate[]>([]);
  const [generating, setGenerating] = useState(false);
  const [importOpen, setImportOpen] = useState(false);
  const [memberEdits, setMemberEdits] = useState<Record<string, OrgMember[]>>({});

  const { data: acceptedUnits = [], isLoading } = useQuery({
    queryKey: ["emergency-org", enterpriseId],
    queryFn: () => getEmergencyOrg(enterpriseId),
    enabled: !!enterpriseId,
  });
  const { data: members = [] } = useQuery({
    queryKey: ["org-members", enterpriseId],
    queryFn: () => listMembers(enterpriseId),
    enabled: !!enterpriseId,
  });

  const accepted = useMemo(() => unitsToCandidates(acceptedUnits), [acceptedUnits]);
  const importedGroups = useMemo(
    () => toOrgCandidates(imported || [], "") as unknown as OrgCandidate[],
    [imported],
  );
  const allCandidates = useMemo(
    () => [...candidates, ...importedGroups],
    [candidates, importedGroups],
  );

  const getEditedMembers = (g: OrgCandidate): OrgMember[] =>
    memberEdits[g.group_key] ?? normalizeMembers(g.members);

  const updateMember = (g: OrgCandidate, index: number, patch: Partial<OrgMember>) => {
    setMemberEdits(prev => {
      const current = prev[g.group_key] ?? normalizeMembers(g.members);
      const next = current.map((m, i) => (i === index ? { ...m, ...patch } : m));
      return { ...prev, [g.group_key]: next };
    });
  };

  const handleImported = (results: ImportResult[]) => {
    const result = results[0];
    if (!result) return;
    onAddImported?.("org", toOrgCandidates(result.candidates || [], result.source));
  };

  const generate = async () => {
    setGenerating(true);
    try {
      const r = await api.post(
        "/onboarding/candidates",
        { enterprise_id: enterpriseId, module: "org", overview },
        { skipGlobalError: true },
      );
      const ts = Date.now();
      setCandidates(
        ((r.data.data.items || []) as OrgCandidate[]).map((g, i) => {
          const key = String(g.group_key || g.group_name || `imp-org-${ts}-${i}`);
          return {
            ...g,
            group_key: key,
            group_name: String(g.group_name || "AI 候选组"),
            members: Array.isArray(g.members) ? g.members : [],
            responsibilities: g.responsibilities ? String(g.responsibilities) : undefined,
            _key: String(g._key || key),
          };
        }),
      );
    } catch (e) {
      message.error(errorDetail(e, "生成失败"));
    } finally {
      setGenerating(false);
    }
  };

  const saveMut = useMutation({
    mutationFn: (units: EmergencyUnit[]) =>
      saveEmergencyOrg(enterpriseId, units, { skipGlobalError: true }),
    onSuccess: () => {
      message.success("应急组织已保存");
      queryClient.invalidateQueries({ queryKey: ["emergency-org", enterpriseId] });
      queryClient.invalidateQueries({ queryKey: ["completion", enterpriseId] });
    },
    onError: e => message.error(errorDetail(e, "保存失败，请重试")),
  });

  const buildUnits = (groups: OrgCandidate[]) =>
    mergeEmergencyUnits(acceptedUnits, candidatesToUnits(groups, members));

  const adoptGroup = async (g: OrgCandidate, edited: OrgMember[]) => {
    if (isLoading || saveMut.isPending) return;
    try {
      await saveMut.mutateAsync(buildUnits([{ ...g, members: edited }]));
      if (importedGroups.some(x => x._key === g._key)) onRemoveImported?.("org", g._key);
      else setCandidates(prev => prev.filter(x => x._key !== g._key));
      setMemberEdits(prev => {
        const next = { ...prev };
        delete next[g.group_key];
        return next;
      });
    } catch {
      // onError 已提示
    }
  };

  const adoptAll = async () => {
    if (isLoading || saveMut.isPending) return;
    const groups = allCandidates.map(g => ({ ...g, members: getEditedMembers(g) }));
    try {
      await saveMut.mutateAsync(buildUnits(groups));
      setCandidates([]);
      allCandidates.forEach(g => onRemoveImported?.("org", g._key));
      setMemberEdits({});
    } catch {
      // onError 已提示
    }
  };

  // 取消采纳：清空应急组织并移回候选区，可重新编辑再采纳
  const unacceptAll = async () => {
    if (accepted.length === 0 || isLoading || saveMut.isPending) return;
    try {
      await saveMut.mutateAsync([]);
      setCandidates(prev => [...prev, ...accepted]);
      message.success(`已全部取消采纳：${accepted.length} 组`);
    } catch {
      // onError 已提示
    }
  };

  return (
    <div style={{ maxWidth: 760 }}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
        }}
      >
        <div>
          <h3>应急组织</h3>
          <p style={{ color: "#666", fontSize: 13 }}>
            突发事件谁来指挥、谁负责什么——预案「应急组织机构及职责」章节直接用它。
            公司部门/班组/岗位请在「组织与人员管理」页维护
          </p>
        </div>
        <Space>
          <Button onClick={() => setImportOpen(true)}>📄 导入现有数据</Button>
        </Space>
      </div>
      <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
        <Input.TextArea
          rows={2}
          value={overview}
          onChange={e => setOverview(e.target.value)}
          placeholder="企业概况（可留空，AI 按行业/规模自动生成）"
        />
        <Button type="primary" loading={generating} onClick={generate}>
          {generating ? "AI 生成中，通常需要 1-2 分钟，请耐心等待" : "AI 生成候选"}
        </Button>
      </div>
      {accepted.length > 0 && (
        <div style={{ marginBottom: 12 }}>
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              marginBottom: 6,
            }}
          >
            <div style={{ fontSize: 13, fontWeight: 600, color: "#52c41a" }}>
              ✓ 已采纳（{accepted.length} 组，已保存，AI 不会改动）
            </div>
            <Button
              size="small"
              loading={saveMut.isPending}
              disabled={isLoading}
              onClick={unacceptAll}
            >
              全部取消采纳
            </Button>
          </div>
          {accepted.map(g => (
            <div
              key={g.group_key || g.group_name}
              style={{
                border: "1px solid #d9f7be",
                background: "#f6ffed",
                borderRadius: 8,
                padding: 10,
                marginBottom: 8,
              }}
            >
              <b>{g.group_name}</b>
              <Table
                size="small"
                pagination={false}
                rowKey={(_, i) => `a-${i}`}
                dataSource={g.members || []}
                columns={[
                  { title: "应急角色", dataIndex: "role" },
                  {
                    title: "姓名",
                    dataIndex: "name",
                    render: (v: string) =>
                      v || <span style={{ color: "#fa8c16" }}>待填</span>,
                  },
                  { title: "公司职位", dataIndex: "position", render: (v: string) => v || "-" },
                  {
                    title: "电话",
                    dataIndex: "phone",
                    render: (v: string) =>
                      v || <span style={{ color: "#fa8c16" }}>待填</span>,
                  },
                ]}
              />
            </div>
          ))}
          <p style={{ color: "#8c8c8c", fontSize: 12 }}>
            人员指派请在「应急组织」页从企业成员中选择（同一人可担任多个应急角色）
          </p>
        </div>
      )}
      {allCandidates.length > 0 && (
        <>
          {allCandidates.map(g => {
            const editedMembers = getEditedMembers(g);
            return (
              <div
                key={g.group_key}
                style={{
                  border: "1px solid #1677ff",
                  borderRadius: 8,
                  padding: 10,
                  marginBottom: 8,
                  background: "#f0f7ff",
                }}
              >
                <b>{g.group_name}</b>
                {g.source && (
                  <div style={{ color: "#999", fontSize: 12 }}>来源：{g.source}</div>
                )}
                <div style={{ color: "#666", fontSize: 12, margin: "4px 0" }}>
                  {g.responsibilities}
                </div>
                <Table
                  size="small"
                  pagination={false}
                  rowKey={(_, i) => `m-${i}`}
                  dataSource={editedMembers}
                  columns={[
                    { title: "应急角色", dataIndex: "role" },
                    {
                      title: "姓名",
                      dataIndex: "name",
                      render: (value: string, _record: OrgMember, index: number) => (
                        <Input
                          size="small"
                          value={value}
                          placeholder="请输入姓名"
                          onChange={e => updateMember(g, index, { name: e.target.value })}
                        />
                      ),
                    },
                    {
                      title: "公司职位",
                      dataIndex: "position",
                      render: (v: string) => v || "-",
                    },
                    {
                      title: "电话",
                      dataIndex: "phone",
                      render: (value: string, _record: OrgMember, index: number) => (
                        <Input
                          size="small"
                          value={value}
                          placeholder="请输入电话"
                          onChange={e => updateMember(g, index, { phone: e.target.value })}
                        />
                      ),
                    },
                  ]}
                />
                <div style={{ marginTop: 6 }}>
                  <Button
                    size="small"
                    type="primary"
                    loading={saveMut.isPending}
                    disabled={isLoading}
                    onClick={() => adoptGroup(g, editedMembers)}
                  >
                    采纳本组
                  </Button>
                </div>
              </div>
            );
          })}
          <Button
            type="primary"
            onClick={adoptAll}
            disabled={isLoading}
            loading={saveMut.isPending}
            style={{ marginBottom: 12 }}
          >
            全部采纳
          </Button>
        </>
      )}
      <div style={{ marginTop: 20, display: "flex", justifyContent: "space-between" }}>
        <Button onClick={onPrev}>上一步</Button>
        <Button type="primary" onClick={onDone}>
          标记完成，下一步 →
        </Button>
      </div>
      <ImportDrawer
        enterpriseId={enterpriseId}
        open={importOpen}
        mode="single"
        module="org_structure"
        onClose={() => setImportOpen(false)}
        onImported={handleImported}
      />
    </div>
  );
}
