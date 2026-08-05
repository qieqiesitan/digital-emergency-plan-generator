import { Group, Circle, Text } from "react-konva";
import { useRiskMappingWorkbenchStore } from "@/store/riskMappingWorkbenchStore";
import { toCanvasX, toCanvasY, toPercent } from "@/utils/riskMappingGeometry";

const STAGE_WIDTH = 1200;
const STAGE_HEIGHT = 900;

export default function WorkbenchRiskPointLayer() {
  const points = useRiskMappingWorkbenchStore(s => s.riskPoints);
  const floor = useRiskMappingWorkbenchStore(s => s.floors.find(f => f.id === s.currentFloorId));
  const setSnapshot = useRiskMappingWorkbenchStore.getState().setSnapshot;
  const commit = useRiskMappingWorkbenchStore.getState().commit;
  const canvasWidth = floor?.canvas_width || STAGE_WIDTH;
  const canvasHeight = floor?.canvas_height || STAGE_HEIGHT;
  return (
    <>
      {points.map(p => (
        <Group
          key={p.id}
          draggable
          x={toCanvasX(p.location_x ?? 0, canvasWidth)}
          y={toCanvasY(p.location_y ?? 0, canvasHeight)}
          onDragEnd={e => {
            const x = e.target.x();
            const y = e.target.y();
            commit();
            setSnapshot({
              riskPoints: points.map(item =>
                item.id === p.id
                  ? {
                      ...item,
                      location_x: Math.round(toPercent(x, canvasWidth) * 100) / 100,
                      location_y: Math.round(toPercent(y, canvasHeight) * 100) / 100,
                    }
                  : item,
              ),
            });
          }}
        >
          <Circle x={0} y={0} radius={6} fill="#1677ff" stroke="#fff" strokeWidth={2} />
          <Text x={8} y={-8} text={p.name} fontSize={12} />
        </Group>
      ))}
    </>
  );
}
