import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Spin, Space, Button, Modal, message } from "antd";
import { ArrowLeftOutlined, SaveOutlined, UndoOutlined, RedoOutlined, UploadOutlined } from "@ant-design/icons";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  getRiskMappingWorkbench,
  saveRiskMappingWorkbench,
} from "@/services/riskMappingWorkbenchService";
import { useRiskMappingWorkbenchStore, undo, redo } from "@/store/riskMappingWorkbenchStore";
import type { BatchSavePayload } from "@/types/riskMappingWorkbench";
import WorkbenchToolbar from "@/components/enterprise/riskMapping/WorkbenchToolbar";
import WorkbenchZonePanel from "@/components/enterprise/riskMapping/WorkbenchZonePanel";
import WorkbenchPropertiesPanel from "@/components/enterprise/riskMapping/WorkbenchPropertiesPanel";
import WorkbenchCanvas from "@/components/enterprise/riskMapping/WorkbenchCanvas";
import WorkbenchLegend from "@/components/enterprise/riskMapping/WorkbenchLegend";
import EnterpriseFloorManager from "@/components/enterprise/EnterpriseFloorManager";
import FourColorImportModal from "@/components/enterprise/riskMapping/FourColorImportModal";

export default function RiskMappingWorkbenchPage() {
  const { id: enterpriseId } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const currentFloorId = useRiskMappingWorkbenchStore(s => s.currentFloorId);
  const setSnapshot = useRiskMappingWorkbenchStore(s => s.setSnapshot);
  const dirty = useRiskMappingWorkbenchStore(s => s.dirty);
  const [importOpen, setImportOpen] = useState(false);
  const floors = useRiskMappingWorkbenchStore(s => s.floors);
  const zones = useRiskMappingWorkbenchStore(s => s.zones);
  const riskPoints = useRiskMappingWorkbenchStore(s => s.riskPoints);
  const texts = useRiskMappingWorkbenchStore(s => s.texts);
  const currentFloor = floors.find(f => f.id === currentFloorId);
  const queryClient = useQueryClient();

  const goBack = () => {
    const back = () => {
      if (enterpriseId) {
        navigate(`/enterprises/${enterpriseId}`);
      } else {
        navigate(-1);
      }
    };
    if (dirty) {
      Modal.confirm({
        title: "返回并放弃未保存的改动？",
        content: "当前工作台存在未保存修改，返回后这些改动将丢失。",
        okText: "返回",
        okButtonProps: { danger: true },
        cancelText: "取消",
        onOk: back,
      });
      return;
    }
    back();
  };

  const { data, isLoading } = useQuery({
    queryKey: ["risk-workbench", enterpriseId, currentFloorId],
    queryFn: () => getRiskMappingWorkbench(enterpriseId!, currentFloorId || undefined),
    enabled: !!enterpriseId,
  });

  useEffect(() => {
    if (data) {
      setSnapshot({
        floors: data.floors,
        currentFloorId: data.currentFloorId,
        zones: data.zones,
        riskPoints: data.riskPoints,
        texts: data.texts,
        pendingRegions: data.pendingRegions ?? [],
        deletedRiskPointIds: [],
        deletedZoneIds: [],
      });
      useRiskMappingWorkbenchStore.getState().markSaved();
    }
  }, [data, setSnapshot]);

  const onSave = async () => {
    const state = useRiskMappingWorkbenchStore.getState();
    const floor = state.floors.find(f => f.id === state.currentFloorId);
    if (!floor) return;
    if (state.pendingRegions.length) {
      Modal.warning({
        title: "存在待绑定区域",
        content: (
          <div>
            <p>以下区域尚未绑定到分区，请先在右侧属性面板选择分区并点击「绑定待处理区域」：</p>
            <ul>
              {state.pendingRegions.map(r => (
                <li key={r.id}>未绑定区域 · {r.points.length} 个顶点</li>
              ))}
            </ul>
          </div>
        ),
      });
      return;
    }
    if (state.zones.some(z => !z.floor_plan_polygon?.polygons.length)) {
      message.error("所有分区必须至少绘制一个区域");
      return;
    }
    if (state.riskPoints.some(p => !p.zone_id)) {
      message.error("所有风险点必须绑定分区");
      return;
    }
    const zones = state.zones.map(z => {
      const isNew = z.id.startsWith("new-zone-");
      const polygon = z.floor_plan_polygon ?? { version: 2, color_source: "auto" as const, color: null, polygons: [] };
      return isNew
        ? {
            zone_id: null as null,
            client_id: z.id,
            name: z.name,
            description: z.description ?? undefined,
            sort_order: z.sort_order,
            floor_plan_polygon: polygon,
          }
        : {
            zone_id: z.id,
            client_id: z.id,
            updated_at: z.updated_at,
            name: z.name,
            description: z.description ?? undefined,
            sort_order: z.sort_order,
            floor_plan_polygon: polygon,
          };
    });
    const risk_points = state.riskPoints.map(p => {
      const isNew = p.id.startsWith("new-point-");
      const targetZone = state.zones.find(z => z.id === p.zone_id);
      const targetZoneIsNew = targetZone?.id.startsWith("new-zone-") ?? false;
      const common = {
        name: p.name,
        zone_id: targetZoneIsNew ? null : p.zone_id,
        zone_client_id: targetZoneIsNew ? p.zone_id : undefined,
        floor_id: p.floor_id,
        location_x: p.location_x ?? 0,
        location_y: p.location_y ?? 0,
      };
      return isNew
        ? { id: null as null, client_id: p.id, ...common }
        : { id: p.id, client_id: p.id, updated_at: p.updated_at, ...common };
    });
    const payload: BatchSavePayload = {
      floor_id: floor.id,
      floor_updated_at: floor.updated_at,
      zones,
      risk_points,
      deleted_risk_point_ids: state.deletedRiskPointIds,
      deleted_zone_ids: state.deletedZoneIds,
      confirm_cascade_zone_ids: [],
      texts: state.texts,
    };
    try {
      const saved = await saveRiskMappingWorkbench(enterpriseId!, payload);
      setSnapshot({
        floors: state.floors.map(f => (f.id === saved.floor.id ? saved.floor : f)),
        currentFloorId: saved.floor.id,
        zones: saved.zones,
        riskPoints: saved.risk_points,
        texts: saved.texts,
        pendingRegions: state.pendingRegions,
        deletedRiskPointIds: [],
        deletedZoneIds: [],
      });
      useRiskMappingWorkbenchStore.getState().markSaved();
      message.success("保存成功");
      queryClient.invalidateQueries({ queryKey: ["risk-hierarchy", enterpriseId] });
      queryClient.invalidateQueries({ queryKey: ["risk-overview", enterpriseId] });
    } catch (e) {
      const err = e as { response?: { data?: { detail?: unknown } } };
      const detail = err?.response?.data?.detail;
      const code = typeof detail === "string" ? detail : (detail as { code?: string } | undefined)?.code;
      const msg = typeof detail === "string" ? detail : (detail as { message?: string } | undefined)?.message;
      if (code === "SAVE_CONFLICT") {
        message.error("数据已被其他人修改，请刷新后重试");
      } else {
        message.error(msg || "保存失败");
      }
    }
  };

  if (isLoading) return <Spin size="large" />;

  return (
    <div style={{ height: "calc(100vh - 80px)", display: "flex", flexDirection: "column", gap: 8 }}>
      <Space wrap>
        <Button aria-label="返回" icon={<ArrowLeftOutlined />} onClick={goBack} />
        <EnterpriseFloorManager enterpriseId={enterpriseId!} />
        <Button
          aria-label="导入四色图"
          icon={<UploadOutlined />}
          disabled={!currentFloor}
          onClick={() => setImportOpen(true)}
        >
          导入四色图
        </Button>
        <WorkbenchToolbar />
        <Button aria-label="撤销" icon={<UndoOutlined />} onClick={undo} />
        <Button aria-label="重做" icon={<RedoOutlined />} onClick={redo} />
        <Button
          aria-label="保存工作台"
          type="primary"
          icon={<SaveOutlined />}
          disabled={!dirty}
          onClick={onSave}
        >
          保存
        </Button>
      </Space>
      <div style={{ flex: 1, display: "grid", gridTemplateColumns: "260px 1fr 300px", gap: 8, minHeight: 0 }}>
        <WorkbenchZonePanel />
        <div style={{ position: "relative", background: "#f5f5f5", borderRadius: 8, overflow: "hidden" }}>
          <WorkbenchCanvas />
          <WorkbenchLegend />
        </div>
        <WorkbenchPropertiesPanel />
      </div>
      <FourColorImportModal
        open={importOpen}
        enterpriseId={enterpriseId!}
        floorId={currentFloor?.id ?? ""}
        hasExistingData={zones.length > 0 || riskPoints.length > 0 || texts.length > 0}
        existingZoneCount={zones.length}
        existingRiskPointCount={riskPoints.length}
        onClose={() => setImportOpen(false)}
        onImported={result => {
          setImportOpen(false);
          const state = useRiskMappingWorkbenchStore.getState();
          setSnapshot({
            floors: state.floors.map(f => (f.id === result.floor.id ? result.floor : f)),
            currentFloorId: result.floor.id,
            zones: result.zones,
            riskPoints: [],
            texts: [],
            pendingRegions: [],
            deletedRiskPointIds: [],
            deletedZoneIds: [],
          });
          useRiskMappingWorkbenchStore.getState().markSaved();
          message.success("四色图导入成功");
          queryClient.invalidateQueries({ queryKey: ["risk-hierarchy", enterpriseId] });
          queryClient.invalidateQueries({ queryKey: ["risk-overview", enterpriseId] });
        }}
      />
    </div>
  );
}
