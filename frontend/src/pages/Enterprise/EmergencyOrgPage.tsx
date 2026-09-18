import { useCallback, useMemo, useState } from "react";
import {
  App as AntApp,
  Button,
  Empty,
  Form,
  Input,
  Modal,
  Select,
  Space,
  Spin,
  Tag,
  Tree,
} from "antd";
import type { DataNode } from "antd/es/tree";
import {
  ApartmentOutlined,
  DeleteOutlined,
  EditOutlined,
  SaveOutlined,
  ThunderboltOutlined,
} from "@ant-design/icons";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useParams } from "react-router-dom";
import { PageHeader } from "@/components/common/PageHeader";
import {
  getEmergencyOrg,
  saveEmergencyOrg,
} from "@/services/emergencyOrgService";
import { listAvailableMembers } from "@/services/enterpriseOrgService";
import { buildPresetUnits, mergeEmergencyUnits } from "@/utils/emergencyOrgPreset";
import type { EmergencyUnit } from "@/types/emergencyOrg";

interface EditState {
  open: boolean;
  mode: "add" | "rename";
  parentId?: string | null;
  unit?: EmergencyUnit;
}

function buildTreeData(
  units: EmergencyUnit[],
  onAddChild: (u: EmergencyUnit) => void,
  onRename: (u: EmergencyUnit) => void,
  onDelete: (u: EmergencyUnit) => void,
): DataNode[] {
  const byParent = new Map<string | null, EmergencyUnit[]>();
  for (const u of units) {
    const key = u.parent_id ?? null;
    byParent.set(key, [...(byParent.get(key) ?? []), u]);
  }
  const toData = (list: EmergencyUnit[] | undefined): DataNode[] =>
    (list ?? []).map(u => ({
      key: u.id ?? u.name,
      title: (
        <Space size={4}>
          <span>{u.name}</span>
          <Tag color="blue">{(u.roles ?? []).length} 角色</Tag>
          <Button size="small" type="text" icon={<ApartmentOutlined />} onClick={() => onAddChild(u)} />
          <Button size="small" type="text" icon={<EditOutlined />} onClick={() => onRename(u)} />
          <Button size="small" type="text" danger icon={<DeleteOutlined />} onClick={() => onDelete(u)} />
        </Space>
      ),
      children: toData(byParent.get(u.id ?? u.name)),
    }));
  return toData(byParent.get(null));
}

/**
 * 应急组织页：维护应急指挥部/应急小组、组内角色与人员指派。
 * 与「组织与人员管理」（公司部门/班组/岗位）是两套独立数据；同一人可担任多个应急角色。
 */
