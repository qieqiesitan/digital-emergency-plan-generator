import { useEffect, useRef, useState } from "react";
import { Stage, Layer, Image as KonvaImage, Line, Rect, Text as KonvaText } from "react-konva";
import type { KonvaEventObject } from "konva/lib/Node";
import { Modal, Input, InputNumber, Button, Space } from "antd";
import { DeleteOutlined } from "@ant-design/icons";
import { useRiskMappingWorkbenchStore } from "@/store/riskMappingWorkbenchStore";
import { clampPoint, pointsToKonva, toCanvasX, toCanvasY, toPercent } from "@/utils/riskMappingGeometry";
import type { RiskPolygonPoint, RiskCanvasText } from "@/types/riskMappingWorkbench";
import type { RiskObject } from "@/types/riskManagement";
import WorkbenchRiskPointLayer from "./WorkbenchRiskPointLayer";

const STAGE_WIDTH = 1200;
const STAGE_HEIGHT = 900;

interface LoadedImage {
  url: string;
  image: HTMLImageElement;
}

const samePoint = (a: RiskPolygonPoint, b: RiskPolygonPoint) => a.x === b.x && a.y === b.y;

const dedupeTail = (points: RiskPolygonPoint[]) => {
  const out = [...points];
  while (out.length > 1 && samePoint(out[out.length - 1], out[out.length - 2])) out.pop();
  return out;
};

