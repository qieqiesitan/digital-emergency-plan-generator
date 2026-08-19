import { useState, useCallback, useMemo, useEffect } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { App as AntApp, Alert, Button, Spin, Empty, Space, Tag } from "antd";
import { PlusOutlined, ThunderboltOutlined, BarChartOutlined, SettingOutlined, EditOutlined, ApartmentOutlined, UnorderedListOutlined } from "@ant-design/icons";
import AppIcon from "@/components/common/AppIcon";
import { useQuery } from "@tanstack/react-query";
import { getFullHierarchy, createZone, updateZone, deleteZone, createObject, updateObject, deleteObject, createUnit, updateUnit, deleteUnit, createEvent, updateEvent, deleteEvent, createMeasure, updateMeasure, deleteMeasure, getMigrationPreview } from "@/services/riskManagementService";
import { deleteEnterpriseFloor, listEnterpriseFloors } from "@/services/riskMappingWorkbenchService";
import RiskHierarchyTree, { type TreeNodeMeta } from "@/components/enterprise/RiskHierarchyTree";
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
 
   const [selectedNode, setSelectedNode] = useState<{ id: string; type: string; name: string } | null>(null);
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
            await updateZone(enterpriseId, form.id, zonePayload);
          } else {
            await createZone(enterpriseId, zonePayload);
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
            await updateObject(enterpriseId, form.id, objectPayload);
          } else {
            await createObject(enterpriseId, { ...objectPayload, zone_id: form.parentId });
          }
          break;
        }
        case "unit":
          if (form.id) {
            await updateUnit(enterpriseId, form.parentId || "", form.id, { name: values.name || "", unit_type: values.unit_type || "", description: values.description || "" });
          } else {
          await createUnit(enterpriseId, form.parentId || "", { name: values.name || "", unit_type: values.unit_type || "", description: values.description || "" });
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
            await updateEvent(enterpriseId, form.id, eventPayload);
          } else {
            await createEvent(enterpriseId, form.parentId || "", { ...eventPayload, ...(form.parentType === "object" ? { object_id: form.parentId } : { unit_id: form.parentId }) });
          }
          break;
        }
        case "measure":
          if (form.id) {
            await updateMeasure(enterpriseId, form.parentId || "", form.id, { measure_category: values.measure_category as MeasureCategory, description: values.description || "", check_items: values.check_items || [] });
          } else {
          await createMeasure(enterpriseId, form.parentId || "", { measure_category: values.measure_category as MeasureCategory, description: values.description || "", check_items: values.check_items || [] });
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
 
   return (
     <div style={{ display: "flex", gap: 16, height: "calc(100vh - 200px)" }}>
       {/* LEFT: Tree */}
       <div style={{ flex: 1, minWidth: 360, overflow: "auto", background: "#fff", borderRadius: 8, padding: 12, boxShadow: "0 2px 8px rgba(0,0,0,.08)" }}>
         {migrationPreview && migrationPreview.total > 0 && (
           <Alert
             type="warning"
             showIcon
             style={{ marginBottom: 12 }}
             message={`检测到 ${migrationPreview.total} 条旧版风险源数据未迁移`}
             action={
               <Button size="small" type="primary" onClick={() => setMigrationOpen(true)}>
                 迁移旧风险源
               </Button>
             }
           />
         )}
        <Space style={{ marginBottom: 12 }}>
          <Button icon={<PlusOutlined />} onClick={() => setForm({ type: "zone", open: true })}>添加分区</Button>
          <Button icon={<ThunderboltOutlined />} onClick={() => setSmartGuideOpen(true)}>🚀 智能导引</Button>
          <Button icon={<ApartmentOutlined />} onClick={() => setFloorDrawerOpen(true)}>楼层管理</Button>
          {!embedded && (
            <>
              <Button icon={<BarChartOutlined />} onClick={() => navigate(`/enterprises/${enterpriseId}/risk-overview`)}>📊 可视化总览</Button>
              <Button icon={<EditOutlined />} onClick={() => navigate(`/enterprises/${enterpriseId}/risk-mapping-workbench`)}>四色分布图工作台</Button>
              <Button icon={<UnorderedListOutlined />} onClick={() => navigate(`/enterprises/${enterpriseId}/risk-control-list`)}>管控清单</Button>
              <Button icon={<AppIcon name="notice" size={14} />} onClick={() => navigate(`/enterprises/${enterpriseId}/risk-publicity`)}>重大风险公示</Button>
              <Button icon={<ApartmentOutlined />} onClick={() => navigate(`/enterprises/${enterpriseId}/risk-notice-cards`)}>风险告知卡</Button>
              <Button icon={<SettingOutlined />} onClick={() => navigate(`/enterprises/${enterpriseId}/risk-methods`)}>⚙ 评估方法</Button>
              <Button icon={<SettingOutlined />} onClick={() => navigate(`/enterprises/${enterpriseId}/data-dicts`)}>风险与隐患配置</Button>
              <Button icon={<ApartmentOutlined />} onClick={() => navigate(`/enterprises/${enterpriseId}/org`)}>组织与人员</Button>
            </>
          )}
        </Space>
         {hierarchy.length === 0 ? <Empty description="暂无数据，请添加风险分区" /> : <RiskHierarchyTree data={hierarchy} floors={floors} onSelect={setSelectedNode} onRefresh={refetch} onAction={handleTreeAction} />}
       </div>
 
       {/* RIGHT: Detail Panel */}
       <div style={{ width: 300, background: "#fff", borderRadius: 8, padding: 16, boxShadow: "0 2px 8px rgba(0,0,0,.08)", overflow: "auto" }}>
        <h4 style={{ fontSize: 14, marginBottom: 12 }}>📌 节点详情</h4>
        {selectedNode ? (() => {
          if (selectedNode.type === "floor") {
            const f = floors.find((x) => x.id === selectedNode.id);
            return (
              <div style={{ fontSize: 13, lineHeight: 1.8 }}>
                <p><strong>{selectedNode.name}</strong></p>
                {f?.is_default && <p><Tag color="blue">默认楼层</Tag></p>}
                <p>分区数：{f?.zone_count ?? 0}</p>
                <p>风险点数：{f?.risk_point_count ?? 0}</p>
              </div>
            );
          }
          const info = hierarchyMap[selectedNode.id] || {};
          return (
            <div style={{ fontSize: 13, lineHeight: 1.8 }}>
              <p><strong>{selectedNode.name}</strong></p>
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
        })() : <p style={{ color: "#8c8c8c", fontSize: 13 }}>点击层级树中的节点查看详情</p>}
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
