import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { Stage, Layer, Line, Circle, Text as KonvaText, Image as KonvaImage } from "react-konva";
import { Spin } from "antd";
import { useQuery } from "@tanstack/react-query";
import { getRiskMappingOverview } from "@/services/riskManagementService";
import { pointsToKonva, toCanvasX, toCanvasY } from "@/utils/riskMappingGeometry";

const DEFAULT_WIDTH = 1200;
const DEFAULT_HEIGHT = 900;

interface LoadedImage {
  url: string;
  image: HTMLImageElement;
}

export default function RiskDistributionStage({
  floorId,
  highlightZone,
  onZoneClick,
}: {
  floorId?: string;
  highlightZone?: string | null;
  onZoneClick?: (zoneId: string) => void;
}) {
  const { id: enterpriseId } = useParams<{ id: string }>();
  const { data, isLoading } = useQuery({
    queryKey: ["risk-overview-stage", enterpriseId, floorId],
    queryFn: () => getRiskMappingOverview(enterpriseId!, floorId),
    enabled: !!enterpriseId,
  });
  const [loadedImage, setLoadedImage] = useState<LoadedImage | null>(null);
  const floor = data?.floors[0];
  const floorPlanUrl = floor?.floor_plan_url ?? null;

  useEffect(() => {
    if (!floorPlanUrl) {
      setLoadedImage(null);
      return;
    }
    const img = new window.Image();
    img.onload = () => setLoadedImage({ url: floorPlanUrl, image: img });
    img.src = floorPlanUrl;
    return () => {
      img.onload = null;
    };
  }, [floorPlanUrl]);

  if (isLoading) return <Spin style={{ display: "block", margin: "60px auto" }} />;
  if (!data) return null;

  const image = loadedImage && loadedImage.url === floorPlanUrl ? loadedImage.image : null;
  const width = floor?.canvas_width || (image ? image.naturalWidth : DEFAULT_WIDTH);
  const height = floor?.canvas_height || (image ? image.naturalHeight : DEFAULT_HEIGHT);

  return (
    <div style={{ width: "100%", height: "100%", overflow: "hidden", background: "#fafafa" }}>
      <Stage width={width} height={height} style={{ maxWidth: "100%", maxHeight: "100%" }}>
        <Layer>
          {image && <KonvaImage image={image} x={0} y={0} width={width} height={height} />}
          {data.zones.map(z =>
            (z.floor_plan_polygon?.polygons || []).map(p => {
              const isHighlighted = highlightZone === z.id;
              return (
                <Line
                  key={p.id}
                  points={pointsToKonva(p.points, width, height)}
                  closed
                  fill={z.effective_color || "#d9d9d9"}
                  opacity={isHighlighted ? 0.6 : 0.35}
                  stroke={z.effective_color || "#d9d9d9"}
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
