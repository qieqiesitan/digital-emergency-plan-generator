import { Tag } from "antd";
import type { PlanType } from "@/types/plan";

const typeConfig: Record<PlanType, { color: string; label: string }> = {
  comprehensive: { color: "blue", label: "综合预案" },
  special: { color: "orange", label: "专项预案" },
  onsite: { color: "green", label: "现场处置" },
};

export function PlanTypeTag({ type }: { type: PlanType }) {
  const config = typeConfig[type] || { color: "default", label: type };
  return <Tag color={config.color}>{config.label}</Tag>;
}
