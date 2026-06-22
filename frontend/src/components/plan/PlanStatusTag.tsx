import { Tag } from "antd";
import type { PlanStatus } from "@/types/plan";

const statusConfig: Record<PlanStatus, { color: string; label: string }> = {
  draft: { color: "default", label: "草稿" },
  generating: { color: "processing", label: "生成中" },
  completed: { color: "success", label: "已完成" },
};

export function PlanStatusTag({ status }: { status: PlanStatus }) {
  const config = statusConfig[status] || { color: "default", label: status };
  return <Tag color={config.color}>{config.label}</Tag>;
}
