import { useEffect, useState } from "react";
import { Stage, Layer, Image as KonvaImage, Line, Rect, Text as KonvaText } from "react-konva";
import type { KonvaEventObject } from "konva/lib/Node";
import { useRiskMappingWorkbenchStore } from "@/store/riskMappingWorkbenchStore";
import { pointsToKonva, toCanvasX, toCanvasY, toPercent } from "@/utils/riskMappingGeometry";
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
  const [loadedImage, setLoadedImage] = useState<LoadedImage | null>(null);

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
      id: `pending-${Date.now()}`,
      floor_id: currentFloorId,
      points,
      created_at: new Date().toISOString(),
    };
    commit();
    setSnapshot({ pendingRegions: [...useRiskMappingWorkbenchStore.getState().pendingRegions, region] });
  };

  const handleClick = (e: KonvaEventObject<MouseEvent>) => {
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
      commit();
      setSnapshot({ riskPoints: [...useRiskMappingWorkbenchStore.getState().riskPoints, riskPoint] });
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
    if (tool === "freehand") {
      setIsDrawing(true);
      setDraftPoints([pointFromEvent(e)]);
    }
  };

  const handleMouseMove = (e: KonvaEventObject<MouseEvent>) => {
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
        {pendingRegions.map(r => (
          <Line
            key={r.id}
            points={pointsToKonva(r.points, canvasWidth, canvasHeight)}
            closed
            stroke="#fa8c16"
            dash={[6, 4]}
            strokeWidth={2}
          />
        ))}
        {draftStart && (
          <Rect
            x={toCanvasX(draftStart.x, canvasWidth)}
            y={toCanvasY(draftStart.y, canvasHeight)}
            width={100}
            height={100}
            dash={[4, 4]}
            stroke="#1677ff"
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
              draggable
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
          />
        ))}
        <WorkbenchRiskPointLayer />
      </Layer>
    </Stage>
  );
}
