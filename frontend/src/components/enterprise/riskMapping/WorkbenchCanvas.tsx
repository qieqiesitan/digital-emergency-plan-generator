import { useEffect, useState } from "react";
import { Stage, Layer, Image as KonvaImage, Line, Rect, Text as KonvaText } from "react-konva";
import { useRiskMappingWorkbenchStore } from "@/store/riskMappingWorkbenchStore";
import { pointsToKonva, toCanvasX, toCanvasY, toPercent } from "@/utils/riskMappingGeometry";
import type { RiskPolygonPoint, RiskCanvasText } from "@/types/riskMappingWorkbench";
import type { RiskObject } from "@/types/riskManagement";
import WorkbenchRiskPointLayer from "./WorkbenchRiskPointLayer";

const STAGE_WIDTH = 1200;
const STAGE_HEIGHT = 900;

const samePoint = (a: RiskPolygonPoint, b: RiskPolygonPoint) => a.x === b.x && a.y === b.y;

const dedupeTail = (points: RiskPolygonPoint[]) => {
  const out = [...points];
  while (out.length > 1 && samePoint(out[out.length - 1], out[out.length - 2])) out.pop();
  return out;
};

export default function WorkbenchCanvas() {
  const zones = useRiskMappingWorkbenchStore(s => s.zones);
  const pendingRegions = useRiskMappingWorkbenchStore(s => s.pendingRegions);
  const texts = useRiskMappingWorkbenchStore(s => s.texts);
  const riskPoints = useRiskMappingWorkbenchStore(s => s.riskPoints);
  const tool = useRiskMappingWorkbenchStore(s => s.tool);
  const gridEnabled = useRiskMappingWorkbenchStore(s => s.gridEnabled);
  const snapEnabled = useRiskMappingWorkbenchStore(s => s.snapEnabled);
  const floor = useRiskMappingWorkbenchStore(s => s.floors.find(f => f.id === s.currentFloorId));
  const currentFloorId = useRiskMappingWorkbenchStore(s => s.currentFloorId);
  const setSnapshot = useRiskMappingWorkbenchStore.getState().setSnapshot;
  const commit = useRiskMappingWorkbenchStore.getState().commit;
  const [draftPoints, setDraftPoints] = useState<RiskPolygonPoint[]>([]);
  const [draftStart, setDraftStart] = useState<RiskPolygonPoint | null>(null);
  const [isDrawing, setIsDrawing] = useState(false);
  const [image, setImage] = useState<HTMLImageElement | null>(null);

  useEffect(() => {
    if (!floor?.floor_plan_url) {
      setImage(null);
      return;
    }
    const img = new window.Image();
    img.onload = () => setImage(img);
    img.src = floor.floor_plan_url;
    return () => {
      img.onload = null;
    };
  }, [floor?.floor_plan_url]);

  const pointFromEvent = (e: any): RiskPolygonPoint => {
    const stage = e.target.getStage?.() ?? null;
    const pos = stage?.getPointerPosition?.() ?? null;
    const rawX = pos ? toPercent(pos.x, STAGE_WIDTH) : toPercent(e.evt.offsetX ?? 0, STAGE_WIDTH);
    const rawY = pos ? toPercent(pos.y, STAGE_HEIGHT) : toPercent(e.evt.offsetY ?? 0, STAGE_HEIGHT);
    const rounded = (v: number) => (snapEnabled ? Math.round(v / 5) * 5 : Math.round(v * 100) / 100);
    return { x: Math.min(100, Math.max(0, rounded(rawX))), y: Math.min(100, Math.max(0, rounded(rawY))) };
  };

  const addPending = (points: RiskPolygonPoint[]) => {
    const region = {
      id: `pending-${Date.now()}`,
      floor_id: currentFloorId,
      points,
      created_at: new Date().toISOString(),
    };
    setSnapshot({ pendingRegions: [...useRiskMappingWorkbenchStore.getState().pendingRegions, region] });
    commit();
  };

  const handleClick = (e: any) => {
    if (tool === "select" || tool === "freehand") return;
    const p = pointFromEvent(e);
    if (tool === "rect") {
      if (!draftStart) {
        setDraftStart(p);
        return;
      }
      addPending([draftStart, { x: p.x, y: draftStart.y }, p, { x: draftStart.x, y: p.y }]);
      setDraftStart(null);
      return;
    }
    if (tool === "polygon") {
      setDraftPoints(prev => [...prev, p]);
      return;
    }
    if (tool === "risk-point") {
      const riskPoint: RiskObject = {
        id: `new-point-${Date.now()}`,
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
      setSnapshot({ riskPoints: [...useRiskMappingWorkbenchStore.getState().riskPoints, riskPoint] });
      commit();
      return;
    }
    if (tool === "text") {
      const item: RiskCanvasText = {
        id: `text-${Date.now()}`,
        content: "双击编辑文字",
        x: p.x,
        y: p.y,
        font_size: 14,
        color: "#333333",
        rotation: 0,
        sort_order: texts.length,
      };
      setSnapshot({ texts: [...useRiskMappingWorkbenchStore.getState().texts, item] });
      commit();
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

  const handleMouseDown = (e: any) => {
    if (tool === "freehand") {
      setIsDrawing(true);
      setDraftPoints([pointFromEvent(e)]);
    }
  };

  const handleMouseMove = (e: any) => {
    if (tool === "freehand" && isDrawing) {
      setDraftPoints(prev => [...prev, pointFromEvent(e)]);
    }
  };

  const handleMouseUp = () => {
    if (tool === "freehand" && isDrawing) {
      if (draftPoints.length >= 3) {
        finishDrawing();
      } else {
        setDraftPoints([]);
        setIsDrawing(false);
      }
    }
  };

  return (
    <Stage
      width={STAGE_WIDTH}
      height={STAGE_HEIGHT}
      style={{ maxWidth: "100%", maxHeight: "100%" }}
      onClick={handleClick}
      onDblClick={finishDrawing}
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
    >
      <Layer>
        {image && <KonvaImage image={image} x={0} y={0} width={STAGE_WIDTH} height={STAGE_HEIGHT} />}
        {gridEnabled &&
          Array.from({ length: 13 }, (_, i) => (
            <Line key={`gv-${i}`} points={[i * 100, 0, i * 100, STAGE_HEIGHT]} stroke="#e8e8e8" strokeWidth={1} />
          ))}
        {gridEnabled &&
          Array.from({ length: 10 }, (_, i) => (
            <Line key={`gh-${i}`} points={[0, i * 100, STAGE_WIDTH, i * 100]} stroke="#e8e8e8" strokeWidth={1} />
          ))}
        {pendingRegions.map(r => (
          <Line
            key={r.id}
            points={pointsToKonva(r.points, STAGE_WIDTH, STAGE_HEIGHT)}
            closed
            stroke="#fa8c16"
            dash={[6, 4]}
            strokeWidth={2}
          />
        ))}
        {draftStart && (
          <Rect
            x={toCanvasX(draftStart.x, STAGE_WIDTH)}
            y={toCanvasY(draftStart.y, STAGE_HEIGHT)}
            width={100}
            height={100}
            dash={[4, 4]}
            stroke="#1677ff"
          />
        )}
        {draftPoints.length > 0 && (
          <Line
            points={pointsToKonva(draftPoints, STAGE_WIDTH, STAGE_HEIGHT)}
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
              points={pointsToKonva(p.points, STAGE_WIDTH, STAGE_HEIGHT)}
              closed
              fill={z.effective_color || "#d9d9d9"}
              opacity={0.35}
              stroke={z.effective_color || "#d9d9d9"}
              strokeWidth={2}
              draggable
            />
          )),
        )}
        {texts.map(t => (
          <KonvaText
            key={t.id}
            x={toCanvasX(t.x, STAGE_WIDTH)}
            y={toCanvasY(t.y, STAGE_HEIGHT)}
            text={t.content}
            fontSize={t.font_size}
            fill={t.color}
            rotation={t.rotation}
          />
        ))}
        <WorkbenchRiskPointLayer />
      </Layer>
    </Stage>
  );
}
