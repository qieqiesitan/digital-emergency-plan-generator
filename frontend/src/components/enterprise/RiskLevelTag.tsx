import { Tag } from "antd";
import type { RiskLevel } from "@/types/riskSource";
import { RISK_LEVEL_COLORS } from "@/utils/riskMethodEngine";

export function RiskLevelTag({ level }: { level: RiskLevel }) {
  return <Tag color={RISK_LEVEL_COLORS[level]}>{level}</Tag>;
}
