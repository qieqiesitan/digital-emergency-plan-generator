import { Button, Empty } from "antd";
import type { CSSProperties, ReactNode } from "react";

export interface AppEmptyProps {
  /** 主说明文案（如「暂无预案」） */
  title: ReactNode;
  /** 次要引导说明（可选） */
  description?: ReactNode;
  /** 主操作按钮文案；与 onAction 成对出现（可选） */
  actionLabel?: ReactNode;
  /** 主操作回调（可选） */
  onAction?: () => void;
  /** 自定义插图/图标（可选；默认 antd 简洁插图） */
  icon?: ReactNode;
  className?: string;
  style?: CSSProperties;
}

/**
 * 全站统一空状态三件套（审查报告 5.1）：
 * 插图/图标 + 主说明（+次说明） + 主操作按钮/引导。
 * 表格 locale.emptyText、列表空分支、页面级空态均可用。
 */
export default function AppEmpty({
  title,
  description,
  actionLabel,
  onAction,
  icon,
  className,
  style,
}: AppEmptyProps) {
  return (
    <Empty
      className={className}
      style={style}
      image={icon ?? Empty.PRESENTED_IMAGE_SIMPLE}
      description={
        <div style={{ padding: "4px 0" }}>
          <div style={{ color: "rgba(0, 0, 0, 0.88)", fontSize: 14, fontWeight: 500 }}>
            {title}
          </div>
          {description ? (
            <div style={{ color: "rgba(0, 0, 0, 0.45)", fontSize: 13, marginTop: 4 }}>
              {description}
            </div>
          ) : null}
        </div>
      }
    >
      {actionLabel && onAction ? (
        <Button type="primary" onClick={onAction}>
          {actionLabel}
        </Button>
      ) : null}
    </Empty>
  );
}
