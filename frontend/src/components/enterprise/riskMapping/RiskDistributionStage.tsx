import { useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { Stage, Layer, Line, Circle, Text as KonvaText } from "react-konva";
import { Spin } from "antd";
import { useQuery } from "@tanstack/react-query";
import { getRiskMappingOverview } from "@/services/riskManagementService";
import { pointsToKonva, toCanvasX, toCanvasY } from "@/utils/riskMappingGeometry";
import type { WorkbenchZone } from "@/types/riskMappingWorkbench";

const DEFAULT_WIDTH = 1200;
const DEFAULT_HEIGHT = 900;

export default function RiskDistributionStage({
  floorId,
  highlightZone,
  onZoneClick,
  mode = "current",
}: {
  floorId?: string;
  highlightZone?: string | null;
  onZoneClick?: (zoneId: string) => void;
  mode?: "current" | "inherent";
}) {
  const { id: enterpriseId } = useParams<{ id: string }>();
  const { data, isLoading } = useQuery({
    queryKey: ["risk-overview-stage", enterpriseId, floorId],
    queryFn: () => getRiskMappingOverview(enterpriseId!, floorId),
    enabled: !!enterpriseId,
  });
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [containerSize, setContainerSize] = useState({ width: 0, height: 0 });
  const [imageSize, setImageSize] = useState<{ width: number; height: number } | null>(null);
  const floor = data?.floors[0];
  const floorPlanUrl = floor?.floor_plan_url ?? null;

  useEffect(() => {
    if (!floorPlanUrl) return;
    const img = new window.Image();
    img.onload = () => {
      setImageSize({ width: img.naturalWidth, height: img.naturalHeight });
    };
    img.src = floorPlanUrl;
    return () => {
      img.onload = null;
    };
  }, [floorPlanUrl]);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const updateSize = () => {
      setContainerSize({ width: el.clientWidth, height: el.clientHeight });
    };
    updateSize();
    const observer = new ResizeObserver(updateSize);
    observer.observe(el);
    return () => observer.disconnect();
  }, [isLoading, data]);

  const width = floor?.canvas_width || imageSize?.width || DEFAULT_WIDTH;
  const height = floor?.canvas_height || imageSize?.height || DEFAULT_HEIGHT;

  const contentBounds = useMemo(() => {
    if (!data) return null;
    const rawPoints: Array<[number, number]> = [];
    for (const zone of data.zones) {
      for (const polygon of zone.floor_plan_polygon?.polygons || []) {
        for (const p of polygon.points) rawPoints.push([p.x, p.y]);
      }
    }
    for (const p of data.riskPoints) {
      if (p.location_x != null && p.location_y != null) rawPoints.push([p.location_x, p.location_y]);
    }
    for (const t of data.texts) rawPoints.push([t.x, t.y]);
    if (!rawPoints.length) {
      return { x: 0, y: 0, width, height };
    }
    const xs = rawPoints.map(p => p[0]);
    const ys = rawPoints.map(p => p[1]);
    const minX = Math.max(0, Math.min(...xs));
    const minY = Math.max(0, Math.min(...ys));
    const maxX = Math.min(100, Math.max(...xs));
    const maxY = Math.min(100, Math.max(...ys));
    return {
      x: toCanvasX(minX, width),
      y: toCanvasY(minY, height),
      width: Math.max(toCanvasX(maxX, width) - toCanvasX(minX, width), 1),
      height: Math.max(toCanvasY(maxY, height) - toCanvasY(minY, height), 1),
    };
  }, [data, width, height]);

  const viewTransform = useMemo(() => {
    if (!containerSize.width || !containerSize.height || !contentBounds) {
      return { scale: 1, x: 0, y: 0 };
    }
    const scale = Math.min(
      containerSize.width / contentBounds.width,
      containerSize.height / contentBounds.height,
      2,
    );
    const x = (containerSize.width - contentBounds.width * scale) / 2 - contentBounds.x * scale;
    const y = (containerSize.height - contentBounds.height * scale) / 2 - contentBounds.y * scale;
    return { scale, x, y };
  }, [containerSize, contentBounds]);

  if (isLoading) return <Spin style={{ display: "block", margin: "60px auto" }} />;
  if (!data) return null;
  const zoneColor = (z: WorkbenchZone) =>
    mode === "inherent" ? (z.inherent_effective_color ?? z.effective_color) : z.effective_color;

  return (
    <div
      ref={containerRef}
      data-testid="risk-distribution-stage"
      data-fit-scale={viewTransform.scale}
      data-container-width={containerSize.width}
      data-container-height={containerSize.height}
      style={{ width: "100%", height: "100%", overflow: "hidden", background: "#fafafa", position: "relative" }}
    >
      <Stage
        width={containerSize.width || width}
        height={containerSize.height || height}
        scaleX={viewTransform.scale}
        scaleY={viewTransform.scale}
        x={viewTransform.x}
        y={viewTransform.y}
      >
        <Layer>
          {data.zones.map(z =>
            (z.floor_plan_polygon?.polygons || []).map(p => {
              const isHighlighted = highlightZone === z.id;
              return (
                <Line
                  key={p.id}
                  points={pointsToKonva(p.points, width, height)}
                  closed
                  fill={zoneColor(z) || "#d9d9d9"}
                  opacity={isHighlighted ? 0.6 : 0.35}
                  stroke={zoneColor(z) || "#d9d9d9"}
                  strokeWidth={isHighlighted ? 4 : 2}
                  onClick={() => onZoneClick?.(z.id)}
                />
              );
            }),
          )}
          {data.riskPoints.map(p => (
            <Circle
              key={p.id}
              x={toCanvasX(p.location_x ?? 0, width)}
              y={toCanvasY(p.location_y ?? 0, height)}
              radius={6}
              fill="#1677ff"
              stroke="#fff"
              strokeWidth={2}
            />
          ))}
          {data.zones.map(z => {
            const first = z.floor_plan_polygon?.polygons?.[0]?.points?.[0];
            return first ? (
              <KonvaText
                key={z.id}
                x={toCanvasX(first.x, width)}
                y={toCanvasY(first.y, height) - 14}
                text={z.name}
                fontSize={13}
                fill="#333"
              />
            ) : null;
          })}
          {data.texts.map(t => (
            <KonvaText
              key={t.id}
              x={toCanvasX(t.x, width)}
              y={toCanvasY(t.y, height)}
              text={t.content}
              fontSize={t.font_size}
              fill={t.color}
              rotation={t.rotation}
            />
          ))}
        </Layer>
      </Stage>
    </div>
  );
}