const nextLocalId = (prefix: string) => `${prefix}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;

export default function WorkbenchCanvas() {
  const zones = useRiskMappingWorkbenchStore(s => s.zones);
  const pendingRegions = useRiskMappingWorkbenchStore(s => s.pendingRegions);
  const texts = useRiskMappingWorkbenchStore(s => s.texts);
  const riskPoints = useRiskMappingWorkbenchStore(s => s.riskPoints);
  const tool = useRiskMappingWorkbenchStore(s => s.tool);
  const gridEnabled = useRiskMappingWorkbenchStore(s => s.gridEnabled);
  const snapEnabled = useRiskMappingWorkbenchStore(s => s.snapEnabled);
  const guideEnabled = useRiskMappingWorkbenchStore(s => s.guideEnabled);
  const floor = useRiskMappingWorkbenchStore(s => s.floors.find(f => f.id === s.currentFloorId));
  const currentFloorId = useRiskMappingWorkbenchStore(s => s.currentFloorId);
  const setSnapshot = useRiskMappingWorkbenchStore.getState().setSnapshot;
  const commit = useRiskMappingWorkbenchStore.getState().commit;
  const [draftPoints, setDraftPoints] = useState<RiskPolygonPoint[]>([]);
  const [draftStart, setDraftStart] = useState<RiskPolygonPoint | null>(null);
  const [draftEnd, setDraftEnd] = useState<RiskPolygonPoint | null>(null);
  const [isDrawing, setIsDrawing] = useState(false);
  const [loadedImage, setLoadedImage] = useState<LoadedImage | null>(null);
  const [editingTextId, setEditingTextId] = useState<string | null>(null);
  const [editContent, setEditContent] = useState("");
  const [editFontSize, setEditFontSize] = useState(14);
  const [editColor, setEditColor] = useState("#333333");
  const zoneDragOriginRef = useRef<Map<string, RiskPolygonPoint[]>>(new Map());
  const pendingDragOriginRef = useRef<Map<string, RiskPolygonPoint[]>>(new Map());

  useEffect(() => {
    const url = floor?.floor_plan_url;
    if (!url) return;
    const img = new window.Image();
    img.onload = () => setLoadedImage({ url, image: img });
    img.src = url;
    return () => {
      img.onload = null;
    };
  }, [floor?.floor_plan_url]);

  const image = loadedImage && loadedImage.url === floor?.floor_plan_url ? loadedImage.image : null;
  const canvasWidth = floor?.canvas_width || (image ? image.naturalWidth : STAGE_WIDTH);
  const canvasHeight = floor?.canvas_height || (image ? image.naturalHeight : STAGE_HEIGHT);

  const pointFromEvent = (e: KonvaEventObject<MouseEvent>): RiskPolygonPoint => {
    const stage = e.target.getStage?.() ?? null;
    const pos = stage?.getPointerPosition?.() ?? null;
    const rawX = pos ? toPercent(pos.x, canvasWidth) : toPercent(e.evt.offsetX ?? 0, canvasWidth);
    const rawY = pos ? toPercent(pos.y, canvasHeight) : toPercent(e.evt.offsetY ?? 0, canvasHeight);
    const rounded = (v: number) => (snapEnabled ? Math.round(v / 5) * 5 : Math.round(v * 100) / 100);
    return { x: Math.min(100, Math.max(0, rounded(rawX))), y: Math.min(100, Math.max(0, rounded(rawY))) };
  };

  const addPending = (points: RiskPolygonPoint[]) => {
    const region = {
      id: nextLocalId("pending"),
      floor_id: currentFloorId,
      points,
      created_at: new Date().toISOString(),
    };
    commit();
    setSnapshot({ pendingRegions: [...useRiskMappingWorkbenchStore.getState().pendingRegions, region] });
  };

  const handleClick = (e: KonvaEventObject<MouseEvent>) => {
    if (tool === "select" || tool === "freehand" || tool === "rect") return;
    const p = pointFromEvent(e);
    if (tool === "polygon") {
      setDraftPoints(prev => [...prev, p]);
      return;
    }
    if (tool === "risk-point") {
      const riskPoint: RiskObject = {
        id: nextLocalId("new-point"),
        enterprise_id: "",
        zone_id: null,
        floor_id: currentFloorId,
        name: "新风险点",
        category: null,
        location: null,
        location_x: p.x,
        location_y: p.y,
        description: null,
        image_url: null,
        is_risk_point: true,
        sort_order: riskPoints.length,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        unit_count: 0,
      };
      commit();
      setSnapshot({ riskPoints: [...useRiskMappingWorkbenchStore.getState().riskPoints, riskPoint] });
      return;
    }
    if (tool === "text") {
      const item: RiskCanvasText = {
        id: nextLocalId("text"),
        content: "双击编辑文字",
        x: p.x,
        y: p.y,
        font_size: 14,
        color: "#333333",
        rotation: 0,
        sort_order: texts.length,
      };
      commit();
      setSnapshot({ texts: [...useRiskMappingWorkbenchStore.getState().texts, item] });
    }
  };

  const finishDrawing = () => {
    if (tool === "polygon" || tool === "freehand") {
      const cleaned = dedupeTail(draftPoints);
      if (cleaned.length >= 3) addPending(cleaned);
    }
    setDraftPoints([]);
    setDraftStart(null);
    setIsDrawing(false);
  };

  const handleMouseDown = (e: KonvaEventObject<MouseEvent>) => {
    if (tool === "rect") {
      const p = pointFromEvent(e);
      setIsDrawing(true);
      setDraftStart(p);
      setDraftEnd(p);
      return;
    }
    if (tool === "freehand") {
      setIsDrawing(true);
      setDraftPoints([pointFromEvent(e)]);
    }
  };

  const handleMouseMove = (e: KonvaEventObject<MouseEvent>) => {
    if (tool === "rect" && isDrawing) {
      setDraftEnd(pointFromEvent(e));
      return;
    }
    if (tool === "freehand" && isDrawing) {
      setDraftPoints(prev => [...prev, pointFromEvent(e)]);
    }
  };

  const handleMouseUp = () => {
    if (tool === "rect" && isDrawing) {
      if (draftStart && draftEnd) {
        const x1 = Math.min(draftStart.x, draftEnd.x);
        const x2 = Math.max(draftStart.x, draftEnd.x);
        const y1 = Math.min(draftStart.y, draftEnd.y);
        const y2 = Math.max(draftStart.y, draftEnd.y);
        if (x2 - x1 >= 0.1 && y2 - y1 >= 0.1) {
          addPending([
            { x: x1, y: y1 },
            { x: x2, y: y1 },
            { x: x2, y: y2 },
            { x: x1, y: y2 },
          ]);
        }
      }
      setDraftStart(null);
      setDraftEnd(null);
      setIsDrawing(false);
      return;
    }
    if (tool === "freehand" && isDrawing) {
      if (draftPoints.length >= 3) {
        finishDrawing();
      } else {
        setDraftPoints([]);
        setIsDrawing(false);
      }
    }
  };

  const editingText = editingTextId ? texts.find(t => t.id === editingTextId) : null;

  return (
    <>
      <div data-testid="workbench-canvas">
        <Stage
          width={canvasWidth}
          height={canvasHeight}
          style={{ maxWidth: "100%", maxHeight: "100%" }}
          onClick={handleClick}
          onDblClick={finishDrawing}
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
        >
          <Layer>
        {image && <KonvaImage image={image} x={0} y={0} width={canvasWidth} height={canvasHeight} />}
        {gridEnabled &&
          Array.from({ length: Math.floor(canvasWidth / 100) + 1 }, (_, i) => (
            <Line key={`gv-${i}`} points={[i * 100, 0, i * 100, canvasHeight]} stroke="#e8e8e8" strokeWidth={1} />
          ))}
        {gridEnabled &&
          Array.from({ length: Math.floor(canvasHeight / 100) + 1 }, (_, i) => (
            <Line key={`gh-${i}`} points={[0, i * 100, canvasWidth, i * 100]} stroke="#e8e8e8" strokeWidth={1} />
          ))}
        {guideEnabled && (
          <>
            <Line points={[canvasWidth / 2, 0, canvasWidth / 2, canvasHeight]} stroke="#f5222d" dash={[8, 6]} strokeWidth={1} opacity={0.45} listening={false} />
            <Line points={[0, canvasHeight / 2, canvasWidth, canvasHeight / 2]} stroke="#f5222d" dash={[8, 6]} strokeWidth={1} opacity={0.45} listening={false} />
          </>
        )}
        {pendingRegions.map(r => (
          <Line
            key={r.id}
            points={pointsToKonva(r.points, canvasWidth, canvasHeight)}
            closed
            stroke="#fa8c16"
            dash={[6, 4]}
            strokeWidth={2}
            draggable={tool === "select"}
            onDragStart={() => {
              pendingDragOriginRef.current.set(r.id, r.points);
            }}
            onDragEnd={e => {
              const origin = pendingDragOriginRef.current.get(r.id) ?? r.points;
              const dx = (e.target.x() / canvasWidth) * 100;
              const dy = (e.target.y() / canvasHeight) * 100;
              const moved = origin.map(pt => clampPoint({ x: pt.x + dx, y: pt.y + dy }));
              pendingDragOriginRef.current.delete(r.id);
              e.target.position({ x: 0, y: 0 });
              commit();
              setSnapshot({
                pendingRegions: useRiskMappingWorkbenchStore.getState().pendingRegions.map(item =>
                  item.id === r.id ? { ...item, points: moved } : item,
                ),
              });
            }}
          />
        ))}
        {draftStart && draftEnd && (
          <Rect
            x={Math.min(toCanvasX(draftStart.x, canvasWidth), toCanvasX(draftEnd.x, canvasWidth))}
            y={Math.min(toCanvasY(draftStart.y, canvasHeight), toCanvasY(draftEnd.y, canvasHeight))}
            width={Math.abs(toCanvasX(draftEnd.x, canvasWidth) - toCanvasX(draftStart.x, canvasWidth))}
            height={Math.abs(toCanvasY(draftEnd.y, canvasHeight) - toCanvasY(draftStart.y, canvasHeight))}
            dash={[4, 4]}
            stroke="#1677ff"
            fill="rgba(22, 119, 255, 0.08)"
          />
        )}
        {draftPoints.length > 0 && (
          <Line
            points={pointsToKonva(draftPoints, canvasWidth, canvasHeight)}
            closed={tool === "polygon"}
            stroke="#1677ff"
            dash={[4, 4]}
            strokeWidth={2}
          />
        )}
        {zones.map(z =>
          (z.floor_plan_polygon?.polygons || []).map(p => (
            <Line
              key={p.id}
              points={pointsToKonva(p.points, canvasWidth, canvasHeight)}
              closed
              fill={z.effective_color || "#d9d9d9"}
              opacity={0.35}
              stroke={z.effective_color || "#d9d9d9"}
              strokeWidth={2}
              draggable={tool === "select"}
              onDragStart={() => {
                zoneDragOriginRef.current.set(`${z.id}:${p.id}`, p.points);
              }}
              onDragEnd={e => {
                const origin = zoneDragOriginRef.current.get(`${z.id}:${p.id}`) ?? p.points;
                const dx = (e.target.x() / canvasWidth) * 100;
                const dy = (e.target.y() / canvasHeight) * 100;
                const moved = origin.map(pt => clampPoint({ x: pt.x + dx, y: pt.y + dy }));
                zoneDragOriginRef.current.delete(`${z.id}:${p.id}`);
                e.target.position({ x: 0, y: 0 });
                commit();
                setSnapshot({
                  zones: useRiskMappingWorkbenchStore.getState().zones.map(item => {
                    if (item.id !== z.id || !item.floor_plan_polygon) return item;
                    return {
                      ...item,
                      floor_plan_polygon: {
                        ...item.floor_plan_polygon,
                        polygons: item.floor_plan_polygon.polygons.map(pp =>
                          pp.id === p.id ? { ...pp, points: moved } : pp,
                        ),
                      },
                    };
                  }),
                });
              }}
            />
          )),
        )}
        {texts.map(t => (
          <KonvaText
            key={t.id}
            x={toCanvasX(t.x, canvasWidth)}
            y={toCanvasY(t.y, canvasHeight)}
            text={t.content}
            fontSize={t.font_size}
            fill={t.color}
            rotation={t.rotation}
            draggable={tool === "select"}
            onDragEnd={e => {
              commit();
              setSnapshot({
                texts: useRiskMappingWorkbenchStore.getState().texts.map(item =>
                  item.id === t.id
                    ? {
                        ...item,
                        x: Math.round(Math.min(100, Math.max(0, (e.target.x() / canvasWidth) * 100)) * 100) / 100,
                        y: Math.round(Math.min(100, Math.max(0, (e.target.y() / canvasHeight) * 100)) * 100) / 100,
                      }
                    : item,
                ),
              });
            }}
            onDblClick={e => {
              e.cancelBubble = true;
              setEditingTextId(t.id);
              setEditContent(t.content);
              setEditFontSize(t.font_size);
              setEditColor(t.color);
            }}
          />
        ))}
        <WorkbenchRiskPointLayer />
        </Layer>
        </Stage>
      </div>
      <Modal
        title="编辑文字标注"
        open={!!editingText}
        onCancel={() => setEditingTextId(null)}
        onOk={() => {
          if (!editingText) return;
          commit();
          setSnapshot({
            texts: useRiskMappingWorkbenchStore.getState().texts.map(t =>
              t.id === editingText.id
                ? { ...t, content: editContent.trim() || t.content, font_size: editFontSize, color: editColor }
                : t,
            ),
          });
          setEditingTextId(null);
        }}
        okText="保存"
        cancelText="取消"
      >
        {editingText && (
          <Space direction="vertical" style={{ width: "100%" }}>
            <div>
              <div style={{ marginBottom: 4, fontSize: 12, color: "#666" }}>内容</div>
              <Input value={editContent} onChange={e => setEditContent(e.target.value)} />
            </div>
            <div>
              <div style={{ marginBottom: 4, fontSize: 12, color: "#666" }}>字号</div>
              <InputNumber min={8} max={72} value={editFontSize} onChange={v => setEditFontSize(v ?? 14)} style={{ width: "100%" }} />
            </div>
            <div>
              <div style={{ marginBottom: 4, fontSize: 12, color: "#666" }}>颜色</div>
              <Input type="color" value={editColor} onChange={e => setEditColor(e.target.value)} style={{ width: "100%", height: 32 }} />
            </div>
            <Button
              danger
              block
              icon={<DeleteOutlined />}
              onClick={() => {
                commit();
                setSnapshot({ texts: useRiskMappingWorkbenchStore.getState().texts.filter(t => t.id !== editingText.id) });
                setEditingTextId(null);
              }}
            >
              删除标注
            </Button>
          </Space>
        )}
      </Modal>
    </>
  );
}
