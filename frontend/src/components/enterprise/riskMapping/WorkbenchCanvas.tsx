import { Fragment, useEffect, useRef, useState } from "react";
import {
  Stage,
  Layer,
  Image as KonvaImage,
  Line,
  Rect,
  Circle as KonvaCircle,
  Text as KonvaText,
} from "react-konva";
import type { KonvaEventObject } from "konva/lib/Node";
import { Modal, Input, InputNumber, Button, Space } from "antd";
import { DeleteOutlined } from "@ant-design/icons";
import { useRiskMappingWorkbenchStore } from "@/store/riskMappingWorkbenchStore";
import {
  clampPoint,
  cubicBezierPoints,
  ellipsePoints,
  pointsToKonva,
  polygonCentroid,
  toCanvasX,
  toCanvasY,
  toPercent,
} from "@/utils/riskMappingGeometry";
import type { RiskPolygonPoint, RiskCanvasText } from "@/types/riskMappingWorkbench";
import type { RiskObject } from "@/types/riskManagement";
import WorkbenchRiskPointLayer from "./WorkbenchRiskPointLayer";

const STAGE_WIDTH = 1200;
const STAGE_HEIGHT = 900;

interface LoadedImage {
  url: string;
  image: HTMLImageElement;
}

interface PenAnchor {
  point: RiskPolygonPoint;
  handle: RiskPolygonPoint | null;
}

const samePoint = (a: RiskPolygonPoint, b: RiskPolygonPoint) => a.x === b.x && a.y === b.y;

const dedupeTail = (points: RiskPolygonPoint[]) => {
  const out = [...points];
  while (out.length > 1 && samePoint(out[out.length - 1], out[out.length - 2])) out.pop();
  return out;
};

