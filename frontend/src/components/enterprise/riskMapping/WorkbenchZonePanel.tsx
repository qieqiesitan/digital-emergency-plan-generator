import { Button, Divider, Empty, Space } from "antd";
import { PlusOutlined, DeleteOutlined } from "@ant-design/icons";
import { useRiskMappingWorkbenchStore } from "@/store/riskMappingWorkbenchStore";
import type { WorkbenchZone } from "@/types/riskMappingWorkbench";

export default function WorkbenchZonePanel() {
  const zones = useRiskMappingWorkbenchStore(s => s.zones);
  const pendingRegions = useRiskMappingWorkbenchStore(s => s.pendingRegions);
  const selectedZoneId = useRiskMappingWorkbenchStore(s => s.selectedZoneId);
  const setState = useRiskMappingWorkbenchStore.setState;
  const commit = useRiskMappingWorkbenchStore.getState().commit;

  const addZone = () => {
    const zone: WorkbenchZone = {
      id: `new-zone-${Date.now()}`,
      enterprise_id: "",
      floor_id: useRiskMappingWorkbenchStore.getState().currentFloorId,
      floor_name: "",
      name: "未命名分区",
      description: null,
      sort_order: zones.length,
      floor_plan_polygon: null,
      max_risk_level: "未评估",
      effective_color: "#d9d9d9",
      object_count: 0,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      objects: [],
    };
    setState({ zones: [...zones, zone], selectedZoneId: zone.id });
    commit();
  };

  return (
    <div style={{ background: "#fff", borderRadius: 8, padding: 8, overflow: "auto" }}>
      <Space style={{ width: "100%", justifyContent: "space-between" }}>
        <strong>分区</strong>
        <Button size="small" icon={<PlusOutlined />} onClick={addZone}>
          新增
        </Button>
      </Space>
      {zones.length === 0 ? (
        <Empty description="暂无分区" />
      ) : (
        zones.map(z => (
          <div
            key={z.id}
            onClick={() => setState({ selectedZoneId: z.id })}
            style={{
              marginTop: 6,
              padding: 8,
              borderRadius: 6,
              cursor: "pointer",
              border: selectedZoneId === z.id ? "2px solid #1677ff" : "1px solid #d9d9d9",
              background: z.effective_color ? z.effective_color + "18" : "#fff",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span>{z.name}</span>
              <Button
                size="small"
                type="text"
                icon={<DeleteOutlined />}
                onClick={e => {
                  e.stopPropagation();
                  const isPersisted = !z.id.startsWith("new-zone-");
                  setState({
                    zones: zones.filter(item => item.id !== z.id),
                    selectedZoneId: null,
                    deletedZoneIds: isPersisted
                      ? [...useRiskMappingWorkbenchStore.getState().deletedZoneIds, z.id]
                      : useRiskMappingWorkbenchStore.getState().deletedZoneIds,
                  });
                  commit();
                }}
              />
            </div>
            <div style={{ fontSize: 12, color: "#8c8c8c" }}>
              {(z.floor_plan_polygon?.polygons || []).length} 个区域 · {z.max_risk_level || "未评估"}风险
            </div>
          </div>
        ))
      )}
      <Divider style={{ margin: "12px 0" }}>待绑定区域</Divider>
      {pendingRegions.length === 0 ? (
        <div style={{ color: "#999", fontSize: 12 }}>暂无待绑定区域</div>
      ) : (
        pendingRegions.map(r => (
          <div key={r.id} style={{ padding: 6, border: "1px dashed #fa8c16", borderRadius: 6, marginTop: 4 }}>
            未绑定区域 · {r.points.length} 个顶点
          </div>
        ))
      )}
    </div>
  );
}
