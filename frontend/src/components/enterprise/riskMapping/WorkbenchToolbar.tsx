import type { ReactNode } from "react";
import { Button, Space, Switch, Tooltip } from "antd";
import {
  AimOutlined,
  BorderOutlined,
  CloseOutlined,
  CheckOutlined,
  DeleteOutlined,
  EditOutlined,
  FullscreenOutlined,
  HighlightOutlined,
  EnvironmentOutlined,
  FontSizeOutlined,
  DragOutlined,
  NodeIndexOutlined,
  ZoomInOutlined,
  ZoomOutOutlined,
} from "@ant-design/icons";
import { useRiskMappingWorkbenchStore } from "@/store/riskMappingWorkbenchStore";

type ToolValue = "select" | "rect" | "circle" | "polygon" | "pen" | "freehand" | "risk-point" | "text";

const TOOLS: Array<{ value: ToolValue; label: string; hint: string; icon: ReactNode }> = [
  { value: "select", label: "选择", hint: "选择、拖拽和编辑对象", icon: <DragOutlined /> },
  { value: "rect", label: "矩形", hint: "按住左键拖出矩形区域", icon: <BorderOutlined /> },
  { value: "circle", label: "圆形", hint: "按住左键拖出圆形区域", icon: <AimOutlined /> },
  { value: "polygon", label: "多边形", hint: "单击添加顶点，Enter 或双击闭合", icon: <NodeIndexOutlined /> },
  { value: "pen", label: "钢笔", hint: "单击添加锚点，按住左键拖出贝塞尔控制手柄，Enter 或双击闭合", icon: <EditOutlined /> },
  { value: "freehand", label: "自由画笔", hint: "按住左键自由绘制区域", icon: <HighlightOutlined /> },
  { value: "risk-point", label: "风险点", hint: "点击放置风险点", icon: <EnvironmentOutlined /> },
  { value: "text", label: "文字", hint: "点击放置文字并立即编辑", icon: <FontSizeOutlined /> },
];

export default function WorkbenchToolbar() {
  const tool = useRiskMappingWorkbenchStore(s => s.tool);
  const gridEnabled = useRiskMappingWorkbenchStore(s => s.gridEnabled);
  const snapEnabled = useRiskMappingWorkbenchStore(s => s.snapEnabled);
  const guideEnabled = useRiskMappingWorkbenchStore(s => s.guideEnabled);
  const showFloorPlan = useRiskMappingWorkbenchStore(s => s.showFloorPlan);
  const drawingTool = ["polygon", "pen", "freehand"].includes(tool);
  const hasSelection = useRiskMappingWorkbenchStore(
    s => Boolean(s.selectedRegionId || s.selectedRiskPointId || s.selectedTextId),
  );
  return (
    <Space wrap>
      {TOOLS.map(item => (
        <Tooltip key={item.value} title={item.hint || item.label}>
          <Button
            aria-label={item.label}
            icon={item.icon}
            type={tool === item.value ? "primary" : "default"}
            onClick={() => useRiskMappingWorkbenchStore.setState({ tool: item.value })}
          />
        </Tooltip>
      ))}
      <Tooltip title="放大">
        <Button
          aria-label="放大"
          icon={<ZoomInOutlined />}
          onClick={() => useRiskMappingWorkbenchStore.getState().zoomBy(1.2)}
        />
      </Tooltip>
      <Tooltip title="缩小">
        <Button
          aria-label="缩小"
          icon={<ZoomOutOutlined />}
          onClick={() => useRiskMappingWorkbenchStore.getState().zoomBy(1 / 1.2)}
        />
      </Tooltip>
      <Tooltip title="重置缩放">
        <Button
          aria-label="重置缩放"
          icon={<FullscreenOutlined />}
          onClick={() => useRiskMappingWorkbenchStore.getState().resetView()}
        />
      </Tooltip>
      <Space size={4}>
        <Switch
          checked={gridEnabled}
          onChange={v => useRiskMappingWorkbenchStore.setState({ gridEnabled: v })}
          size="small"
        />
        <span style={{ fontSize: 12 }}>网格</span>
      </Space>
      <Space size={4}>
        <Switch
          checked={showFloorPlan}
          onChange={v => useRiskMappingWorkbenchStore.setState({ showFloorPlan: v })}
          size="small"
        />
        <span style={{ fontSize: 12 }}>平面图</span>
      </Space>
      <Space size={4}>
        <Switch
          checked={snapEnabled}
          onChange={v => useRiskMappingWorkbenchStore.setState({ snapEnabled: v })}
          size="small"
        />
        <span style={{ fontSize: 12 }}>吸附</span>
      </Space>
      <Space size={4}>
        <Switch
          checked={guideEnabled}
          onChange={v => useRiskMappingWorkbenchStore.setState({ guideEnabled: v })}
          size="small"
        />
        <span style={{ fontSize: 12 }}>辅助线</span>
      </Space>
      <Tooltip title="取消绘制（回到选择）">
        <Button
          aria-label="取消绘制"
          icon={<CloseOutlined />}
          onClick={() => useRiskMappingWorkbenchStore.setState({ tool: "select" })}
        />
      </Tooltip>
      <Tooltip title="完成绘制">
        <Button
          aria-label="完成绘制"
          icon={<CheckOutlined />}
          disabled={!drawingTool}
          onClick={() => window.dispatchEvent(new CustomEvent("risk-mapping:finish-drawing"))}
        />
      </Tooltip>
      <Tooltip title="删除所选">
        <Button
          aria-label="删除所选"
          danger
          disabled={!hasSelection}
          icon={<DeleteOutlined />}
          onClick={() => useRiskMappingWorkbenchStore.getState().deleteSelected()}
        />
      </Tooltip>
    </Space>
  );
}