const nextLocalId = (prefix: string) => `${prefix}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;

const mirrorHandle = (point: RiskPolygonPoint, handle: RiskPolygonPoint): RiskPolygonPoint => ({
  x: point.x * 2 - handle.x,
  y: point.y * 2 - handle.y,
});

const samplePenAnchors = (anchors: PenAnchor[], closed = false): RiskPolygonPoint[] | null => {
  if (anchors.length < 2) return null;
  const points: RiskPolygonPoint[] = [anchors[0].point];
  const appendSegment = (start: PenAnchor, end: PenAnchor) => {
    const cp1 = start.handle ?? start.point;
    const cp2 = end.handle ? mirrorHandle(end.point, end.handle) : end.point;
    const sampled = cubicBezierPoints(start.point, cp1, cp2, end.point, 24).slice(1);
    points.push(...sampled);
  };
  for (let i = 0; i < anchors.length - 1; i++) {
    appendSegment(anchors[i], anchors[i + 1]);
  }
  if (closed && anchors.length >= 3) {
    appendSegment(anchors[anchors.length - 1], anchors[0]);
  }
  return points;
};

const isEditableTarget = (target: Element | null) => {
  if (!target) return false;
  const tag = target.tagName;
  return tag === "INPUT" || tag === "TEXTAREA" || (target as HTMLElement).isContentEditable;
};

export default function WorkbenchCanvas() {
  const zones = useRiskMappingWorkbenchStore(s => s.zones);
  const pendingRegions = useRiskMappingWorkbenchStore(s => s.pendingRegions);
  const texts = useRiskMappingWorkbenchStore(s => s.texts);
  const riskPoints = useRiskMappingWorkbenchStore(s => s.riskPoints);
  const tool = useRiskMappingWorkbenchStore(s => s.tool);
  const gridEnabled = useRiskMappingWorkbenchStore(s => s.gridEnabled);
  const snapEnabled = useRiskMappingWorkbenchStore(s => s.snapEnabled);
  const guideEnabled = useRiskMappingWorkbenchStore(s => s.guideEnabled);
  const selectedRegionId = useRiskMappingWorkbenchStore(s => s.selectedRegionId);
  const selectedTextId = useRiskMappingWorkbenchStore(s => s.selectedTextId);
  const viewScale = useRiskMappingWorkbenchStore(s => s.viewScale);
  const viewX = useRiskMappingWorkbenchStore(s => s.viewX);
  const viewY = useRiskMappingWorkbenchStore(s => s.viewY);
  const floor = useRiskMappingWorkbenchStore(s => s.floors.find(f => f.id === s.currentFloorId));
  const currentFloorId = useRiskMappingWorkbenchStore(s => s.currentFloorId);
  const setState = useRiskMappingWorkbenchStore.setState;
  const setSnapshot = useRiskMappingWorkbenchStore.getState().setSnapshot;
  const commit = useRiskMappingWorkbenchStore.getState().commit;
  const [draftPoints, setDraftPointsState] = useState<RiskPolygonPoint[]>([]);
  const draftPointsRef = useRef<RiskPolygonPoint[]>([]);
  const setDraftPoints = (next: RiskPolygonPoint[] | ((prev: RiskPolygonPoint[]) => RiskPolygonPoint[])) => {
    const value = typeof next === "function" ? next(draftPointsRef.current) : next;
    draftPointsRef.current = value;
    setDraftPointsState(value);
  };
  const [penAnchors, setPenAnchorsState] = useState<PenAnchor[]>([]);
  const penAnchorsRef = useRef<PenAnchor[]>([]);
  const setPenAnchors = (next: PenAnchor[] | ((prev: PenAnchor[]) => PenAnchor[])) => {
    const value = typeof next === "function" ? next(penAnchorsRef.current) : next;
    penAnchorsRef.current = value;
    setPenAnchorsState(value);
  };
  const [penActive, setPenActiveState] = useState<PenAnchor | null>(null);
  const penActiveRef = useRef<PenAnchor | null>(null);
  const setPenActive = (next: PenAnchor | null) => {
    penActiveRef.current = next;
    setPenActiveState(next);
  };
  const [draftCursor, setDraftCursor] = useState<RiskPolygonPoint | null>(null);
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
  const spacePressedRef = useRef(false);
  const panStartRef = useRef<{ x: number; y: number; viewX: number; viewY: number } | null>(null);
  const isPanningRef = useRef(false);
  const penDraggedRef = useRef(false);
  const penCloseCandidateRef = useRef(false);
  const [isPanning, setIsPanning] = useState(false);
  const [spacePressed, setSpacePressed] = useState(false);

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

  useEffect(() => {
    if (!["polygon", "pen", "freehand"].includes(tool)) {
      setDraftPoints([]);
      setDraftCursor(null);
      setDraftStart(null);
      setDraftEnd(null);
      setIsDrawing(false);
    }
    if (tool !== "pen") {
      setPenAnchors([]);
      setPenActive(null);
      penCloseCandidateRef.current = false;
    }
  }, [tool]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.code === "Space" && !isEditableTarget(document.activeElement)) {
        event.preventDefault();
        spacePressedRef.current = true;
        setSpacePressed(true);
      }
      if (event.key === "Escape") {
        setDraftPoints([]);
        setDraftCursor(null);
        setDraftStart(null);
        setDraftEnd(null);
        penCloseCandidateRef.current = false;
        setPenAnchors([]);
        setPenActive(null);
        setIsDrawing(false);
        setState({ selectedRegionId: null, selectedRiskPointId: null, selectedTextId: null });
        return;
      }
      if (event.key === "Enter" && ["polygon", "pen"].includes(useRiskMappingWorkbenchStore.getState().tool)) {
        event.preventDefault();
        finishDrawing();
        return;
      }
      if ((event.key === "Delete" || event.key === "Backspace") && !isEditableTarget(document.activeElement)) {
        useRiskMappingWorkbenchStore.getState().deleteSelected();
      }
    };
    const onKeyUp = (event: KeyboardEvent) => {
      if (event.code === "Space") {
        spacePressedRef.current = false;
        setSpacePressed(false);
      }
    };
    const onWindowMouseMove = (event: MouseEvent) => {
      if (!isPanningRef.current || !panStartRef.current) return;
      const origin = panStartRef.current;
      setState({
        viewX: origin.viewX + event.clientX - origin.x,
        viewY: origin.viewY + event.clientY - origin.y,
      });
    };
    const onWindowMouseUp = () => {
      if (isPanningRef.current) {
        isPanningRef.current = false;
        setIsPanning(false);
        panStartRef.current = null;
      }
    };
    const onWindowMouseDown = (event: MouseEvent) => {
      const target = event.target as HTMLElement | null;
      const canvasContainer = document.querySelector('[data-testid="workbench-canvas"]');
      if (!target || !canvasContainer?.contains(target)) return;
      if (event.button === 2 || (event.button === 0 && spacePressedRef.current)) {
        event.preventDefault();
        const view = useRiskMappingWorkbenchStore.getState();
        panStartRef.current = { x: event.clientX, y: event.clientY, viewX: view.viewX, viewY: view.viewY };
        isPanningRef.current = true;
        setIsPanning(true);
      }
    };
    const onFinishDrawing = () => finishDrawing();
    window.addEventListener("keydown", onKeyDown);
    window.addEventListener("keyup", onKeyUp);
    window.addEventListener("mousedown", onWindowMouseDown);
    window.addEventListener("mousemove", onWindowMouseMove);
    window.addEventListener("mouseup", onWindowMouseUp);
    window.addEventListener("risk-mapping:finish-drawing", onFinishDrawing);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("keyup", onKeyUp);
      window.removeEventListener("mousedown", onWindowMouseDown);
      window.removeEventListener("mousemove", onWindowMouseMove);
      window.removeEventListener("mouseup", onWindowMouseUp);
      window.removeEventListener("risk-mapping:finish-drawing", onFinishDrawing);
    };
  }, [setState]);

  const image = loadedImage && loadedImage.url === floor?.floor_plan_url ? loadedImage.image : null;
  const canvasWidth = floor?.canvas_width || (image ? image.naturalWidth : STAGE_WIDTH);
  const canvasHeight = floor?.canvas_height || (image ? image.naturalHeight : STAGE_HEIGHT);

  const pointFromEvent = (e: KonvaEventObject<MouseEvent>): RiskPolygonPoint => {
    const stage = e.target.getStage?.() ?? null;
    const pos = stage?.getPointerPosition?.() ?? null;
    const rawX = pos ? (pos.x - viewX) / viewScale : (e.evt.offsetX ?? 0);
    const rawY = pos ? (pos.y - viewY) / viewScale : (e.evt.offsetY ?? 0);
    const rounded = (v: number) => (snapEnabled ? Math.round(v / 5) * 5 : Math.round(v * 100) / 100);
    return {
      x: Math.min(100, Math.max(0, rounded(toPercent(rawX, canvasWidth)))),
      y: Math.min(100, Math.max(0, rounded(toPercent(rawY, canvasHeight)))),
    };
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
    setState({ selectedRegionId: `pending:${region.id}` });
  };

  const createRiskPoint = (p: RiskPolygonPoint) => {
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
    setState({ tool: "select", selectedRiskPointId: riskPoint.id });
  };

  const createText = (p: RiskPolygonPoint) => {
    const item: RiskCanvasText = {
      id: nextLocalId("text"),
      content: "新文字标注",
      x: p.x,
      y: p.y,
      font_size: 14,
      color: "#333333",
      rotation: 0,
      sort_order: texts.length,
    };
    commit();
    setSnapshot({ texts: [...useRiskMappingWorkbenchStore.getState().texts, item] });
    setEditingTextId(item.id);
    setEditContent(item.content);
    setEditFontSize(item.font_size);
    setEditColor(item.color);
    setState({ tool: "select", selectedTextId: item.id });
  };

  const handleClick = (e: KonvaEventObject<MouseEvent>) => {
    if (["select", "rect", "circle", "freehand"].includes(tool)) return;
    if (e.evt.detail > 1) return;
    const p = pointFromEvent(e);
    if (tool === "risk-point") {
      createRiskPoint(p);
      return;
    }
    if (tool === "text") {
      createText(p);
    }
  };

  const finishDrawing = () => {
    const activeTool = useRiskMappingWorkbenchStore.getState().tool;
    if (activeTool === "polygon" || activeTool === "freehand") {
      const cleaned = dedupeTail(draftPointsRef.current);
      if (cleaned.length >= 3) addPending(cleaned);
    }
    if (activeTool === "pen") {
      const sampled = samplePenAnchors(penAnchorsRef.current, true);
      if (sampled && sampled.length >= 3) addPending(sampled);
    }
    setDraftPoints([]);
    setDraftCursor(null);
    setDraftStart(null);
    setDraftEnd(null);
    setPenAnchors([]);
    setPenActive(null);
    penCloseCandidateRef.current = false;
    setIsDrawing(false);
  };

  const handleMouseDown = (e: KonvaEventObject<MouseEvent>) => {
    if (e.evt.button === 2 || (e.evt.button === 0 && spacePressedRef.current)) {
      e.evt.preventDefault();
      const view = useRiskMappingWorkbenchStore.getState();
      panStartRef.current = { x: e.evt.clientX, y: e.evt.clientY, viewX: view.viewX, viewY: view.viewY };
      isPanningRef.current = true;
      setIsPanning(true);
      return;
    }
    if (e.evt.detail > 1) return;
    if (tool === "rect" || tool === "circle") {
      const p = pointFromEvent(e);
      setIsDrawing(true);
      setDraftStart(p);
      setDraftEnd(p);
      return;
    }
    if (tool === "polygon") {
      setDraftPoints(prev => [...prev, pointFromEvent(e)]);
      return;
    }
    if (tool === "pen") {
      const p = pointFromEvent(e);
      const nearFirst =
        penAnchors.length >= 3 &&
        Math.hypot(p.x - penAnchors[0].point.x, p.y - penAnchors[0].point.y) <= 3;
      const nearLast =
        penAnchors.length >= 3 &&
        Math.hypot(
          p.x - penAnchors[penAnchors.length - 1].point.x,
          p.y - penAnchors[penAnchors.length - 1].point.y,
        ) <= 3;
      if (nearFirst || nearLast) {
        penCloseCandidateRef.current = true;
        return;
      }
      setIsDrawing(true);
      penDraggedRef.current = false;
      setPenActive({ point: p, handle: null });
      return;
    }
    if (tool === "freehand") {
      setIsDrawing(true);
      setDraftPoints([pointFromEvent(e)]);
      return;
    }
  };

  const handleMouseMove = (e: KonvaEventObject<MouseEvent>) => {
    if (isPanningRef.current) return;
    const p = pointFromEvent(e);
    if ((tool === "rect" || tool === "circle") && isDrawing) {
      setDraftEnd(p);
      return;
    }
    if (tool === "freehand" && isDrawing) {
      setDraftPoints(prev => [...prev, p]);
      return;
    }
    if (tool === "pen" && isDrawing) {
      if (penActiveRef.current) {
        const active = penActiveRef.current;
        if (Math.hypot(p.x - active.point.x, p.y - active.point.y) > 0.2) {
          penDraggedRef.current = true;
        }
        setPenActive({ point: active.point, handle: penDraggedRef.current ? p : null });
      }
      return;
    }
    if (tool === "polygon" && draftPoints.length > 0 && !isDrawing) {
      setDraftCursor(p);
    }
    if (tool === "pen" && penAnchors.length > 0 && !isDrawing) {
      setDraftCursor(p);
    }
  };

  const handleMouseUp = () => {
    if (isPanningRef.current) {
      isPanningRef.current = false;
      setIsPanning(false);
      panStartRef.current = null;
      return;
    }
    if (tool === "pen" && penCloseCandidateRef.current) {
      penCloseCandidateRef.current = false;
      finishDrawing();
      return;
    }
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
    if (tool === "circle" && isDrawing) {
      if (draftStart && draftEnd) {
        const radius = Math.hypot(
          toCanvasX(draftEnd.x, canvasWidth) - toCanvasX(draftStart.x, canvasWidth),
          toCanvasY(draftEnd.y, canvasHeight) - toCanvasY(draftStart.y, canvasHeight),
        );
        if (radius > 0.1) {
          addPending(
            ellipsePoints(
              draftStart,
              (radius / canvasWidth) * 100,
              (radius / canvasHeight) * 100,
            ),
          );
        }
      }
      setDraftStart(null);
      setDraftEnd(null);
      setIsDrawing(false);
      return;
    }
    if (tool === "freehand" && isDrawing) {
      if (draftPointsRef.current.length >= 3) {
        finishDrawing();
      } else {
        setDraftPoints([]);
        setIsDrawing(false);
      }
      return;
    }
    if (tool === "pen" && isDrawing) {
      if (penActiveRef.current) setPenAnchors(prev => [...prev, penActiveRef.current!]);
      penDraggedRef.current = false;
      setPenActive(null);
      setIsDrawing(false);
      setDraftStart(null);
      setDraftEnd(null);
    }
  };

  const handleWheel = (e: KonvaEventObject<WheelEvent>) => {
    const stage = e.target.getStage();
    if (!stage) return;
    e.evt.preventDefault();
    const pointer = stage.getPointerPosition();
    if (!pointer) return;
    const oldScale = viewScale;
    const mousePointTo = {
      x: (pointer.x - viewX) / oldScale,
      y: (pointer.y - viewY) / oldScale,
    };
    const direction = e.evt.deltaY > 0 ? 1 / 1.2 : 1.2;
    const nextScale = Math.min(4, Math.max(0.25, oldScale * direction));
    setState({
      viewScale: nextScale,
      viewX: pointer.x - mousePointTo.x * nextScale,
      viewY: pointer.y - mousePointTo.y * nextScale,
    });
  };

  const editingText = editingTextId ? texts.find(t => t.id === editingTextId) : null;
  const penPathPoints = samplePenAnchors(penAnchors);
  const penPreviewAnchors = penActive ? [...penAnchors, penActive] : penAnchors;
  const penPreviewPoints = penActive ? samplePenAnchors(penPreviewAnchors) : null;
  const penCursorPreview =
    !penActive && draftCursor && penAnchors.length > 0
      ? samplePenAnchors([penAnchors[penAnchors.length - 1], { point: draftCursor, handle: null }])
      : null;

  return (
    <>
      <div
        data-testid="workbench-canvas"
        data-draft-count={draftPoints.length}
        data-tool={tool}
        data-space={spacePressed}
        data-view-x={viewX}
        data-view-y={viewY}
        data-view-scale={viewScale}
        style={{ height: "100%" }}
        onMouseDownCapture={e => {
          if (e.button === 2 || (e.button === 0 && spacePressedRef.current)) {
            e.preventDefault();
            const view = useRiskMappingWorkbenchStore.getState();
            panStartRef.current = { x: e.clientX, y: e.clientY, viewX: view.viewX, viewY: view.viewY };
            isPanningRef.current = true;
            setIsPanning(true);
          }
        }}
      >
        <Stage
          width={canvasWidth}
          height={canvasHeight}
          scaleX={viewScale}
          scaleY={viewScale}
          x={viewX}
          y={viewY}
          style={{
            maxWidth: "100%",
            maxHeight: "100%",
            cursor: isPanning || spacePressedRef.current ? "grabbing" : tool === "select" ? "default" : "crosshair",
          }}
          onClick={handleClick}
          onDblClick={() => {
            if (tool === "polygon" || tool === "pen") finishDrawing();
          }}
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onWheel={handleWheel}
          onContextMenu={e => e.evt.preventDefault()}
        >
          <Layer>
            {image && (
              <KonvaImage
                image={image}
                x={0}
                y={0}
                width={canvasWidth}
                height={canvasHeight}
                opacity={0.55}
              />
            )}
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
            {pendingRegions.map(r => {
              const selected = selectedRegionId === `pending:${r.id}`;
              return (
                <Line
                  key={r.id}
                  points={pointsToKonva(r.points, canvasWidth, canvasHeight)}
                  closed
                  stroke={selected ? "#1677ff" : "#fa8c16"}
                  dash={selected ? undefined : [6, 4]}
                  strokeWidth={selected ? 3 : 2}
                  draggable={tool === "select"}
                  onClick={e => {
                    e.cancelBubble = true;
                    setState({ selectedRegionId: `pending:${r.id}`, selectedRiskPointId: null, selectedTextId: null });
                  }}
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
              );
            })}
            {draftStart && draftEnd && tool === "rect" && (
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
            {draftStart && draftEnd && tool === "circle" && (
              <KonvaCircle
                x={toCanvasX(draftStart.x, canvasWidth)}
                y={toCanvasY(draftStart.y, canvasHeight)}
                radius={Math.hypot(
                  toCanvasX(draftEnd.x, canvasWidth) - toCanvasX(draftStart.x, canvasWidth),
                  toCanvasY(draftEnd.y, canvasHeight) - toCanvasY(draftStart.y, canvasHeight),
                )}
                dash={[4, 4]}
                stroke="#1677ff"
                fill="rgba(22, 119, 255, 0.08)"
              />
            )}
            {draftPoints.length > 0 && (
              <Line
                points={pointsToKonva(draftCursor ? [...draftPoints, draftCursor] : draftPoints, canvasWidth, canvasHeight)}
                closed={tool === "polygon" && !draftCursor}
                stroke="#1677ff"
                dash={[4, 4]}
                strokeWidth={2}
              />
            )}
            {draftPoints.map((p, index) => (
              <KonvaCircle
                key={`${p.x}-${p.y}-${index}`}
                x={toCanvasX(p.x, canvasWidth)}
                y={toCanvasY(p.y, canvasHeight)}
                radius={4}
                fill="#1677ff"
                stroke="#fff"
                strokeWidth={1}
              />
            ))}
            {tool === "pen" && (
              <>
                {penPathPoints && (
                  <Line
                    points={pointsToKonva(penPathPoints, canvasWidth, canvasHeight)}
                    stroke="#1677ff"
                    strokeWidth={2}
                    listening={false}
                  />
                )}
                {penPreviewPoints && (
                  <Line
                    points={pointsToKonva(penPreviewPoints, canvasWidth, canvasHeight)}
                    stroke="#1677ff"
                    dash={[4, 4]}
                    strokeWidth={2}
                    listening={false}
                  />
                )}
                {penCursorPreview && (
                  <Line
                    points={pointsToKonva(penCursorPreview, canvasWidth, canvasHeight)}
                    stroke="#8b5cf6"
                    dash={[4, 4]}
                    strokeWidth={1.5}
                    listening={false}
                  />
                )}
                {penAnchors.map((anchor, index) => (
                  <Fragment key={`anchor-${index}`}>
                    {anchor.handle && (
                      <Line
                        points={pointsToKonva([anchor.point, anchor.handle], canvasWidth, canvasHeight)}
                        stroke="#8b5cf6"
                        dash={[4, 4]}
                        strokeWidth={1.5}
                        listening={false}
                      />
                    )}
                    <KonvaCircle
                      x={toCanvasX(anchor.point.x, canvasWidth)}
                      y={toCanvasY(anchor.point.y, canvasHeight)}
                      radius={4}
                      fill="#1677ff"
                      stroke="#fff"
                      strokeWidth={2}
                      listening={false}
                    />
                    {anchor.handle && (
                      <KonvaCircle
                        x={toCanvasX(anchor.handle.x, canvasWidth)}
                        y={toCanvasY(anchor.handle.y, canvasHeight)}
                        radius={3}
                        fill="#8b5cf6"
                        stroke="#fff"
                        strokeWidth={1.5}
                        listening={false}
                      />
                    )}
                  </Fragment>
                ))}
                {penActive && (
                  <>
                    {penActive.handle && (
                      <Line
                        points={pointsToKonva([penActive.point, penActive.handle], canvasWidth, canvasHeight)}
                        stroke="#8b5cf6"
                        dash={[4, 4]}
                        strokeWidth={1.5}
                        listening={false}
                      />
                    )}
                    <KonvaCircle
                      x={toCanvasX(penActive.point.x, canvasWidth)}
                      y={toCanvasY(penActive.point.y, canvasHeight)}
                      radius={4}
                      fill="#1677ff"
                      stroke="#fff"
                      strokeWidth={2}
                      listening={false}
                    />
                    {penActive.handle && (
                      <KonvaCircle
                        x={toCanvasX(penActive.handle.x, canvasWidth)}
                        y={toCanvasY(penActive.handle.y, canvasHeight)}
                        radius={3}
                        fill="#8b5cf6"
                        stroke="#fff"
                        strokeWidth={1.5}
                        listening={false}
                      />
                    )}
                  </>
                )}
              </>
            )}
            {zones.map(z =>
              (z.floor_plan_polygon?.polygons || []).map(p => {
                const regionId = `zone:${z.id}:${p.id}`;
                const selected = selectedRegionId === regionId;
                const centroid = polygonCentroid(p.points);
                const labelWidth = z.name.length * 14 + 12;
                const labelX = toCanvasX(centroid.x, canvasWidth) - labelWidth / 2;
                const labelY = toCanvasY(centroid.y, canvasHeight) - 12;
                return (
                  <Fragment
                    key={regionId}
                  >
                    <Line
                      points={pointsToKonva(p.points, canvasWidth, canvasHeight)}
                      closed
                      fill={z.effective_color || "#d9d9d9"}
                      opacity={0.22}
                      stroke={selected ? "#1677ff" : "#ffffff"}
                      strokeWidth={selected ? 3.5 : 2.5}
                      draggable={tool === "select"}
                      onClick={e => {
                        e.cancelBubble = true;
                        setState({ selectedRegionId: regionId, selectedRiskPointId: null, selectedTextId: null });
                      }}
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
                    <Rect
                      x={labelX}
                      y={labelY}
                      width={labelWidth}
                      height={24}
                      fill="rgba(17,24,39,0.72)"
                      cornerRadius={4}
                      listening={false}
                    />
                    <KonvaText
                      x={labelX}
                      y={labelY}
                      text={z.name}
                      fontSize={14}
                      fontStyle="bold"
                      fill="#ffffff"
                      align="center"
                      width={labelWidth}
                      height={24}
                      verticalAlign="middle"
                      listening={false}
                    />
                  </Fragment>
                );
              }),
            )}
            {texts.map(t => {
              const selected = selectedTextId === t.id;
              return (
                <KonvaText
                  key={t.id}
                  x={toCanvasX(t.x, canvasWidth)}
                  y={toCanvasY(t.y, canvasHeight)}
                  text={t.content}
                  fontSize={t.font_size}
                  fill={t.color}
                  rotation={t.rotation}
                  stroke={selected ? "#1677ff" : undefined}
                  strokeWidth={selected ? 1 : 0}
                  draggable={tool === "select"}
                  onClick={e => {
                    e.cancelBubble = true;
                    setState({ selectedTextId: t.id, selectedRiskPointId: null, selectedRegionId: null });
                  }}
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
                    setState({ selectedTextId: t.id, selectedRiskPointId: null, selectedRegionId: null });
                    setEditingTextId(t.id);
                    setEditContent(t.content);
                    setEditFontSize(t.font_size);
                    setEditColor(t.color);
                  }}
                />
              );
            })}
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
                useRiskMappingWorkbenchStore.getState().deleteText(editingText.id);
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
