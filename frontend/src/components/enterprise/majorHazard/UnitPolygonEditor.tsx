import { useEffect, useRef, useState } from "react";
import type { MouseEvent as ReactMouseEvent, PointerEvent as ReactPointerEvent } from "react";
import { App as AntApp, Alert, Button, Card, Empty, Select, Space, Typography } from "antd";
import { ClearOutlined, EditOutlined, ReloadOutlined, SaveOutlined } from "@ant-design/icons";
import { useQuery } from "@tanstack/react-query";
import { listEnterpriseFloors } from "@/services/riskMappingWorkbenchService";
import { setUnitPolygon } from "@/services/majorHazardService";
import type { MajorHazardUnitPolygonPoint } from "@/types/majorHazard";
import { clampPoint } from "@/utils/riskMappingGeometry";
import {
  buildUnitPolygon,
  isClosingClick,
  isUnitPolygonComplete,
  parseUnitPolygon,
} from "@/utils/unitPolygon";

const { Text } = Typography;

interface Props {
  enterpriseId: string;
  unitId: string;
  /** 已保存落点所在楼层。 */
  floorId?: string | null;
  /** 已保存的落点（后端 JSONB，可能为脏数据，由 parseUnitPolygon 宽容解析）。 */
  polygon?: unknown;
  /** 保存/清空成功后回调（父组件用于 invalidateQueries）。 */
  onSaved?: () => void;
}

/**
 * 单元平面图落点编辑器。
 *
 * 与四色图工作台共用坐标约定（百分比 0-100）与几何纯函数（utils/riskMappingGeometry、
 * utils/unitPolygon），但不依赖工作台的 store 与画布组件——单元落点只需要
 * "选楼层 → 画一个闭合边界 → 保存"，用 SVG 表达比引 Konva 更薄、更可测。
 *
 * 楼层与落点必须成对：切换楼层时编辑区按目标楼层重置，
 * 避免把 A 楼层的坐标存到 B 楼层上。
 */
