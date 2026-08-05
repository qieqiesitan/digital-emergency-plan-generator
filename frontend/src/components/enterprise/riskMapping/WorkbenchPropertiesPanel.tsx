import { useState } from "react";
import { Button, Input, Select, Space } from "antd";
import { DeleteOutlined, PlusOutlined } from "@ant-design/icons";
import { useRiskMappingWorkbenchStore } from "@/store/riskMappingWorkbenchStore";
import type { RiskCanvasText, WorkbenchZone } from "@/types/riskMappingWorkbench";

export default function WorkbenchPropertiesPanel() {
  const zones = useRiskMappingWorkbenchStore(s => s.zones);
  const riskPoints = useRiskMappingWorkbenchStore(s => s.riskPoints);
  const pendingRegions = useRiskMappingWorkbenchStore(s => s.pendingRegions);
  const texts = useRiskMappingWorkbenchStore(s => s.texts);
  const selectedZoneId = useRiskMappingWorkbenchStore(s => s.selectedZoneId);
  const setSnapshot = useRiskMappingWorkbenchStore.getState().setSnapshot;
  const commit = useRiskMappingWorkbenchStore.getState().commit;
  const [textContent, setTextContent] = useState("");
  const zone = zones.find(z => z.id === selectedZoneId);

  const updateZone = (patch: Partial<WorkbenchZone>) => {
    if (!zone) return;
    commit();
    setSnapshot({ zones: zones.map(z => (z.id === zone.id ? { ...z, ...patch } : z)) });
  };

  const bindFirstPending = () => {
    if (!zone || !pendingRegions.length) return;
    const region = pendingRegions[0];
    const polygon = zone.floor_plan_polygon || { version: 2, color_source: "auto" as const, color: null, polygons: [] };
    commit();
    setSnapshot({
      zones: zones.map(z =>
        z.id === zone.id
          ? {
              ...z,
              floor_plan_polygon: {
                ...polygon,
                polygons: [...polygon.polygons, { id: region.id, label: `${zone.name}-区域${polygon.polygons.length + 1}`, points: region.points }],
              },
            }
          : z,
      ),
      pendingRegions: pendingRegions.slice(1),
    });
  };

  const addText = () => {
    if (!textContent.trim()) return;
    const item: RiskCanvasText = {
      id: `text-${Date.now()}`,
      content: textContent.trim(),
      x: 50,
      y: 50,
      font_size: 14,
      color: "#333333",
      rotation: 0,
      sort_order: texts.length,
    };
    commit();
    setSnapshot({ texts: [...texts, item] });
    setTextContent("");
  };

  return (
    <div style={{ background: "#fff", borderRadius: 8, padding: 12, overflow: "auto" }}>
      <h4 style={{ fontSize: 14, marginBottom: 12 }}>属性</h4>
      {!zone ? (
        <div style={{ color: "#999" }}>请先选择分区</div>
      ) : (
        <>
          <Input value={zone.name} onChange={e => updateZone({ name: e.target.value })} />
          <Input.TextArea
            style={{ marginTop: 8 }}
            rows={3}
            value={zone.description || ""}
            onChange={e => updateZone({ description: e.target.value })}
          />
          <Select
            style={{ width: "100%", marginTop: 8 }}
            value={zone.floor_plan_polygon?.color_source || "auto"}
            options={[{ value: "auto", label: "自动颜色" }, { value: "manual", label: "手动覆盖" }]}
            onChange={value => {
              const polygon = zone.floor_plan_polygon || { version: 2, color_source: "auto" as const, color: null, polygons: [] };
              updateZone({
                floor_plan_polygon: {
                  ...polygon,
                  color_source: value as "auto" | "manual",
                  color: value === "manual" ? polygon.color || "#ff4d4f" : null,
                },
              });
            }}
          />
          {zone.floor_plan_polygon?.color_source === "manual" && (
            <Input
              type="color"
              style={{ width: "100%", marginTop: 8 }}
              value={zone.floor_plan_polygon.color || "#ff4d4f"}
              onChange={e =>
                updateZone({
                  floor_plan_polygon: { ...zone.floor_plan_polygon!, color: e.target.value },
                })
              }
            />
          )}
          {pendingRegions.length > 0 && (
            <Button block style={{ marginTop: 8 }} onClick={bindFirstPending}>
              绑定待处理区域
            </Button>
          )}
          <Button
            danger
            block
            style={{ marginTop: 8 }}
            icon={<DeleteOutlined />}
            onClick={() => {
              commit();
              useRiskMappingWorkbenchStore.getState().deleteZone(zone.id);
            }}
          >
            删除分区
          </Button>
        </>
      )}
      <h4 style={{ fontSize: 14, marginTop: 16 }}>风险点</h4>
      {riskPoints.map(p => (
        <div key={p.id} style={{ marginTop: 4 }}>
          <div style={{ display: "flex", justifyContent: "space-between" }}>
            <span>{p.name}</span>
            <Button
              size="small"
              type="text"
              icon={<DeleteOutlined />}
              onClick={() => {
                commit();
                useRiskMappingWorkbenchStore.getState().deleteRiskPoint(p.id);
              }}
            />
          </div>
          <Select
            size="small"
            style={{ width: "100%", marginTop: 4 }}
            value={p.zone_id || undefined}
            placeholder="绑定分区"
            options={zones.map(z => ({ value: z.id, label: z.name }))}
            onChange={zone_id => {
              commit();
              setSnapshot({ riskPoints: riskPoints.map(item => (item.id === p.id ? { ...item, zone_id } : item)) });
            }}
          />
        </div>
      ))}
      <h4 style={{ fontSize: 14, marginTop: 16 }}>文字标注</h4>
      <Space.Compact style={{ width: "100%" }}>
        <Input value={textContent} onChange={e => setTextContent(e.target.value)} placeholder="标注内容" />
        <Button icon={<PlusOutlined />} onClick={addText} />
      </Space.Compact>
      {texts.map(t => (
        <div
          key={t.id}
          style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: 12, marginTop: 4 }}
        >
          <span
            style={{
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
              color: t.color,
              fontSize: t.font_size,
            }}
          >
            {t.content}
          </span>
          <Button
            size="small"
            type="text"
            icon={<DeleteOutlined />}
            onClick={() => {
              commit();
              setSnapshot({ texts: texts.filter(item => item.id !== t.id) });
            }}
          />
        </div>
      ))}
    </div>
  );
}
