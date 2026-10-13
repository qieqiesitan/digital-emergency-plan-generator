import { useState, useCallback, useMemo, useEffect } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { App as AntApp, Alert, Button, Dropdown, Spin, Space, Tag } from "antd";
import { PlusOutlined, ThunderboltOutlined, BarChartOutlined, SettingOutlined, EditOutlined, ApartmentOutlined, UnorderedListOutlined, DownOutlined } from "@ant-design/icons";
import AppEmpty from "@/components/common/AppEmpty";
import AppIcon from "@/components/common/AppIcon";
import { useQuery } from "@tanstack/react-query";
import { getFullHierarchy, createZone, updateZone, deleteZone, createObject, updateObject, deleteObject, createUnit, updateUnit, deleteUnit, createEvent, updateEvent, deleteEvent, createMeasure, updateMeasure, deleteMeasure, getMigrationPreview } from "@/services/riskManagementService";
import { deleteEnterpriseFloor, listEnterpriseFloors } from "@/services/riskMappingWorkbenchService";
import RiskHierarchyTree, { type TreeNodeMeta } from "@/components/enterprise/RiskHierarchyTree";
import RiskTreeFourColorMap from "@/components/enterprise/RiskTreeFourColorMap";
import RiskMigrationWizard from "@/components/enterprise/RiskMigrationWizard";
import type { HierarchyZone, HierarchyObject, HierarchyUnit, HierarchyEvent, HierarchyMeasure, CheckItem, RiskZoneFloorPlanPolygon, MethodType, MeasureCategory } from "@/types/riskManagement";
import { buildZonePayload } from "@/utils/zoneSubmit";
 import RiskZoneForm from "@/components/enterprise/RiskZoneForm";
 import RiskObjectForm from "@/components/enterprise/RiskObjectForm";
 import RiskUnitForm from "@/components/enterprise/RiskUnitForm";
import RiskEventForm from "@/components/enterprise/RiskEventForm";
import RiskMeasureForm from "@/components/enterprise/RiskMeasureForm";
import RiskSmartGuideModal from "@/components/enterprise/RiskSmartGuideModal";
import FloorManagementDrawer from "@/components/enterprise/FloorManagementDrawer";
import { MEASURE_CATEGORY_LABELS, RISK_LEVEL_COLORS } from "@/utils/riskMethodEngine";

interface Props {
  enterpriseId: string;
  floorPlanUrl?: string | null;
  embedded?: boolean;
}
 
 type FormType = "zone" | "object" | "unit" | "event" | "measure" | null;
 
interface FormState {
  type: FormType;
  open: boolean;
  id?: string;
  parentId?: string;
  parentType?: string;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any -- 表单组件各自定义未导出的 values 类型，跨表单分发时用 any 保持兼容
  initialValues?: any;
}

interface ZoneFormValues {
  name?: string;
  description?: string;
  floor_plan_polygon?: RiskZoneFloorPlanPolygon | null;
  category?: string;
  location?: string;
  location_x?: number | null;
  location_y?: number | null;
  is_risk_point?: boolean;
  responsible_unit?: string;
  responsible_person?: string;
  contact_phone?: string;
  unit_type?: string;
  accident_type?: string | string[];
  chemical_id?: string | null;
  method_type?: string;
  method_params?: Record<string, number>;
  risk_level?: string | null;
  risk_score?: string | null;
  inherent_risk_level?: string | null;
  inherent_risk_score?: string | null;
  control_level?: string | null;
  measure_category?: string;
  check_items?: CheckItem[];
}