export default function UnitPolygonEditor({ enterpriseId, unitId, floorId, polygon, onSaved }: Props) {
  const { message } = AntApp.useApp();
  const savedShape = parseUnitPolygon(polygon);
  const [selectedFloorId, setSelectedFloorId] = useState<string | null>(floorId ?? null);
  const [points, setPoints] = useState<MajorHazardUnitPolygonPoint[]>(
    () => savedShape?.points ?? [],
  );
  const [drafting, setDrafting] = useState(false);
  const [saving, setSaving] = useState(false);
  const svgRef = useRef<SVGSVGElement | null>(null);
  const dragIndexRef = useRef<number | null>(null);

  const { data: floors = [], isLoading: floorsLoading } = useQuery({
    queryKey: ["enterprise-floors", enterpriseId],
    queryFn: () => listEnterpriseFloors(enterpriseId),
    enabled: !!enterpriseId,
  });
  const floor = floors.find((f) => f.id === selectedFloorId);

  // Esc 取消当前编辑（回到已保存落点），与工作台手感一致
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      setDrafting(false);
      setPoints(parseUnitPolygon(polygon)?.points ?? []);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [polygon]);

  const pointFromEvent = (clientX: number, clientY: number): MajorHazardUnitPolygonPoint | null => {
    const rect = svgRef.current?.getBoundingClientRect();
    if (!rect || !rect.width || !rect.height) return null;
    return clampPoint({
      x: Number((((clientX - rect.left) / rect.width) * 100).toFixed(2)),
      y: Number((((clientY - rect.top) / rect.height) * 100).toFixed(2)),
    });
  };

  const handleFloorChange = (value?: string) => {
    const next = value ?? null;
    setSelectedFloorId(next);
    setDrafting(false);
    // 与已保存楼层相同 → 还原到已保存落点；不同 → 从空白开始，
    // 因为原来那组坐标只对原楼层有意义。
    setPoints(next && next === floorId ? savedShape?.points ?? [] : []);
  };

  const handleCanvasClick = (event: ReactMouseEvent<SVGSVGElement>) => {
    if (!drafting) return;
    if ((event.target as Element).tagName === "circle") return;
    const point = pointFromEvent(event.clientX, event.clientY);
    if (!point) return;
    if (isClosingClick(points, point)) {
      setDrafting(false);
      message.info("边界已闭合，请点「保存落点」");
      return;
    }
    setPoints((prev) => [...prev, point]);
  };

  const handleVertexPointerDown = (index: number) => (event: ReactPointerEvent<SVGCircleElement>) => {
    event.stopPropagation();
    event.currentTarget.setPointerCapture(event.pointerId);
    dragIndexRef.current = index;
  };

  const handleVertexPointerMove = (event: ReactPointerEvent<SVGCircleElement>) => {
    if (dragIndexRef.current === null) return;
    const point = pointFromEvent(event.clientX, event.clientY);
    if (!point) return;
    const index = dragIndexRef.current;
    setPoints((prev) => prev.map((item, i) => (i === index ? point : item)));
  };

  const handleVertexPointerUp = (event: ReactPointerEvent<SVGCircleElement>) => {
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
    dragIndexRef.current = null;
  };

  const startDraw = () => {
    setDrafting(true);
    const shape = selectedFloorId === floorId ? savedShape : null;
    setPoints(shape?.points ?? []);
  };

  const restore = () => {
    setDrafting(false);
    setPoints(savedShape?.points ?? []);
  };

  const save = async () => {
    if (!selectedFloorId) {
      message.warning("请先选择楼层");
      return;
    }
    const shape = buildUnitPolygon(points);
    if (!shape) {
      message.warning("至少需要 3 个顶点，且边界不能退化为一条线");
      return;
    }
    setSaving(true);
    try {
      await setUnitPolygon(unitId, { floor_id: selectedFloorId, polygon: shape });
      setDrafting(false);
      message.success("落点已保存");
      onSaved?.();
    } finally {
      setSaving(false);
    }
  };

  const clear = async () => {
    setSaving(true);
    try {
      await setUnitPolygon(unitId, { floor_id: null, polygon: null });
      setSelectedFloorId(null);
      setDrafting(false);
      setPoints([]);
      message.success("落点已清空");
      onSaved?.();
    } finally {
      setSaving(false);
    }
  };

  const canSave = !!selectedFloorId && isUnitPolygonComplete(points);

  return (
    <Card size="small" title="平面图落点">
      <Space orientation="vertical" style={{ width: "100%" }} size="small">
        <Space wrap>
          <Select
            placeholder="选择楼层"
            style={{ width: 240 }}
            loading={floorsLoading}
            value={selectedFloorId ?? undefined}
            onChange={handleFloorChange}
            allowClear
            options={floors.map((f) => ({ value: f.id, label: f.name }))}
          />
          <Button icon={<EditOutlined />} onClick={startDraw} disabled={!selectedFloorId} type={drafting ? "primary" : "default"}>
            绘制边界
          </Button>
          <Button icon={<SaveOutlined />} type="primary" onClick={save} loading={saving} disabled={!canSave}>
            保存落点
          </Button>
          {savedShape && (
            <Button icon={<ReloadOutlined />} onClick={restore} disabled={drafting}>
              还原
            </Button>
          )}
          {floorId && (
            <Button danger icon={<ClearOutlined />} onClick={clear} loading={saving}>
              清空落点
            </Button>
          )}
        </Space>

        {!selectedFloorId && (
          <Alert type="info" showIcon title="请先选择楼层，再绘制该单元在平面图上的边界。" />
        )}

        {savedShape && selectedFloorId && selectedFloorId !== floorId && (
          <Alert
            type="warning"
            showIcon
            title="该单元已保存的落点在其它楼层，保存后将以当前楼层的边界为准。"
          />
        )}

        {selectedFloorId && (
          <div
            style={{
              position: "relative",
              border: "1px solid #f0f0f0",
              borderRadius: 4,
              overflow: "hidden",
              background: "#fafafa",
            }}
          >
            {floor?.floor_plan_url ? (
              <img
                src={floor.floor_plan_url}
                alt={`${floor.name} 平面图`}
                draggable={false}
                style={{ display: "block", width: "100%", userSelect: "none", pointerEvents: "none" }}
              />
            ) : (
              <div
                style={{
                  width: "100%",
                  aspectRatio: "4 / 3",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  background:
                    "repeating-linear-gradient(0deg, #f0f0f0, #f0f0f0 1px, #fafafa 1px, #fafafa 24px)," +
                    "repeating-linear-gradient(90deg, #f0f0f0, #f0f0f0 1px, #fafafa 1px, #fafafa 24px)",
                }}
              >
                <Empty
                  image={Empty.PRESENTED_IMAGE_SIMPLE}
                  description="该楼层尚未上传平面图，仍可直接落点"
                />
              </div>
            )}
            <svg
              ref={svgRef}
              viewBox="0 0 100 100"
              preserveAspectRatio="none"
              onClick={handleCanvasClick}
              style={{
                position: "absolute",
                inset: 0,
                width: "100%",
                height: "100%",
                cursor: drafting ? "crosshair" : "default",
                touchAction: "none",
              }}
            >
              {points.length >= 2 && (
                <polygon
                  points={points.map((p) => `${p.x},${p.y}`).join(" ")}
                  fill="rgba(22, 119, 255, 0.15)"
                  stroke="#1677ff"
                  strokeWidth={2}
                  strokeDasharray={drafting ? "6 4" : undefined}
                  vectorEffect="non-scaling-stroke"
                />
              )}
              {drafting && points.length >= 2 && (
                <line
                  x1={points[points.length - 1].x}
                  y1={points[points.length - 1].y}
                  x2={points[0].x}
                  y2={points[0].y}
                  stroke="#1677ff"
                  strokeWidth={1}
                  strokeDasharray="4 4"
                  vectorEffect="non-scaling-stroke"
                />
              )}
              {points.map((p, index) => (
                <circle
                  key={`${index}-${p.x}-${p.y}`}
                  cx={p.x}
                  cy={p.y}
                  r={2}
                  fill={index === 0 ? "#fa8c16" : "#1677ff"}
                  stroke="#fff"
                  strokeWidth={1}
                  vectorEffect="non-scaling-stroke"
                  style={{ cursor: "grab" }}
                  onPointerDown={handleVertexPointerDown(index)}
                  onPointerMove={handleVertexPointerMove}
                  onPointerUp={handleVertexPointerUp}
                />
              ))}
            </svg>
          </div>
        )}

        <Text type="secondary" style={{ fontSize: 12 }}>
          {drafting
            ? "在图上点击逐点绘制边界；点回第一个顶点（橙色）即闭合；按 Esc 取消。拖动蓝色顶点可微调。"
            : "边界用百分比坐标保存，楼层底图更换后位置仍按相对位置对齐。"}
        </Text>
      </Space>
    </Card>
  );
}
