import { Button, Space, Tag } from "antd";
import {
  CheckCircleFilled,
  CloseCircleFilled,
  LoadingOutlined,
  RedoOutlined,
  ThunderboltOutlined,
} from "@ant-design/icons";

/**
 * 单章生成/重新生成按钮（报告工作台专用，交互对齐预案 AIGenerateButton）。
 * 生成中显示进行中状态并允许停止（由父组件 AbortController 控制）。
 */
interface ReportChapterActionsProps {
  generate: () => void;       // 生成本章（空章节）
  regenerate: () => void;     // 重新生成（已有内容，父组件确认）
  stop?: () => void;
  disabled?: boolean;
  loading?: boolean;
  hasContent?: boolean;
}

export default function ReportChapterActions({
  generate,
  regenerate,
  stop,
  disabled,
  loading,
  hasContent,
}: ReportChapterActionsProps) {
  if (loading) {
    return (
      <Space>
        <Button size="small" icon={<LoadingOutlined />} onClick={stop} disabled={disabled}>
          生成中... 停止
        </Button>
        <Tag icon={<LoadingOutlined />} color="processing">
          AI 生成中
        </Tag>
      </Space>
    );
  }
  return (
    <Space>
      <Button
        size="small"
        type="primary"
        ghost
        icon={hasContent ? <RedoOutlined /> : <ThunderboltOutlined />}
        disabled={disabled}
        onClick={() => {
          if (hasContent) regenerate();
          else generate();
        }}
      >
        {hasContent ? "重新生成本章" : "生成本章"}
      </Button>
      {hasContent && (
        <Tag icon={<CheckCircleFilled />} color="success">
          已有内容
        </Tag>
      )}
      {disabled && hasContent && (
        <Tag icon={<CloseCircleFilled />} color="warning">
          全局生成中
        </Tag>
      )}
    </Space>
  );
}
