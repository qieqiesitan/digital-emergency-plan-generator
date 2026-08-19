import { useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { Stage, Layer, Line, Circle, Text as KonvaText, Image as KonvaImage } from "react-konva";
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
  const [floorPlanImg, setFloorPlanImg] = useState<HTMLImageElement | null>(null);
  const [floorPlanImgUrl, setFloorPlanImgUrl] = useState<string | null>(null);
  const floor = data?.floors[0];
  const floorPlanUrl = floor?.floor_plan_url ?? null;

  useEffect(() => {
    if (!floorPlanUrl) return;
    const img = new window.Image();
    img.onload = () => {
      setImageSize({ width: img.naturalWidth, height: img.naturalHeight });
      setFloorPlanImg(img);
      setFloorPlanImgUrl(floorPlanUrl);
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
  // 仅当已加载图片与当前楼层底图 URL 一致时才作为底图，切换楼层不闪现旧图
  const activePlanImg = floorPlanImgUrl === floorPlanUrl ? floorPlanImg : null;

  // 与四色图工作台一致：按整张画布（floor.canvas_width/height）等比适配并居中，
  // 避免「按内容包围盒缩放」导致风险点/分区相对底图整体偏移。
  const viewTransform = useMemo(() => {
    if (!containerSize.width || !containerSize.height) {
      return { scale: 1, x: 0, y: 0 };
    }
    const scale = Math.min(
      4,
      Math.max(0.25, Math.min(containerSize.width / width, containerSize.height / height)),
    );
    const x = (containerSize.width - width * scale) / 2;
    const y = (containerSize.height - height * scale) / 2;
    return { scale, x, y };
  }, [containerSize, width, height]);

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
          {activePlanImg && (
            <KonvaImage
              image={activePlanImg}
              width={width}
              height={height}
              listening={false}
            />
          )}
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
