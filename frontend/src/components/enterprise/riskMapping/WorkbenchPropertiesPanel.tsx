import { useEffect, useState } from "react";
import { Button, Input, InputNumber, Select, Space } from "antd";
import { DeleteOutlined, PlusOutlined } from "@ant-design/icons";
import { useRiskMappingWorkbenchStore } from "@/store/riskMappingWorkbenchStore";
import type { RiskCanvasText, WorkbenchZone } from "@/types/riskMappingWorkbench";
import type { RiskObject } from "@/types/riskManagement";

type RiskPointDraft = Pick<
  RiskObject,
  "id" | "name" | "category" | "location" | "description" | "location_x" | "location_y" | "zone_id"
>;

export default function WorkbenchPropertiesPanel() {
  const zones = useRiskMappingWorkbenchStore(s => s.zones);
  const riskPoints = useRiskMappingWorkbenchStore(s => s.riskPoints);
  const pendingRegions = useRiskMappingWorkbenchStore(s => s.pendingRegions);
  const texts = useRiskMappingWorkbenchStore(s => s.texts);
  const selectedZoneId = useRiskMappingWorkbenchStore(s => s.selectedZoneId);
  const selectedRegionId = useRiskMappingWorkbenchStore(s => s.selectedRegionId);
  const selectedRiskPointId = useRiskMappingWorkbenchStore(s => s.selectedRiskPointId);
  const selectedTextId = useRiskMappingWorkbenchStore(s => s.selectedTextId);
  const setState = useRiskMappingWorkbenchStore.setState;
  const setSnapshot = useRiskMappingWorkbenchStore.getState().setSnapshot;
  const commit = useRiskMappingWorkbenchStore.getState().commit;
  const [textContent, setTextContent] = useState("");
  const [regionZoneId, setRegionZoneId] = useState<string | null>(null);
  const [targetZoneId, setTargetZoneId] = useState<string | null>(null);
  const [pointDraft, setPointDraft] = useState<RiskPointDraft | null>(null);
  const zone = zones.find(z => z.id === selectedZoneId);
  const selectedPending = selectedRegionId?.startsWith("pending:")
    ? pendingRegions.find(r => r.id === selectedRegionId.slice("pending:".length)) ?? null
    : null;
  const selectedZonePolygon = selectedRegionId?.startsWith("zone:")
    ? (() => {
        const body = selectedRegionId.slice("zone:".length);
        const separator = body.indexOf(":");
        const zid = body.slice(0, separator);
        const pid = body.slice(separator + 1);
        return {
          zoneId: zid,
          polygonId: pid,
          zone: zones.find(z => z.id === zid) ?? null,
          polygon: zones.find(z => z.id === zid)?.floor_plan_polygon?.polygons.find(p => p.id === pid) ?? null,
        };
      })()
    : null;
  const selectedRiskPoint = riskPoints.find(p => p.id === selectedRiskPointId) ?? null;
  const selectedText = texts.find(t => t.id === selectedTextId) ?? null;

  useEffect(() => {
    setRegionZoneId(selectedPending ? (selectedZoneId ?? zones[0]?.id ?? null) : null);
  }, [selectedRegionId, selectedPending, selectedZoneId, zones]);

  useEffect(() => {
    setTargetZoneId(null);
  }, [selectedRegionId]);

  useEffect(() => {
    const point = riskPoints.find(p => p.id === selectedRiskPointId);
    setPointDraft(
      point
        ? {
            id: point.id,
            name: point.name,
            category: point.category,
            location: point.location,
            description: point.description,
            location_x: point.location_x,
            location_y: point.location_y,
            zone_id: point.zone_id,
          }
        : null,
    );
  }, [selectedRiskPointId, riskPoints]);

  const updateZone = (patch: Partial<WorkbenchZone>) => {
    if (!zone) return;
    commit();
    setSnapshot({ zones: useRiskMappingWorkbenchStore.getState().zones.map(z => (z.id === zone.id ? { ...z, ...patch } : z)) });
  };

  const bindSelectedPending = () => {
    if (!selectedPending || !regionZoneId) return;
    const target = zones.find(z => z.id === regionZoneId);
    if (!target) return;
    const polygon = target.floor_plan_polygon || { version: 2, color_source: "auto" as const, color: null, polygons: [] };
    commit();
    setSnapshot({
      zones: useRiskMappingWorkbenchStore.getState().zones.map(z =>
        z.id === target.id
          ? {
              ...z,
              floor_plan_polygon: {
                ...polygon,
                polygons: [
                  ...polygon.polygons,
                  {
                    id: selectedPending.id,
                    label: `${target.name}-区域${polygon.polygons.length + 1}`,
                    points: selectedPending.points,
                  },
                ],
              },
            }
          : z,
      ),
      pendingRegions: useRiskMappingWorkbenchStore.getState().pendingRegions.filter(r => r.id !== selectedPending.id),
    });
    setState({ selectedRegionId: null });
  };

  const moveSelectedPolygon = () => {
    if (!selectedZonePolygon || !targetZoneId || targetZoneId === selectedZonePolygon.zoneId) return;
    const sourceZone = zones.find(z => z.id === selectedZonePolygon.zoneId);
    const targetZone = zones.find(z => z.id === targetZoneId);
    const polygon = sourceZone?.floor_plan_polygon?.polygons.find(p => p.id === selectedZonePolygon.polygonId);
    if (!sourceZone || !targetZone || !polygon) return;
    const targetPolygon = targetZone.floor_plan_polygon || { version: 2, color_source: "auto" as const, color: null, polygons: [] };
    const targetPolygonId = targetPolygon.polygons.some(p => p.id === polygon.id)
      ? `${polygon.id}-moved-${Date.now().toString(36)}`
      : polygon.id;
    commit();
    setSnapshot({
      zones: useRiskMappingWorkbenchStore.getState().zones.map(z => {
        if (z.id === sourceZone.id && z.floor_plan_polygon) {
          return {
            ...z,
            floor_plan_polygon: {
              ...z.floor_plan_polygon,
              polygons: z.floor_plan_polygon.polygons.filter(p => p.id !== polygon.id),
            },
          };
        }
        if (z.id === targetZone.id) {
          return {
            ...z,
            floor_plan_polygon: {
              ...targetPolygon,
              polygons: [...targetPolygon.polygons, { ...polygon, id: targetPolygonId }],
            },
          };
        }
        return z;
      }),
    });
    setState({ selectedRegionId: null });
  };

  const saveRiskPoint = () => {
    if (!pointDraft) return;
    commit();
    setSnapshot({
      riskPoints: useRiskMappingWorkbenchStore.getState().riskPoints.map(p =>
        p.id === pointDraft.id
          ? {
              ...p,
              name: pointDraft.name.trim() || p.name,
              category: pointDraft.category,
              location: pointDraft.location,
              description: pointDraft.description,
              location_x: pointDraft.location_x ?? 50,
              location_y: pointDraft.location_y ?? 50,
              zone_id: pointDraft.zone_id,
              updated_at: new Date().toISOString(),
            }
          : p,
      ),
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
    setSnapshot({ texts: [...useRiskMappingWorkbenchStore.getState().texts, item] });
    setTextContent("");
    setState({ selectedTextId: item.id, selectedRiskPointId: null, selectedRegionId: null });
  };

  return (
    <div style={{ background: "#fff", borderRadius: 8, padding: 12, overflow: "auto" }}>
      <h4 style={{ fontSize: 14, marginBottom: 12 }}>属性</h4>

      {selectedPending && (
        <div style={{ border: "1px dashed #fa8c16", borderRadius: 6, padding: 8, marginBottom: 12 }}>
          <strong>待绑定区域</strong>
          <div style={{ fontSize: 12, color: "#8c8c8c", margin: "4px 0" }}>{selectedPending.points.length} 个顶点</div>
          <Select
            style={{ width: "100%" }}
            placeholder="选择所属分区"
            value={regionZoneId || undefined}
            options={zones.map(z => ({ value: z.id, label: z.name }))}
            onChange={setRegionZoneId}
          />
          <Button block type="primary" style={{ marginTop: 6 }} disabled={!regionZoneId} onClick={bindSelectedPending}>
            绑定到分区
          </Button>
          <Button
            danger
            block
            style={{ marginTop: 6 }}
            icon={<DeleteOutlined />}
            onClick={() => {
              commit();
              useRiskMappingWorkbenchStore.getState().deletePendingRegion(selectedPending.id);
            }}
          >
            删除区域
          </Button>
        </div>
      )}

      {selectedZonePolygon?.polygon && selectedZonePolygon.zone && (
        <div style={{ border: "1px solid #d9d9d9", borderRadius: 6, padding: 8, marginBottom: 12 }}>
          <strong>已绑定区域</strong>
          <div style={{ fontSize: 12, color: "#8c8c8c", margin: "4px 0" }}>
            当前分区：{selectedZonePolygon.zone.name} · {selectedZonePolygon.polygon.points.length} 个顶点
          </div>
          <Select
            style={{ width: "100%" }}
            placeholder="移动到其他分区"
            value={targetZoneId || undefined}
            options={zones.map(z => ({ value: z.id, label: z.name }))}
            onChange={setTargetZoneId}
          />
          <Button
            block
            style={{ marginTop: 6 }}
            disabled={!targetZoneId || targetZoneId === selectedZonePolygon.zoneId}
            onClick={moveSelectedPolygon}
          >
            移动到分区
          </Button>
          <Button
            danger
            block
            style={{ marginTop: 6 }}
            icon={<DeleteOutlined />}
            onClick={() => {
              commit();
              useRiskMappingWorkbenchStore.getState().deleteZonePolygon(
                selectedZonePolygon.zoneId,
                selectedZonePolygon.polygonId,
              );
            }}
          >
            删除区域
          </Button>
        </div>
      )}

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
      {selectedRiskPoint && pointDraft && (
        <div style={{ border: "1px solid #1677ff", borderRadius: 6, padding: 8, marginBottom: 8 }}>
          <Input
            value={pointDraft.name}
            onChange={e => setPointDraft({ ...pointDraft, name: e.target.value })}
            placeholder="风险点名称"
          />
          <Input
            style={{ marginTop: 6 }}
            value={pointDraft.category || ""}
            onChange={e => setPointDraft({ ...pointDraft, category: e.target.value })}
            placeholder="类别"
          />
          <Input
            style={{ marginTop: 6 }}
            value={pointDraft.location || ""}
            onChange={e => setPointDraft({ ...pointDraft, location: e.target.value })}
            placeholder="位置描述"
          />
          <Input.TextArea
            style={{ marginTop: 6 }}
            rows={2}
            value={pointDraft.description || ""}
            onChange={e => setPointDraft({ ...pointDraft, description: e.target.value })}
            placeholder="说明"
          />
          <Space.Compact style={{ width: "100%", marginTop: 6 }}>
            <InputNumber
              style={{ width: "50%" }}
              min={0}
              max={100}
              value={pointDraft.location_x ?? 50}
              onChange={v => setPointDraft({ ...pointDraft, location_x: v ?? 50 })}
            />
            <InputNumber
              style={{ width: "50%" }}
              min={0}
              max={100}
              value={pointDraft.location_y ?? 50}
              onChange={v => setPointDraft({ ...pointDraft, location_y: v ?? 50 })}
            />
          </Space.Compact>
          <Select
            style={{ width: "100%", marginTop: 6 }}
            placeholder="绑定分区"
            value={pointDraft.zone_id || undefined}
            options={zones.map(z => ({ value: z.id, label: z.name }))}
            onChange={zone_id => setPointDraft({ ...pointDraft, zone_id })}
          />
          <Button block type="primary" style={{ marginTop: 6 }} onClick={saveRiskPoint}>
            保存风险点
          </Button>
          <Button
            danger
            block
            style={{ marginTop: 6 }}
            icon={<DeleteOutlined />}
            onClick={() => {
              commit();
              useRiskMappingWorkbenchStore.getState().deleteRiskPoint(selectedRiskPoint.id);
            }}
          >
            删除风险点
          </Button>
        </div>
      )}
      {riskPoints.map(p => (
        <div
          key={p.id}
          style={{
            marginTop: 4,
            padding: 4,
            borderRadius: 4,
            cursor: "pointer",
            border: selectedRiskPointId === p.id ? "1px solid #1677ff" : "1px solid transparent",
          }}
          onClick={() => setState({ selectedRiskPointId: p.id, selectedRegionId: null, selectedTextId: null })}
        >
          <div style={{ display: "flex", justifyContent: "space-between" }}>
            <span>{p.name}</span>
            <Button
              size="small"
              type="text"
              icon={<DeleteOutlined />}
              onClick={e => {
                e.stopPropagation();
                commit();
                useRiskMappingWorkbenchStore.getState().deleteRiskPoint(p.id);
              }}
            />
          </div>
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
          onClick={() => setState({ selectedTextId: t.id, selectedRiskPointId: null, selectedRegionId: null })}
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            fontSize: 12,
            marginTop: 4,
            cursor: "pointer",
            border: selectedTextId === t.id ? "1px solid #1677ff" : "1px solid transparent",
            borderRadius: 4,
            padding: "2px 4px",
          }}
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
            onClick={e => {
              e.stopPropagation();
              commit();
              useRiskMappingWorkbenchStore.getState().deleteText(t.id);
            }}
          />
        </div>
      ))}
      {selectedText && (
        <Button
          block
          style={{ marginTop: 8 }}
          onClick={() => {
            commit();
            useRiskMappingWorkbenchStore.getState().deleteText(selectedText.id);
          }}
        >
          删除选中文字
        </Button>
      )}
    </div>
  );
}
