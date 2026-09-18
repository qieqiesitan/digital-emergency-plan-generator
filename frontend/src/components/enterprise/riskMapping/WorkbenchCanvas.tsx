import { Fragment, useCallback, useEffect, useRef, useState } from "react";
import {
  Stage,
  Layer,
  Image as KonvaImage,
  Line,
  Rect,
  Circle as KonvaCircle,
  Text as KonvaText,
  Transformer,
} from "react-konva";
import type { KonvaEventObject } from "konva/lib/Node";
import type { Node as KonvaNode } from "konva/lib/Node";
import type { Transformer as KonvaTransformer } from "konva/lib/shapes/Transformer";
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
import type { PendingRegion, RiskPolygonPoint, RiskCanvasText, WorkbenchZone } from "@/types/riskMappingWorkbench";
import type { RiskObject } from "@/types/riskManagement";
import { zoneDisplayColor } from "@/utils/zoneDisplay";
import { collectRegionsInRect, rectFromPoints } from "@/utils/riskMappingMarquee";
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

export default function WorkbenchCanvas({ colorMode = "current" }: { colorMode?: "current" | "inherent" }) {
  const zones = useRiskMappingWorkbenchStore(s => s.zones);
  const pendingRegions = useRiskMappingWorkbenchStore(s => s.pendingRegions);
  const texts = useRiskMappingWorkbenchStore(s => s.texts);
  const riskPoints = useRiskMappingWorkbenchStore(s => s.riskPoints);
  const tool = useRiskMappingWorkbenchStore(s => s.tool);
  const gridEnabled = useRiskMappingWorkbenchStore(s => s.gridEnabled);
  const snapEnabled = useRiskMappingWorkbenchStore(s => s.snapEnabled);
  const guideEnabled = useRiskMappingWorkbenchStore(s => s.guideEnabled);
  const showFloorPlan = useRiskMappingWorkbenchStore(s => s.showFloorPlan);
  const selectedRegionIds = useRiskMappingWorkbenchStore(s => s.selectedRegionIds);
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
  const setPenAnchors = useCallback((next: PenAnchor[] | ((prev: PenAnchor[]) => PenAnchor[])) => {
    const value = typeof next === "function" ? next(penAnchorsRef.current) : next;
    penAnchorsRef.current = value;
    setPenAnchorsState(value);
  }, []);
  const [penActive, setPenActiveState] = useState<PenAnchor | null>(null);
  const penActiveRef = useRef<PenAnchor | null>(null);
  const setPenActive = useCallback((next: PenAnchor | null) => {
    penActiveRef.current = next;
    setPenActiveState(next);
  }, []);
  const [draftCursor, setDraftCursor] = useState<RiskPolygonPoint | null>(null);
  const [draftStart, setDraftStart] = useState<RiskPolygonPoint | null>(null);
  const [draftEnd, setDraftEnd] = useState<RiskPolygonPoint | null>(null);
  const [isDrawing, setIsDrawing] = useState(false);
  const [loadedImage, setLoadedImage] = useState<LoadedImage | null>(null);
  const [editingTextId, setEditingTextId] = useState<string | null>(null);
  const [editContent, setEditContent] = useState("");
  const [editFontSize, setEditFontSize] = useState(14);
  const [editColor, setEditColor] = useState("#333333");
  const pendingDragOriginRef = useRef<Map<string, RiskPolygonPoint[]>>(new Map());
  const regionNodeRefs = useRef<Map<string, KonvaNode>>(new Map());
  const regionTransformOriginRef = useRef<Map<string, RiskPolygonPoint[]>>(new Map());
  const groupDragRef = useRef<{ startX: number; startY: number; origin: Map<string, RiskPolygonPoint[]> } | null>(null);
  const dragWritebackRef = useRef(false);
  const transformerRef = useRef<KonvaTransformer>(null);
  const spacePressedRef = useRef(false);
  const panStartRef = useRef<{ x: number; y: number; viewX: number; viewY: number } | null>(null);
  const isPanningRef = useRef(false);
  const penDraggedRef = useRef(false);
  const penCloseCandidateRef = useRef(false);
  const [isPanning, setIsPanning] = useState(false);
  const [spacePressed, setSpacePressed] = useState(false);
  const canvasBoxRef = useRef<HTMLDivElement | null>(null);
  const [containerSize, setContainerSize] = useState({ width: 0, height: 0 });
  const [marqueeStart, setMarqueeStart] = useState<RiskPolygonPoint | null>(null);
  const [marqueeEnd, setMarqueeEnd] = useState<RiskPolygonPoint | null>(null);
  const marqueeEndRef = useRef<RiskPolygonPoint | null>(null);
  const marqueeShiftRef = useRef(false);
  const zoneColor = (z: WorkbenchZone) => zoneDisplayColor(z, colorMode);

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
    const el = canvasBoxRef.current;
    if (!el) return;
    const update = () => setContainerSize({ width: el.clientWidth, height: el.clientHeight });
    update();
    const observer = new ResizeObserver(update);
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  // 工具切换时清理绘制草稿。
  // 这些 setter 内部同时写 ref（penAnchorsRef 等），渲染期调用会被 react-hooks/refs 判为读 ref；
  // 放在微任务里执行则既满足 react-hooks/set-state-in-effect，也不在渲染/effect 同步阶段写 ref。
  useEffect(() => {
    void Promise.resolve().then(() => {
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
    });
  }, [tool, setPenAnchors, setPenActive]);

  // finishDrawing 定义在本文件后面，事件监听通过 ref 取最新实现（避免“先用后声明”）
  const finishDrawingRef = useRef<() => void>(() => {});

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
        setState({ selectedRegionIds: [], selectedRiskPointId: null, selectedTextId: null });
        return;
      }
      if (event.key === "Enter" && ["polygon", "pen"].includes(useRiskMappingWorkbenchStore.getState().tool)) {
        event.preventDefault();
        finishDrawingRef.current();
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
    const onFinishDrawing = () => finishDrawingRef.current();
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
  }, [setState, setPenAnchors, setPenActive]);

  const image = loadedImage && loadedImage.url === floor?.floor_plan_url ? loadedImage.image : null;
  const canvasWidth = floor?.canvas_width || (image ? image.naturalWidth : STAGE_WIDTH);
  const canvasHeight = floor?.canvas_height || (image ? image.naturalHeight : STAGE_HEIGHT);

  // 画布尺寸或容器变化时自动适配视图（导入后画布更换也能铺满容器）
  useEffect(() => {
    if (!containerSize.width || !containerSize.height) return;
    const scale = Math.min(4, Math.max(0.25, Math.min(
      containerSize.width / canvasWidth,
      containerSize.height / canvasHeight,
    )));
    const x = (containerSize.width - canvasWidth * scale) / 2;
    const y = (containerSize.height - canvasHeight * scale) / 2;
    useRiskMappingWorkbenchStore.setState({ viewScale: scale, viewX: x, viewY: y });
  }, [canvasWidth, canvasHeight, containerSize.width, containerSize.height]);

  // 选中集合变化时把对应节点挂到 Transformer：渲染期不能读 ref，
  // 改为在 effect 里命令式设置 Konva Transformer 的 nodes
  useEffect(() => {
    if (tool !== "select") return;
    const tr = transformerRef.current;
    if (!tr) return;
    const nodes = selectedRegionIds
      .map((id) => regionNodeRefs.current.get(id))
      .filter((node): node is KonvaNode => node !== undefined);
    tr.nodes(nodes);
    tr.getLayer()?.batchDraw();
  }, [selectedRegionIds, tool]);

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

  // 框选使用不做网格吸附的坐标：绘制工具的 5% 吸附会把小范围框选压缩成 0 尺寸。
  const rawPointFromEvent = (e: KonvaEventObject<MouseEvent>): RiskPolygonPoint => {
    const stage = e.target.getStage?.() ?? null;
    const pos = stage?.getPointerPosition?.() ?? null;
    const rawX = pos ? (pos.x - viewX) / viewScale : (e.evt.offsetX ?? 0);
    const rawY = pos ? (pos.y - viewY) / viewScale : (e.evt.offsetY ?? 0);
    return {
      x: Math.min(100, Math.max(0, Math.round(toPercent(rawX, canvasWidth) * 100) / 100)),
      y: Math.min(100, Math.max(0, Math.round(toPercent(rawY, canvasHeight) * 100) / 100)),
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
    setState({ selectedRegionIds: [`pending:${region.id}`] });
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
      responsible_unit: null,
      responsible_person: null,
      contact_phone: null,
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

  // 每次渲染后把最新的 finishDrawing 交给 ref（effect 内写 ref 是允许的）
  useEffect(() => {
    finishDrawingRef.current = finishDrawing;
  });

  const resolveRegionPoints = (id: string): RiskPolygonPoint[] | null => {
    const store = useRiskMappingWorkbenchStore.getState();
    if (id.startsWith("pending:")) {
      return store.pendingRegions.find(r => r.id === id.slice("pending:".length))?.points ?? null;
    }
    if (id.startsWith("zone:")) {
      const body = id.slice("zone:".length);
      const separator = body.indexOf(":");
      const zoneId = body.slice(0, separator);
      const polygonId = body.slice(separator + 1);
      const zone = store.zones.find(z => z.id === zoneId);
      return zone?.floor_plan_polygon?.polygons.find(p => p.id === polygonId)?.points ?? null;
    }
    return null;
  };

  const applyRegionPointUpdates = (
    zones: WorkbenchZone[],
    pendingRegions: PendingRegion[],
    updates: Map<string, RiskPolygonPoint[]>,
  ) => {
    const zoneUpdates = new Map<string, Map<string, RiskPolygonPoint[]>>();
    const pendingUpdates = new Map<string, RiskPolygonPoint[]>();
    updates.forEach((points, id) => {
      if (id.startsWith("pending:")) {
        pendingUpdates.set(id.slice("pending:".length), points);
      } else if (id.startsWith("zone:")) {
        const body = id.slice("zone:".length);
        const separator = body.indexOf(":");
        const zoneId = body.slice(0, separator);
        const polygonId = body.slice(separator + 1);
        if (!zoneUpdates.has(zoneId)) zoneUpdates.set(zoneId, new Map());
        zoneUpdates.get(zoneId)!.set(polygonId, points);
      }
    });
    return {
      zones: zones.map(z => {
        const map = zoneUpdates.get(z.id);
        if (!map || !z.floor_plan_polygon) return z;
        return {
          ...z,
          floor_plan_polygon: {
            ...z.floor_plan_polygon,
            polygons: z.floor_plan_polygon.polygons.map(p =>
              map.has(p.id) ? { ...p, points: map.get(p.id)! } : p,
            ),
          },
        };
      }),
      pendingRegions: pendingRegions.map(r =>
        pendingUpdates.has(r.id) ? { ...r, points: pendingUpdates.get(r.id)! } : r,
      ),
    };
  };

  const handleRegionTransformStart = (regionId: string, points: RiskPolygonPoint[]) => {
    const store = useRiskMappingWorkbenchStore.getState();
    const targets = store.selectedRegionIds.length ? store.selectedRegionIds : [regionId];
    regionTransformOriginRef.current.clear();
    targets.forEach(id => {
      const pts = resolveRegionPoints(id);
      if (pts) regionTransformOriginRef.current.set(id, pts);
    });
    if (!regionTransformOriginRef.current.size) {
      regionTransformOriginRef.current.set(regionId, points);
    }
  };

  const handleRegionTransformEnd = () => {
    const origin = regionTransformOriginRef.current;
    if (!origin.size) return;
    const updates = new Map<string, RiskPolygonPoint[]>();
    origin.forEach((points, id) => {
      const node = regionNodeRefs.current.get(id);
      if (!node) return;
      const transform = node.getTransform();
      const next = points.map(pt => {
        const canvasPoint = transform.point({
          x: toCanvasX(pt.x, canvasWidth),
          y: toCanvasY(pt.y, canvasHeight),
        });
        return clampPoint({
          x: toPercent(canvasPoint.x, canvasWidth),
          y: toPercent(canvasPoint.y, canvasHeight),
        });
      });
      node.scale({ x: 1, y: 1 });
      node.rotation(0);
      node.position({ x: 0, y: 0 });
      node.offset({ x: 0, y: 0 });
      updates.set(id, next);
    });
    regionTransformOriginRef.current.clear();
    if (!updates.size) return;
    const store = useRiskMappingWorkbenchStore.getState();
    const applied = applyRegionPointUpdates(store.zones, store.pendingRegions, updates);
    commit();
    setSnapshot(applied);
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
    if (tool === "select") {
      const p = rawPointFromEvent(e);
      marqueeShiftRef.current = e.evt.shiftKey;
      marqueeEndRef.current = p;
      setMarqueeStart(p);
      setMarqueeEnd(p);
      return;
    }
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
    if (marqueeStart) {
      const p = rawPointFromEvent(e);
      marqueeEndRef.current = p;
      setMarqueeEnd(p);
      return;
    }
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
    if (marqueeStart) {
      const end = marqueeEndRef.current ?? marqueeStart;
      const rect = rectFromPoints(marqueeStart, end, (3 / canvasWidth) * 100);
      const append = marqueeShiftRef.current;
      setMarqueeStart(null);
      setMarqueeEnd(null);
      marqueeEndRef.current = null;
      const store = useRiskMappingWorkbenchStore.getState();
      if (!rect) {
        if (!append) store.setSelectedRegions([]);
        return;
      }
      const hitIds: string[] = [];
      store.zones.forEach(z => {
        const polygons = z.floor_plan_polygon?.polygons ?? [];
        collectRegionsInRect(polygons, rect).forEach(pid => hitIds.push(`zone:${z.id}:${pid}`));
      });
      if (!hitIds.length) {
        if (!append) store.setSelectedRegions([]);
        return;
      }
      store.setSelectedRegions(hitIds, { append });
      const firstZoneId = hitIds[0].slice("zone:".length).split(":")[0];
      useRiskMappingWorkbenchStore.setState({ selectedZoneId: firstZoneId });
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
      if (penActiveRef.current) setPenAnchors((prev: PenAnchor[]) => [...prev, penActiveRef.current!]);
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
        ref={canvasBoxRef}
        data-testid="workbench-canvas"
        data-draft-count={draftPoints.length}
        data-floor-plan={showFloorPlan}
        data-transform-active={tool === "select" && selectedRegionIds.length > 0}
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
          width={containerSize.width || canvasWidth}
          height={containerSize.height || canvasHeight}
          scaleX={viewScale}
          scaleY={viewScale}
          x={viewX}
          y={viewY}
          style={{
            maxWidth: "100%",
            maxHeight: "100%",
            cursor: isPanning || spacePressed ? "grabbing" : tool === "select" ? "default" : "crosshair",
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
            {showFloorPlan && image && (
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
            {marqueeStart && marqueeEnd && (() => {
              const rect = rectFromPoints(marqueeStart, marqueeEnd, (3 / canvasWidth) * 100);
              if (!rect) return null;
              return (
                <Rect
                  x={toCanvasX(rect.x, canvasWidth)}
                  y={toCanvasY(rect.y, canvasHeight)}
                  width={(rect.width / 100) * canvasWidth}
                  height={(rect.height / 100) * canvasHeight}
                  fill="rgba(22,119,255,0.12)"
                  stroke="#1677ff"
                  dash={[6, 4]}
                  strokeWidth={1.5}
                  listening={false}
                />
              );
            })()}
            {pendingRegions.map(r => {
              const selected = selectedRegionIds.includes(`pending:${r.id}`);
              return (
                <Line
                  id={`pending:${r.id}`}
                  key={r.id}
                  points={pointsToKonva(r.points, canvasWidth, canvasHeight)}
                  closed
                  stroke={selected ? "#1677ff" : "#fa8c16"}
                  dash={selected ? undefined : [6, 4]}
                  strokeWidth={selected ? 3 : 2}
                  draggable={tool === "select"}
                  ref={node => {
                    if (node) {
                      regionNodeRefs.current.set(`pending:${r.id}`, node);
                    } else {
                      regionNodeRefs.current.delete(`pending:${r.id}`);
                    }
                  }}
                  onMouseDown={e => {
                    e.cancelBubble = true;
                  }}
                  onClick={e => {
                    e.cancelBubble = true;
                    setState({ selectedRegionIds: [`pending:${r.id}`], selectedRiskPointId: null, selectedTextId: null });
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
                  onTransformStart={() => handleRegionTransformStart(`pending:${r.id}`, r.points)}
                  onTransformEnd={handleRegionTransformEnd}
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
                const selected = selectedRegionIds.includes(regionId);
                const centroid = polygonCentroid(p.points);
                const labelWidth = z.name.length * 14 + 12;
                const labelX = toCanvasX(centroid.x, canvasWidth) - labelWidth / 2;
                const labelY = toCanvasY(centroid.y, canvasHeight) - 12;
                return (
                  <Fragment
                    key={regionId}
                  >
                    <Line
                      id={regionId}
                      points={pointsToKonva(p.points, canvasWidth, canvasHeight)}
                      closed
                      fill={zoneColor(z) || "#d9d9d9"}
                      opacity={0.22}
                      stroke={selected ? "#1677ff" : "#ffffff"}
                      strokeWidth={selected ? 3.5 : 2.5}
                      draggable={tool === "select"}
                      ref={node => {
                        if (node) {
                          regionNodeRefs.current.set(regionId, node);
                        } else {
                          regionNodeRefs.current.delete(regionId);
                        }
                      }}
                      onMouseDown={e => {
                        e.cancelBubble = true;
                      }}
                      onClick={e => {
                        e.cancelBubble = true;
                        setState({
                          selectedRegionIds: [regionId],
                          selectedRiskPointId: null,
                          selectedTextId: null,
                          selectedZoneId: z.id,
                        });
                      }}
                      onDragStart={e => {
                        const store = useRiskMappingWorkbenchStore.getState();
                        if (!store.selectedRegionIds.includes(regionId)) {
                          store.setSelectedRegions([regionId]);
                        }
                        const origin = new Map<string, RiskPolygonPoint[]>();
                        useRiskMappingWorkbenchStore.getState().selectedRegionIds.forEach(id => {
                          const pts = resolveRegionPoints(id);
                          if (pts) origin.set(id, pts);
                        });
                        if (!origin.size) origin.set(regionId, p.points);
                        groupDragRef.current = { startX: e.target.x(), startY: e.target.y(), origin };
                        dragWritebackRef.current = false;
                      }}
                      onDragMove={e => {
                        const group = groupDragRef.current;
                        if (!group || group.origin.size < 2) return;
                        const dx = e.target.x() - group.startX;
                        const dy = e.target.y() - group.startY;
                        group.origin.forEach((_pts, id) => {
                          if (id === regionId) return;
                          regionNodeRefs.current.get(id)?.position({ x: dx, y: dy });
                        });
                      }}
                      onDragEnd={e => {
                        const dxPx = e.target.x();
                        const dyPx = e.target.y();
                        e.target.position({ x: 0, y: 0 });
                        // Konva 会为每个选中节点各触发一次 dragEnd：只允许有位移的那次写回，
                        // 否则后续 0 位移的 dragEnd 会把整体位移覆盖掉。
                        if (dragWritebackRef.current) return;
                        if (Math.abs(dxPx) < 0.01 && Math.abs(dyPx) < 0.01) return;
                        dragWritebackRef.current = true;
                        const dx = (dxPx / canvasWidth) * 100;
                        const dy = (dyPx / canvasHeight) * 100;
                        const group = groupDragRef.current;
                        groupDragRef.current = null;
                        const targets =
                          group?.origin ?? new Map<string, RiskPolygonPoint[]>([[regionId, resolveRegionPoints(regionId) ?? p.points]]);
                        const updates = new Map<string, RiskPolygonPoint[]>();
                        targets.forEach((points, id) => {
                          updates.set(id, points.map(pt => clampPoint({ x: pt.x + dx, y: pt.y + dy })));
                          regionNodeRefs.current.get(id)?.position({ x: 0, y: 0 });
                        });
                        const store = useRiskMappingWorkbenchStore.getState();
                        const applied = applyRegionPointUpdates(store.zones, store.pendingRegions, updates);
                        commit();
                        setSnapshot(applied);
                      }}
                      onTransformStart={() => handleRegionTransformStart(regionId, p.points)}
                      onTransformEnd={handleRegionTransformEnd}
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
                    setState({ selectedTextId: t.id, selectedRiskPointId: null, selectedRegionIds: [] });
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
                    setState({ selectedTextId: t.id, selectedRiskPointId: null, selectedRegionIds: [] });
                    setEditingTextId(t.id);
                    setEditContent(t.content);
                    setEditFontSize(t.font_size);
                    setEditColor(t.color);
                  }}
                />
              );
            })}
            <WorkbenchRiskPointLayer />
            {tool === "select" && (
              <Transformer
                ref={transformerRef}
                rotateEnabled
                flipEnabled={false}
                anchorSize={10}
                borderStroke="#1677ff"
                anchorStroke="#1677ff"
                anchorFill="#ffffff"
              />
            )}
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
