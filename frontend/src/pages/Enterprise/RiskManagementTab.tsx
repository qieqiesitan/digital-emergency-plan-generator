 import { useState, useCallback } from "react";
 import { useNavigate } from "react-router-dom";
 import { Button, Spin, Empty, Space, Drawer, message, Modal } from "antd";
 import { PlusOutlined, ThunderboltOutlined, BarChartOutlined, SettingOutlined } from "@ant-design/icons";
 import { useQuery, useQueryClient } from "@tanstack/react-query";
 import { getFullHierarchy, createZone, createObject, createUnit, createEvent, createMeasure } from "@/services/riskManagementService";
 import RiskHierarchyTree from "@/components/enterprise/RiskHierarchyTree";
 import RiskZoneForm from "@/components/enterprise/RiskZoneForm";
 import RiskObjectForm from "@/components/enterprise/RiskObjectForm";
 import RiskUnitForm from "@/components/enterprise/RiskUnitForm";
 import RiskEventForm from "@/components/enterprise/RiskEventForm";
 import RiskMeasureForm from "@/components/enterprise/RiskMeasureForm";
 import RiskSmartGuideModal from "@/components/enterprise/RiskSmartGuideModal";
 import type { HierarchyZone, RiskZoneCreate, RiskObjectCreate, RiskUnitCreate, RiskEventCreate, RiskMeasureCreate } from "@/types/riskManagement";
 
 interface Props { enterpriseId: string; floorPlanUrl?: string | null; }
 
 type FormType = "zone" | "object" | "unit" | "event" | "measure" | null;
 
 interface FormState { type: FormType; open: boolean; parentId?: string; parentType?: string; initialValues?: any; }
 
 export default function RiskManagementTab({ enterpriseId, floorPlanUrl }: Props) {
   const navigate = useNavigate();
   const queryClient = useQueryClient();
 
   const { data: hierarchy = [], isLoading, refetch } = useQuery({ queryKey: ["risk-hierarchy", enterpriseId], queryFn: () => getFullHierarchy(enterpriseId) });
 
   const [selectedNode, setSelectedNode] = useState<{ id: string; type: string; name: string } | null>(null);
   const [form, setForm] = useState<FormState>({ type: null, open: false });
   const [smartGuideOpen, setSmartGuideOpen] = useState(false);
   const [zones, setZones] = useState<{ id: string; name: string }[]>([]);
 
   // Refresh zone list for object form dropdown
   const refreshZones = useCallback(() => {
     if (hierarchy) setZones(hierarchy.map(z => ({ id: z.id, name: z.name })));
   }, [hierarchy]);
 
   // Handle tree node action (add/edit/delete from RiskHierarchyTree)
   const handleTreeAction = useCallback((action: string, meta: { id: string; type: string; name: string }) => {
     switch (action) {
       case "add-zone":
         setForm({ type: "zone", open: true });
         break;
       case "add-object":
         setForm({ type: "object", open: true, parentId: meta.id, parentType: "zone" });
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
       case "edit-zone":
       case "edit-object":
       case "edit-unit":
       case "edit-event":
       case "edit-measure":
         message.info(`编辑功能开发中: ${meta.name}`);
         break;
       case "delete-zone":
         Modal.confirm({ title: `确认删除分区「${meta.name}」？`, content: "将级联删除该分区下所有对象、单元、事件和措施", onOk: async () => { await fetch(`/api/v1/enterprises/${enterpriseId}/risk-management/zones/${meta.id}`, { method: "DELETE" }); refetch(); } });
         break;
       case "delete-object":
         Modal.confirm({ title: `确认删除对象「${meta.name}」？`, content: "将级联删除该对象下所有单元、事件和措施", onOk: async () => { await fetch(`/api/v1/enterprises/${enterpriseId}/risk-management/objects/${meta.id}`, { method: "DELETE" }); refetch(); } });
         break;
       case "delete-unit":
         Modal.confirm({ title: `确认删除单元「${meta.name}」？`, content: "将级联删除该单元下所有事件和措施", onOk: async () => { await fetch(`/api/v1/enterprises/${enterpriseId}/risk-management/objects/placeholder/units/${meta.id}`, { method: "DELETE" }); refetch(); } });
         break;
       case "delete-event":
         Modal.confirm({ title: `确认删除事件「${meta.name}」？`, onOk: async () => { await fetch(`/api/v1/enterprises/${enterpriseId}/risk-management/events/${meta.id}`, { method: "DELETE" }); refetch(); } });
         break;
       case "delete-measure":
         Modal.confirm({ title: `确认删除措施「${meta.name}」？`, onOk: async () => { await fetch(`/api/v1/enterprises/${enterpriseId}/risk-management/events/${meta.id}/measures`, { method: "DELETE" }); refetch(); } });
         break;
       default:
         message.info(`${action}: ${meta.name}`);
     }
   }, [enterpriseId, refetch]);
 
   // Handle form submit
   const handleFormSubmit = useCallback(async (values: any) => {
     try {
       switch (form.type) {
         case "zone":
           await createZone(enterpriseId, { name: values.name, description: values.description || "" });
           break;
         case "object":
           await createObject(enterpriseId, { zone_id: form.parentId, name: values.name, category: values.category || "", description: values.description || "", is_risk_point: values.is_risk_point || false });
           break;
         case "unit":
           await createUnit(enterpriseId, form.parentId || "", { object_id: form.parentId || "", name: values.name, unit_type: values.unit_type || "", description: values.description || "" });
           break;
         case "event":
           await createEvent(enterpriseId, form.parentId || "", { accident_type: values.accident_type, description: values.description || "", method_type: values.method_type || "LS", method_params: values.method_params || {} });
           break;
         case "measure":
           await createMeasure(enterpriseId, form.parentId || "", { event_id: form.parentId || "", measure_category: values.measure_category, description: values.description || "", check_items: values.check_items || [] });
           break;
       }
       message.success("创建成功");
       setForm({ type: null, open: false });
       refetch();
       refreshZones();
     } catch (e: any) { message.error("创建失败: " + (e?.message || "未知错误")); }
   }, [enterpriseId, form, refetch, refreshZones]);
 
   if (isLoading) return <Spin size="large" />;
 
   return (
     <div style={{ display: "flex", gap: 16, height: "calc(100vh - 200px)" }}>
       {/* LEFT: Tree */}
       <div style={{ flex: 1, minWidth: 360, overflow: "auto", background: "#fff", borderRadius: 8, padding: 12, boxShadow: "0 2px 8px rgba(0,0,0,.08)" }}>
         <Space style={{ marginBottom: 12 }}>
           <Button icon={<PlusOutlined />} onClick={() => setForm({ type: "zone", open: true })}>添加分区</Button>
           <Button icon={<ThunderboltOutlined />} onClick={() => setSmartGuideOpen(true)}>🚀 智能导引</Button>
           <Button icon={<BarChartOutlined />} onClick={() => navigate(`/enterprises/${enterpriseId}/risk-overview`)}>📊 可视化总览</Button>
           <Button icon={<SettingOutlined />} onClick={() => navigate(`/enterprises/${enterpriseId}/risk-methods`)}>⚙ 评估方法</Button>
         </Space>
         {hierarchy.length === 0 ? <Empty description="暂无数据，请添加风险分区" /> : <RiskHierarchyTree data={hierarchy} onSelect={setSelectedNode} onRefresh={refetch} onAction={handleTreeAction} />}
       </div>
 
       {/* RIGHT: Detail Panel */}
       <div style={{ width: 300, background: "#fff", borderRadius: 8, padding: 16, boxShadow: "0 2px 8px rgba(0,0,0,.08)", overflow: "auto" }}>
         <h4 style={{ fontSize: 14, marginBottom: 12 }}>📌 节点详情</h4>
         {selectedNode ? <div><p>名称: {selectedNode.name}</p><p>类型: {selectedNode.type}</p><p>ID: {selectedNode.id?.slice(0, 8)}...</p></div> : <p style={{ color: "#8c8c8c", fontSize: 13 }}>点击层级树中的节点查看详情</p>}
       </div>
 
       {/* FORMS */}
       {form.type === "zone" && <RiskZoneForm open={form.open} onClose={() => setForm({ type: null, open: false })} onSubmit={handleFormSubmit} floorPlanUrl={floorPlanUrl || undefined} />}
       {form.type === "object" && <RiskObjectForm open={form.open} onClose={() => setForm({ type: null, open: false })} onSubmit={handleFormSubmit} zones={zones} />}
       {form.type === "unit" && <RiskUnitForm open={form.open} onClose={() => setForm({ type: null, open: false })} onSubmit={handleFormSubmit} />}
       {form.type === "event" && <RiskEventForm open={form.open} onClose={() => setForm({ type: null, open: false })} onSubmit={handleFormSubmit} enterpriseId={enterpriseId} />}
       {form.type === "measure" && <RiskMeasureForm open={form.open} onClose={() => setForm({ type: null, open: false })} onSubmit={handleFormSubmit} enterpriseId={enterpriseId} />}
 
       {/* SMART GUIDE MODAL */}
       <RiskSmartGuideModal open={smartGuideOpen} onClose={() => setSmartGuideOpen(false)} onRefresh={refetch} enterpriseId={enterpriseId} />
     </div>
   );
 }