export default function EmergencyOrgPage() {
  const { id: enterpriseId = "" } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { message, modal } = AntApp.useApp();
  const queryClient = useQueryClient();
  const [form] = Form.useForm();
  const [localUnits, setLocalUnits] = useState<EmergencyUnit[] | null>(null);
  const [selectedId, setSelectedId] = useState<string | undefined>();
  const [editState, setEditState] = useState<EditState>({ open: false, mode: "add" });
  const [saving, setSaving] = useState(false);

  const { data: fetched = [], isLoading } = useQuery({
    queryKey: ["emergency-org", enterpriseId],
    queryFn: () => getEmergencyOrg(enterpriseId),
    enabled: !!enterpriseId,
  });
  const { data: available = [] } = useQuery({
    queryKey: ["org-members-available", enterpriseId],
    queryFn: () => listAvailableMembers(enterpriseId),
    enabled: !!enterpriseId,
  });

  const units = localUnits ?? fetched;
  const dirty = localUnits !== null;
  const selected = useMemo(
    () => units.find(u => (u.id ?? u.name) === selectedId),
    [units, selectedId],
  );

  const patchUnit = useCallback(
    (targetId: string | undefined, patch: Partial<EmergencyUnit>) => {
      setLocalUnits(prev => {
        const base = prev ?? fetched;
        return base.map(u => ((u.id ?? u.name) === targetId ? { ...u, ...patch } : u));
      });
    },
    [fetched],
  );

  const patchRoleMembers = useCallback(
    (unitId: string | undefined, roleIndex: number, memberIds: string[]) => {
      setLocalUnits(prev => {
        const base = prev ?? fetched;
        return base.map(u =>
          (u.id ?? u.name) === unitId
            ? {
                ...u,
                roles: (u.roles ?? []).map((r, i) =>
                  i === roleIndex ? { ...r, member_ids: memberIds } : r,
                ),
              }
            : u,
        );
      });
    },
    [fetched],
  );

  const applyPreset = useCallback(() => {
    modal.confirm({
      title: "应用预置应急组织？",
      content:
        "将「应急组织机构 → 六个应急小组 → 组内角色」合并到当前应急组织：只补齐缺失的组与角色，已有指派保留。",
      okText: "应用",
      onOk: () => {
        setLocalUnits(mergeEmergencyUnits(units, buildPresetUnits()));
        message.info("已合并预置应急组织，请核对后点击「保存」");
      },
    });
  }, [message, modal, units]);

  const handleSave = useCallback(async () => {
    const payload = units.map((u, ui) => ({
      ...u,
      sort_order: u.sort_order ?? ui,
      roles: (u.roles ?? []).map((r, ri) => ({ ...r, sort_order: r.sort_order ?? ri })),
    }));
    setSaving(true);
    try {
      await saveEmergencyOrg(enterpriseId, payload, { skipGlobalError: true });
      setLocalUnits(null);
      message.success("应急组织已保存");
      queryClient.invalidateQueries({ queryKey: ["emergency-org", enterpriseId] });
      queryClient.invalidateQueries({ queryKey: ["completion", enterpriseId] });
    } catch (e) {
      message.error(`保存失败：${e instanceof Error ? e.message : "未知错误"}`);
    } finally {
      setSaving(false);
    }
  }, [enterpriseId, message, queryClient, units]);

  const openAdd = useCallback(
    (parentId: string | null) => {
      form.resetFields();
      setEditState({ open: true, mode: "add", parentId });
    },
    [form],
  );

  const openRename = useCallback(
    (unit: EmergencyUnit) => {
      form.setFieldsValue({ name: unit.name });
      setEditState({ open: true, mode: "rename", unit });
    },
    [form],
  );

  const submitEdit = useCallback(() => {
    void form.validateFields().then(values => {
      const name = String(values.name ?? "").trim();
      if (!name) {
        message.error("名称不能为空");
        return;
      }
      setLocalUnits(prev => {
        const base = prev ?? fetched;
        if (editState.mode === "add") {
          return [
            ...base,
            { id: `unit-${Date.now()}`, parent_id: editState.parentId ?? null, name, duties: "", roles: [] },
          ];
        }
        const targetId = editState.unit?.id ?? editState.unit?.name;
        return base.map(u => ((u.id ?? u.name) === targetId ? { ...u, name } : u));
      });
      setEditState({ open: false, mode: "add" });
      form.resetFields();
    });
  }, [editState, fetched, form, message]);

  const confirmDelete = useCallback(
    (unit: EmergencyUnit) => {
      const rootId = unit.id ?? unit.name;
      const doomed = new Set<string>([rootId]);
      let grew = true;
      while (grew) {
        grew = false;
        for (const u of units) {
          const uid = u.id ?? u.name;
          if (u.parent_id && doomed.has(u.parent_id) && !doomed.has(uid)) {
            doomed.add(uid);
            grew = true;
          }
        }
      }
      modal.confirm({
        title: `确认删除「${unit.name}」及其下级？`,
        content: "将同时移除该组下的角色与人员指派。",
        okText: "删除",
        okButtonProps: { danger: true },
        onOk: () => {
          setLocalUnits(prev => (prev ?? fetched).filter(u => !doomed.has(u.id ?? u.name)));
          setSelectedId(undefined);
        },
      });
    },
    [fetched, modal, units],
  );

  const memberOptions = useMemo(
    () =>
      available.map(m => ({
        value: m.id,
        label: `${m.name}${m.position ? `（${m.position}）` : ""}${m.org_path ? ` - ${m.org_path}` : ""}`,
      })),
    [available],
  );

  return (
    <div>
      <PageHeader
        title="应急组织"
        subtitle="维护应急指挥部与各应急小组、组内角色及人员指派；同一人可担任多个应急角色"
        onBack={() => navigate(`/enterprises/${enterpriseId}`)}
        extra={
          <Space wrap>
            <Button icon={<ThunderboltOutlined />} type="primary" ghost onClick={applyPreset}>
              应用预置应急组织
            </Button>
            <Button
              icon={<SaveOutlined />}
              type="primary"
              disabled={!dirty}
              loading={saving}
              onClick={handleSave}
            >
              保存
            </Button>
          </Space>
        }
      />
      <div style={{ display: "flex", gap: 16, alignItems: "flex-start" }}>
        {/* 左：应急组织树 */}
        <div
          style={{
            flex: 1,
            minWidth: 340,
            background: "#fff",
            borderRadius: 8,
            padding: 12,
            boxShadow: "0 2px 8px rgba(0,0,0,.08)",
          }}
        >
          <Space style={{ marginBottom: 12 }} wrap>
            <Button icon={<ApartmentOutlined />} onClick={() => openAdd(null)}>
              添加顶层单元
            </Button>
            {dirty && <Tag color="orange">有未保存的修改</Tag>}
          </Space>
          {isLoading ? (
            <Spin />
          ) : units.length === 0 ? (
            <Empty description="暂无应急组织，可点击「应用预置应急组织」或手动添加" />
          ) : (
            <Tree
              key={units.map(u => u.id ?? u.name).join(",")}
              treeData={buildTreeData(units, u => openAdd(u.id ?? null), openRename, confirmDelete)}
              defaultExpandAll
              selectedKeys={selectedId ? [selectedId] : []}
              onSelect={keys => setSelectedId((keys[0] as string) ?? undefined)}
            />
          )}
        </div>

        {/* 右：选中单元的角色与人员指派 */}
        <div
          style={{
            flex: 2,
            background: "#fff",
            borderRadius: 8,
            padding: 12,
            boxShadow: "0 2px 8px rgba(0,0,0,.08)",
          }}
        >
          {!selected ? (
            <Empty description="请选择左侧单元查看角色与人员指派" />
          ) : (
            <Form layout="vertical">
              <Form.Item label={`单元职责（${selected.name}）`} style={{ marginBottom: 12 }}>
                <Input.TextArea
                  rows={2}
                  value={selected.duties ?? ""}
                  placeholder="例如：统一指挥现场应急处置"
                  onChange={e => patchUnit(selected.id ?? selected.name, { duties: e.target.value })}
                />
              </Form.Item>
              {(selected.roles ?? []).length === 0 ? (
                <Empty description="该单元暂无角色" />
              ) : (
                (selected.roles ?? []).map((role, ri) => (
                  <Form.Item
                    key={`${role.name}-${ri}`}
                    label={role.is_required ? `${role.name}（必填）` : role.name}
                  >
                    <Select
                      mode="multiple"
                      allowClear
                      placeholder="从企业成员中选择"
                      value={role.member_ids ?? []}
                      options={memberOptions}
                      onChange={values =>
                        patchRoleMembers(selected.id ?? selected.name, ri, values)
                      }
                    />
                  </Form.Item>
                ))
              )}
            </Form>
          )}
        </div>
      </div>

      <Modal
        title={editState.mode === "add" ? "添加应急小组/单元" : "重命名单元"}
        open={editState.open}
        onCancel={() => setEditState({ open: false, mode: "add" })}
        onOk={submitEdit}
        destroyOnHidden
      >
        <Form form={form} layout="vertical" autoComplete="off">
          <Form.Item
            name="name"
            label="名称"
            rules={[{ required: true, whitespace: true, message: "请输入名称" }]}
          >
            <Input placeholder="例如：应急指挥部 / 抢险救灾组" maxLength={50} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
