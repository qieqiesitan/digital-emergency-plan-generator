import { Alert, Button } from "antd";
import { useNavigate } from "react-router-dom";
import { AI_CONFIG_ROUTE, AI_NOT_CONFIGURED_HINT } from "@/utils/aiUnavailable";

interface AiNotConfiguredHintProps {
  /** 关闭回调；传入后 Alert 右上角显示关闭按钮 */
  onClose?: () => void;
}

/**
 * AI 未配置统一引导（审查报告 I7）。
 *
 * Chat / 悬浮球（embedded Chat）/ 一键生成三个入口共用：展示
 * "系统尚未配置 AI 模型…" 引导并提供跳转 设置→AI 配置 的按钮。
 */
export default function AiNotConfiguredHint({ onClose }: AiNotConfiguredHintProps) {
  const navigate = useNavigate();

  return (
    <Alert
      type="warning"
      showIcon
      message={AI_NOT_CONFIGURED_HINT}
      closable={!!onClose}
      onClose={onClose}
      action={
        <Button size="small" type="primary" onClick={() => navigate(AI_CONFIG_ROUTE)}>
          前往 AI 配置
        </Button>
      }
      style={{ marginBottom: 8 }}
    />
  );
}