function eventInitialValues(meta: TreeNodeMeta): Record<string, unknown> {
  const rawParams = (meta.method_params ?? {}) as Record<string, unknown>;
  // DIRECT 旧数据可能存等级文案（risk_level），归一化为表单 Select 的数值键
  let methodParams: Record<string, unknown> = rawParams;
  if (meta.method_type === "DIRECT") {
    const levelRaw = rawParams.level ?? rawParams.risk_level;
    const levelNum = typeof levelRaw === "number"
      ? levelRaw
      : typeof levelRaw === "string"
        ? ({ "低": 1, "一般": 2, "较大": 3, "重大": 4 } as Record<string, number>)[levelRaw] ?? 1
        : undefined;
    methodParams = levelNum != null ? { level: levelNum } : rawParams;
  }
  return {
    accident_type: meta.name,
    chemical_id: meta.chemical_id ?? undefined,
    method_type: meta.method_type,
    method_params: methodParams,
    risk_level: meta.risk_level,
    risk_score: meta.risk_score,
    inherent_risk_level: meta.inherent_risk_level,
    inherent_risk_score: meta.inherent_risk_score,
    control_level: meta.control_level,
  };
}
 
export default function RiskManagementTab({ enterpriseId, floorPlanUrl, embedded }: Props) {
  const navigate = useNavigate();
  const { modal, message: antMessage } = AntApp.useApp();
 
   const { data: hierarchy = [], isLoading, refetch } = useQuery({ queryKey: ["risk-hierarchy", enterpriseId], queryFn: () => getFullHierarchy(enterpriseId) });
   const { data: floors = [], refetch: refetchFloors } = useQuery({
     queryKey: ["enterprise-floors", enterpriseId],
     queryFn: () => listEnterpriseFloors(enterpriseId),
   });
 
   const [selectedNode, setSelectedNode] = useState<TreeNodeMeta | null>(null);
   const [mapFloorId, setMapFloorId] = useState<string | null>(null);
   const [form, setForm] = useState<FormState>({ type: null, open: false });
  const [smartGuideOpen, setSmartGuideOpen] = useState(false);
  const [floorDrawerOpen, setFloorDrawerOpen] = useState(false);
  const [migrationOpen, setMigrationOpen] = useState(false);
  const [searchParams] = useSearchParams();
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- 计划指定：侧栏「楼层平面图」跳转 ?floor=1 时打开楼层抽屉，属对外部路由参数变更的同步，项目已存在同类带说明禁用
    if (searchParams.get("floor") === "1") setFloorDrawerOpen(true);
  }, [searchParams]);
  const { data: migrationPreview, refetch: refetchMigrationPreview } = useQuery({
    queryKey: ["risk-migration-preview", enterpriseId],
    queryFn: () => getMigrationPreview(enterpriseId),
    enabled: !!enterpriseId,
  });
  const zones = useMemo(() => hierarchy.map(z => ({ id: z.id, name: z.name })), [hierarchy]);

  const hierarchyMap = useMemo(() => {
    const map: Record<string, {
      zone: HierarchyZone | null;
      object: HierarchyObject | null;
      unit: HierarchyUnit | null;
      event: HierarchyEvent | null;
      measure: HierarchyMeasure | null;
    }> = {};
    for (const z of hierarchy) {
      map[z.id] = { zone: z, object: null, unit: null, event: null, measure: null };
      for (const o of z.objects || []) {
        map[o.id] = { zone: z, object: o, unit: null, event: null, measure: null };
        for (const u of o.units || []) {
          map[u.id] = { zone: z, object: o, unit: u, event: null, measure: null };
          for (const ev of u.events || []) {
            map[ev.id] = { zone: z, object: o, unit: u, event: ev, measure: null };
            for (const m of ev.measures || []) {
              map[m.id] = { zone: z, object: o, unit: u, event: ev, measure: m };
            }
          }
        }
        for (const ev of o.events || []) {
          if (!map[ev.id]) map[ev.id] = { zone: z, object: o, unit: null, event: ev, measure: null };
          for (const m of ev.measures || []) {
            map[m.id] = { zone: z, object: o, unit: null, event: ev, measure: m };
          }
        }
      }
    }
    return map;
  }, [hierarchy]);

  // ── 风险树 ⇄ 四色图 联动 ──
  // 树选中键（受控）：让地图点选分区后能反向选中/展开树节点
  const treeSelectedKey = useMemo(
    () => (selectedNode ? `${selectedNode.type}-${selectedNode.id}` : null),
    [selectedNode],
  );
  // 需要在地图上高亮的分区：分区节点=自身；深层节点=其所属分区；楼层节点=不高亮
  const highlightZoneId = useMemo(() => {
    if (!selectedNode || selectedNode.type === "floor") return null;
    if (selectedNode.type === "zone") return selectedNode.id;
    return hierarchyMap[selectedNode.id]?.zone?.id ?? null;
  }, [selectedNode, hierarchyMap]);
  // 地图楼层跟随所选节点（楼层节点直接切换；分区及深层节点跟随所属分区楼层）
  useEffect(() => {
    if (!selectedNode) return;
    const floorOfNode = selectedNode.type === "floor"
      ? (selectedNode.id !== "unassigned" ? selectedNode.id : null)
      : (hierarchyMap[selectedNode.id]?.zone?.floor_id ?? null);
    // eslint-disable-next-line react-hooks/set-state-in-effect -- 四色图楼层跟随所选节点切换，属对外部选中值变更的同步
    if (floorOfNode) setMapFloorId(floorOfNode);
  }, [selectedNode, hierarchyMap]);
  // 地图点选分区 → 反向选中树节点（树自动展开祖先定位）
  const handleMapZoneClick = useCallback((zoneId: string) => {
    const zone = hierarchy.find((z) => z.id === zoneId);
    if (!zone) return;
    setSelectedNode({
      id: zone.id,
      type: "zone",
      name: zone.name,
      floorId: zone.floor_id,
      floor_plan_polygon: zone.floor_plan_polygon ?? null,
    });
  }, [hierarchy]);

  const confirmDelete = useCallback((meta: TreeNodeMeta) => {
    const typeLabels: Record<TreeNodeMeta["type"], string> = {
      floor: "楼层",
      zone: "分区",
      object: "对象",
      unit: "单元",
      event: "事件",
      measure: "措施",
    };
    const contents: Record<TreeNodeMeta["type"], string> = {
      floor: "将删除该楼层及其下所有分区",
      zone: "将级联删除该分区下所有对象、单元、事件和措施",
      object: "将级联删除该对象下所有单元、事件和措施",
      unit: "将级联删除该单元下所有事件和措施",
      event: "将级联删除该事件下所有措施",
      measure: "仅删除该措施",
    };
    modal.confirm({
      title: `确认删除${typeLabels[meta.type]}「${meta.name}」？`,
      content: contents[meta.type],
      onOk: async () => {
        switch (meta.type) {
          case "floor": {
            const f = floors.find(x => x.id === meta.id);
            const zoneCount = f?.zone_count ?? 0;
            const pointCount = f?.risk_point_count ?? 0;
            await new Promise<void>((resolve) => {
              modal.confirm({
                title: `再次确认删除楼层「${meta.name}」？`,
                content: zoneCount > 0 || pointCount > 0
                  ? `该楼层下有 ${zoneCount} 个分区、${pointCount} 个风险点，删除将一并级联删除其全部对象、单元、事件与管控措施，且无法恢复。`
                  : "删除后无法恢复。",
                okText: "确认删除",
                okButtonProps: { danger: true },
                cancelText: "取消",
                onOk: async () => {
                  await deleteEnterpriseFloor(enterpriseId, meta.id);
                  resolve();
                },
                onCancel: () => resolve(),
              });
            });
            refetchFloors();
            break;
          }
          case "zone": await deleteZone(enterpriseId, meta.id); break;
          case "object": await deleteObject(enterpriseId, meta.id); break;
          case "unit": await deleteUnit(enterpriseId, meta.parentId || "", meta.id); break;
          case "event": await deleteEvent(enterpriseId, meta.id); break;
          case "measure": await deleteMeasure(enterpriseId, meta.parentId || "", meta.id); break;
        }
        refetch();
      },
    });
  }, [enterpriseId, refetch, refetchFloors, floors, modal]);

  // Handle tree node action (add/edit/delete from RiskHierarchyTree)
  const handleTreeAction = useCallback((action: string, meta: TreeNodeMeta) => {
    switch (action) {
      case "add-zone":
        setForm({
          type: "zone",
          open: true,
          parentId: meta.id,
          initialValues: meta.floorId ? { name: "", floor_id: meta.floorId } : undefined,
        });
        break;
      case "add-object":
        setForm({ type: "object", open: true, parentId: meta.id, parentType: "zone", initialValues: { zone_id: meta.id } });
        break;
      case "add-unit":
        setForm({ type: "unit", open: true, parentId: meta.id, parentType: "object" });
        break;
      case "add-event":
        setForm({ type: "event", open: true, parentId: meta.id, parentType: meta.type === "unit" ? "unit" : "object" });
        break;
      case "add-measure":
        setForm({ type: "measure", open: true, parentId: meta.id, parentType: "event" });
        break;
      case "edit":
        setForm({
          type: meta.type as FormType,
          open: true,
          id: meta.id,
          parentId: meta.parentId,
          parentType: meta.parentType,
          initialValues:
            meta.type === "zone" ? { name: meta.name, floor_plan_polygon: meta.floor_plan_polygon ?? undefined, floor_id: meta.floorId ?? undefined }
            : meta.type === "object" ? { name: meta.name, zone_id: meta.parentId }
            : meta.type === "unit" ? { name: meta.name }
            : meta.type === "event" ? eventInitialValues(meta)
            : { description: meta.name },
        });
        break;
      case "delete":
        confirmDelete(meta);
        break;
      case "edit-zone":
      case "edit-object":
      case "edit-unit":
      case "edit-event":
      case "edit-measure":
        setForm({
          type: meta.type as FormType,
          open: true,
          id: meta.id,
          parentId: meta.parentId,
          parentType: meta.parentType,
          initialValues:
            meta.type === "zone" ? { name: meta.name, floor_plan_polygon: meta.floor_plan_polygon ?? undefined, floor_id: meta.floorId ?? undefined }
            : meta.type === "object" ? { name: meta.name, zone_id: meta.parentId }
            : meta.type === "unit" ? { name: meta.name }
            : meta.type === "event" ? eventInitialValues(meta)
            : { description: meta.name },
        });
        break;
      case "delete-zone":
      case "delete-object":
      case "delete-unit":
      case "delete-event":
      case "delete-measure":
        confirmDelete(meta);
        break;
      default:
        antMessage.info(`${action}: ${meta.name}`);
    }
  }, [confirmDelete, antMessage]);
 
   // Handle form submit
  const handleFormSubmit = useCallback(async (values: ZoneFormValues) => {
    try {
      if (form.type === "object" && values.is_risk_point && (!form.parentId || values.location_x == null || values.location_y == null)) {
        antMessage.warning("风险点必须绑定分区并设置平面图坐标");
        return;
      }
      switch (form.type) {
        case "zone": {
          const zonePayload = buildZonePayload(values);
          if (form.id) {
            await updateZone(enterpriseId, form.id, zonePayload, { skipGlobalError: true });
          } else {
            await createZone(enterpriseId, zonePayload, { skipGlobalError: true });
          }
          break;
        }
        case "object": {
          const objectPayload = {
            name: values.name || "",
            category: values.category || "",
            description: values.description || "",
            location: values.location || undefined,
            location_x: values.location_x ?? undefined,
            location_y: values.location_y ?? undefined,
            is_risk_point: values.is_risk_point || false,
            responsible_unit: values.responsible_unit || undefined,
            responsible_person: values.responsible_person || undefined,
            contact_phone: values.contact_phone || undefined,
          };
          if (form.id) {
            await updateObject(enterpriseId, form.id, objectPayload, { skipGlobalError: true });
          } else {
            await createObject(enterpriseId, { ...objectPayload, zone_id: form.parentId }, { skipGlobalError: true });
          }
          break;
        }
        case "unit":
          if (form.id) {
            await updateUnit(enterpriseId, form.parentId || "", form.id, { name: values.name || "", unit_type: values.unit_type || "", description: values.description || "" }, { skipGlobalError: true });
          } else {
          await createUnit(enterpriseId, form.parentId || "", { name: values.name || "", unit_type: values.unit_type || "", description: values.description || "" }, { skipGlobalError: true });
          }
          break;
        case "event": {
          // 表单负责判定「未改动」并省略对应字段；提交层仅携带表单显式提供的字段，
          // 未改动保存时不发送 method_type/method_params/risk_*/inherent_*，避免覆盖已存等级
          const eventPayload = {
            accident_type: Array.isArray(values.accident_type)
              ? values.accident_type.join("、")
              : (values.accident_type || ""),
            description: values.description || "",
            ...(values.method_type ? { method_type: values.method_type as MethodType } : {}),
            ...(values.method_params ? { method_params: values.method_params } : {}),
            // 显式透传：null 表示清空固有/现有等级（序列化保留），undefined 序列化时省略
            risk_level: values.risk_level,
            risk_score: values.risk_score,
            inherent_risk_level: values.inherent_risk_level,
            inherent_risk_score: values.inherent_risk_score,
            control_level: values.control_level ?? null,
            chemical_id: values.chemical_id ?? null,
          };
          if (form.id) {
            await updateEvent(enterpriseId, form.id, eventPayload, { skipGlobalError: true });
          } else {
            await createEvent(enterpriseId, form.parentId || "", { ...eventPayload, ...(form.parentType === "object" ? { object_id: form.parentId } : { unit_id: form.parentId }) }, { skipGlobalError: true });
          }
          break;
        }
        case "measure":
          if (form.id) {
            await updateMeasure(enterpriseId, form.parentId || "", form.id, { measure_category: values.measure_category as MeasureCategory, description: values.description || "", check_items: values.check_items || [] }, { skipGlobalError: true });
          } else {
          await createMeasure(enterpriseId, form.parentId || "", { measure_category: values.measure_category as MeasureCategory, description: values.description || "", check_items: values.check_items || [] }, { skipGlobalError: true });
          }
          break;
      }
      antMessage.success(form.id ? "保存成功" : "创建成功");
      setForm({ type: null, open: false });
      refetch();
      refetchFloors();
    } catch (e: unknown) { antMessage.error("创建失败: " + (e instanceof Error ? e.message : "未知错误")); }
   }, [enterpriseId, form, refetch, refetchFloors, antMessage]);
 
   if (isLoading) return <Spin size="large" />;
 
   const navMenuItems = [
     { key: `/enterprises/${enterpriseId}/risk-overview`, icon: <BarChartOutlined />, label: "📊 可视化总览" },
     { key: `/enterprises/${enterpriseId}/risk-mapping-workbench`, icon: <EditOutlined />, label: "四色分布图工作台" },
     { key: `/enterprises/${enterpriseId}/risk-control-list`, icon: <UnorderedListOutlined />, label: "管控清单" },
     { key: `/enterprises/${enterpriseId}/risk-publicity`, icon: <AppIcon name="notice" size={14} />, label: "重大风险公示" },
     { key: `/enterprises/${enterpriseId}/risk-notice-cards`, icon: <ApartmentOutlined />, label: "风险告知卡" },
     { key: `/enterprises/${enterpriseId}/risk-methods`, icon: <SettingOutlined />, label: "⚙ 评估方法" },
     { key: `/enterprises/${enterpriseId}/data-dicts`, icon: <SettingOutlined />, label: "风险与隐患配置" },
     { key: `/enterprises/${enterpriseId}/org`, icon: <ApartmentOutlined />, label: "组织与人员" },
   ];

   return (
     <div style={{ display: "flex", gap: 12, height: "calc(100vh - 200px)" }}>
       {/* LEFT: 风险树编辑（紧凑） */}
       <div
         style={{
           flex: 1,
           minWidth: 380,
           display: "flex",
           flexDirection: "column",
           background: "#fff",
           borderRadius: 8,
           padding: 10,
           boxShadow: "0 2px 8px rgba(0,0,0,.08)",
         }}
       >
         {migrationPreview && migrationPreview.total > 0 && (
           <Alert
             type="warning"
             showIcon
             style={{ marginBottom: 8 }}
             title={`检测到 ${migrationPreview.total} 条旧版风险源数据未迁移`}
             action={
               <Button size="small" type="primary" onClick={() => setMigrationOpen(true)}>
                 迁移旧风险源
               </Button>
             }
           />
         )}
        <Space size={8} wrap style={{ marginBottom: 8 }}>
          <Button size="small" icon={<PlusOutlined />} onClick={() => setForm({ type: "zone", open: true })}>添加分区</Button>
          <Button size="small" icon={<ThunderboltOutlined />} onClick={() => setSmartGuideOpen(true)}>🚀 智能导引</Button>
          <Button size="small" icon={<ApartmentOutlined />} onClick={() => setFloorDrawerOpen(true)}>楼层管理</Button>
          {!embedded && (
            <Dropdown menu={{ items: navMenuItems, onClick: ({ key }) => navigate(key) }}>
              <Button size="small" icon={<DownOutlined />}>更多</Button>
            </Dropdown>
          )}
        </Space>
        <div style={{ flex: 1, minHeight: 0, overflow: "auto" }}>
         {hierarchy.length === 0 ? (
           <AppEmpty
             title="暂无风险分区"
             description="先添加分区与风险点，构建风险分级管控结构"
             actionLabel="添加分区"
             onAction={() => setForm({ type: "zone", open: true })}
             style={{ padding: "24px 8px" }}
           />
         ) : (
           <RiskHierarchyTree data={hierarchy} floors={floors} selectedKey={treeSelectedKey} onSelect={setSelectedNode} onRefresh={refetch} onAction={handleTreeAction} />
         )}
        </div>
       </div>
 
       {/* RIGHT: 节点详情（小）+ 四色图（与左侧联动） */}
       <div style={{ width: 420, flexShrink: 0, display: "flex", flexDirection: "column", gap: 12, minHeight: 0 }}>
        <div
          data-testid="risk-tree-node-detail"
          style={{ flexShrink: 0, maxHeight: "38%", overflow: "auto", background: "#fff", borderRadius: 8, padding: 12, boxShadow: "0 2px 8px rgba(0,0,0,.08)" }}
        >
        <h4 style={{ fontSize: 13, marginBottom: 8 }}>📌 节点详情</h4>
        {selectedNode ? (() => {
          if (selectedNode.type === "floor") {
            const f = floors.find((x) => x.id === selectedNode.id);
            return (
              <div style={{ fontSize: 12.5, lineHeight: 1.7 }}>
                <p><strong>{selectedNode.name}</strong></p>
                {f?.is_default && <p><Tag color="blue">默认楼层</Tag></p>}
                <p>分区数：{f?.zone_count ?? 0}</p>
                <p>风险点数：{f?.risk_point_count ?? 0}</p>
              </div>
            );
          }
          const info = hierarchyMap[selectedNode.id] || {};
          return (
            <div style={{ fontSize: 12.5, lineHeight: 1.7 }}>
              <p><strong>{selectedNode.name}</strong></p>
              {info.zone && <p>楼层：{info.zone.floor_name || "未分配"}</p>}
              {info.zone?.max_risk_level && (
                <p>分区等级：<Tag color={RISK_LEVEL_COLORS[info.zone.max_risk_level] || "#d9d9d9"}>{info.zone.max_risk_level}</Tag></p>
              )}
              {info.zone && info.zone.id !== selectedNode.id && <p>分区：{info.zone.name}</p>}
              {info.object && info.object.id !== selectedNode.id && <p>对象：{info.object.name}</p>}
              {info.unit && info.unit.id !== selectedNode.id && <p>单元：{info.unit.name}</p>}
              {info.event && info.event.id !== selectedNode.id && <p>事故类型：{info.event.accident_type}</p>}
              {info.event?.risk_level && <p>风险等级：<Tag color={RISK_LEVEL_COLORS[info.event.risk_level]}>{info.event.risk_level}</Tag></p>}
              {info.event?.risk_score && <p>风险分值：{info.event.risk_score}</p>}
              {info.event?.description && <p style={{ color: "#666" }}>{info.event.description}</p>}
              {info.measure && (
                <p>
                  措施类别：
                  {MEASURE_CATEGORY_LABELS[info.measure.measure_category] ?? info.measure.measure_category}
                </p>
              )}
              {info.measure?.status && <p>状态：{info.measure.status}</p>}
              {info.object?.category && <p>类别：{info.object.category}</p>}
              {info.unit?.unit_type && <p>类型：{info.unit.unit_type}</p>}
            </div>
          );
        })() : <p style={{ color: "#8c8c8c", fontSize: 12.5 }}>点击左侧风险树节点查看详情（地图联动高亮）</p>}
        </div>
        <RiskTreeFourColorMap
          floors={floors}
          floorId={mapFloorId}
          highlightZoneId={highlightZoneId}
          onFloorChange={setMapFloorId}
          onZoneClick={handleMapZoneClick}
          onManageFloors={() => setFloorDrawerOpen(true)}
        />
       </div>
 
       {/* FORMS */}
       {form.type === "zone" && <RiskZoneForm key={`zone-${form.id || "new"}`} open={form.open} onClose={() => setForm({ type: null, open: false })} onSubmit={handleFormSubmit} initialValues={form.initialValues} floorPlanUrl={floorPlanUrl || undefined} floors={floors} />}
       {form.type === "object" && <RiskObjectForm key={`object-${form.id || form.parentId || "new"}`} open={form.open} onClose={() => setForm({ type: null, open: false })} onSubmit={handleFormSubmit} initialValues={form.initialValues} isEdit={!!form.id} zones={zones} />}
       {form.type === "unit" && <RiskUnitForm key={`unit-${form.id || form.parentId || "new"}`} open={form.open} onClose={() => setForm({ type: null, open: false })} onSubmit={handleFormSubmit} initialValues={form.initialValues} />}
       {form.type === "event" && (() => {
         const pInfo = hierarchyMap[form.parentId || ""] || {};
        return <RiskEventForm key={`event-${form.id || form.parentId || "new"}`} open={form.open} onClose={() => setForm({ type: null, open: false })} onSubmit={handleFormSubmit} initialValues={form.initialValues} enterpriseId={enterpriseId} eventId={form.id} zoneName={pInfo.zone?.name} objectName={pInfo.object?.name} unitName={pInfo.unit?.name} />;
       })()}
       {form.type === "measure" && <RiskMeasureForm key={`measure-${form.id || form.parentId || "new"}`} open={form.open} onClose={() => setForm({ type: null, open: false })} onSubmit={handleFormSubmit} initialValues={form.initialValues} enterpriseId={enterpriseId} />}
 
       <FloorManagementDrawer
         enterpriseId={enterpriseId}
         open={floorDrawerOpen}
         onClose={() => setFloorDrawerOpen(false)}
         onChanged={refetch}
       />

      {/* SMART GUIDE MODAL */}
      <RiskSmartGuideModal open={smartGuideOpen} onClose={() => setSmartGuideOpen(false)} onRefresh={refetch} enterpriseId={enterpriseId} />
      <RiskMigrationWizard
        open={migrationOpen}
        onClose={() => setMigrationOpen(false)}
        onRefresh={() => {
          refetch();
          refetchFloors();
          refetchMigrationPreview();
        }}
        enterpriseId={enterpriseId}
      />
     </div>
   );
 }
