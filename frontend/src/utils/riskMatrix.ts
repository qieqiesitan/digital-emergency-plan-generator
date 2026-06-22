import type { RiskLevel } from "@/types/riskSource";

/**
 * LxS 5级风险矩阵
 * L: 1-5 (可能性), S: 1-5 (严重性), R = L x S
 */
export function calculateRiskLevel(l: number, s: number): RiskLevel {
  const r = l * s;
  if (r >= 20) return "重大";
  if (r >= 15) return "较大";
  if (r >= 9) return "一般";
  return "低";
}

export function calculateRiskScore(l: number, s: number): number {
  return l * s;
}

export const RISK_LEVEL_COLORS: Record<RiskLevel, string> = {
  "重大": "#ff4d4f",
  "较大": "#fa8c16",
  "一般": "#fadb14",
  "低": "#1890ff",
};

export const RISK_LEVEL_COLORS_HEATMAP: Record<RiskLevel, string> = {
  "重大": "#ff4d4f",
  "较大": "#fa8c16",
  "一般": "#fadb14",
  "低": "#52c41a",
};

export function getRiskColor(r: number): string {
  if (r >= 20) return "#ff4d4f";
  if (r >= 15) return "#fa8c16";
  if (r >= 9) return "#fadb14";
  return "#52c41a";
}
