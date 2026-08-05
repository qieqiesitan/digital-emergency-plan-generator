import { Button, Space, Switch, Tooltip } from "antd";
import {
  AimOutlined,
  BorderOutlined,
  EditOutlined,
  HighlightOutlined,
  EnvironmentOutlined,
  FontSizeOutlined,
  DragOutlined,
} from "@ant-design/icons";
import { useRiskMappingWorkbenchStore } from "@/store/riskMappingWorkbenchStore";

const TOOLS = [
  { value: "select", label: "选择", icon: <DragOutlined /> },
  { value: "rect", label: "矩形", icon: <BorderOutlined /> },
  { value: "polygon", label: "多边形", icon: <EditOutlined /> },
  { value: "freehand", label: "自由画笔", icon: <HighlightOutlined /> },
  { value: "risk-point", label: "风险点", icon: <EnvironmentOutlined /> },
  { value: "text", label: "文字", icon: <FontSizeOutlined /> },
] as const;

export default function WorkbenchToolbar() {
  const tool = useRiskMappingWorkbenchStore(s => s.tool);
  const gridEnabled = useRiskMappingWorkbenchStore(s => s.gridEnabled);
  const snapEnabled = useRiskMappingWorkbenchStore(s => s.snapEnabled);
  const guideEnabled = useRiskMappingWorkbenchStore(s => s.guideEnabled);
  return (
    <Space wrap>
      {TOOLS.map(item => (
        <Tooltip key={item.value} title={item.label}>
          <Button
            aria-label={item.label}
            icon={item.icon}
            type={tool === item.value ? "primary" : "default"}
            onClick={() => useRiskMappingWorkbenchStore.setState({ tool: item.value })}
          />
        </Tooltip>
      ))}
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
          icon={<AimOutlined />}
          onClick={() => useRiskMappingWorkbenchStore.setState({ tool: "select" })}
        />
      </Tooltip>
    </Space>
  );
}
