export interface RiskResult { riskLevel: string; riskScore: string; action: string; deadline: string; }

const DEFAULT_LS_THRESHOLDS = [
  { min: 20, max: 25, level: "重大", action: "立即整改", deadline: "立即" },
  { min: 15, max: 19, level: "较大", action: "立即或近期整改", deadline: "近期" },
  { min: 9, max: 14, level: "一般", action: "2年内治理", deadline: "2年" },
  { min: 1, max: 8, level: "低", action: "有条件有经费时治理", deadline: "有条件时" },
];

const DEFAULT_LEC_THRESHOLDS = [
  { min: 320, max: 9999, level: "重大", action: "立即停止作业整改", deadline: "立即" },
  { min: 160, max: 319, level: "较大", action: "立即或近期整改", deadline: "近期" },
  { min: 70, max: 159, level: "一般", action: "限期整改", deadline: "限期" },
  { min: 0, max: 69, level: "低", action: "日常管理", deadline: "持续" },
];

function findLevel(score: number, thresholds: typeof DEFAULT_LS_THRESHOLDS): RiskResult {
  for (const t of thresholds) { if (score >= t.min && score <= t.max) return { riskLevel: t.level, riskScore: "", action: t.action, deadline: t.deadline }; }
  return { riskLevel: "低", riskScore: "", action: "日常管理", deadline: "持续" };
}

export function computeRiskLS(l: number, s: number, thresholds = DEFAULT_LS_THRESHOLDS): RiskResult {
  const r = l * s; const result = findLevel(r, thresholds); result.riskScore = `R=${r}`; return result;
}

export function computeRiskLEC(l: number, e: number, c: number, thresholds = DEFAULT_LEC_THRESHOLDS): RiskResult {
  const d = Math.round(l * e * c); const result = findLevel(d, thresholds); result.riskScore = `D=${d}`; return result;
}

export const RISK_LEVEL_COLORS: Record<string, string> = { "重大": "#ff4d4f", "较大": "#fa8c16", "一般": "#fadb14", "低": "#52c41a" };
export const MEASURE_CATEGORY_LABELS: Record<string, string> = { engineering: "工程技术", management: "管理措施", ppe: "个体防护", emergency: "应急处置" };
export const ACCIDENT_TYPES = ["物体打击","车辆伤害","机械伤害","起重伤害","触电","淹溺","灼烫","火灾","高处坠落","坍塌","锅炉爆炸","容器爆炸","其他爆炸","中毒和窒息","其他伤害"];
export function getCellClass(r: number): string { if (r >= 20) return "lvl-red"; if (r >= 15) return "lvl-orange"; if (r >= 9) return "lvl-yellow"; return "lvl-green"; }

export function renderMatrixData(methodType: string, thresholds = DEFAULT_LS_THRESHOLDS): { l: number; s: number; r: number; level: string; color: string }[][] {
  const rows: { l: number; s: number; r: number; level: string; color: string }[][] = [];
  for (let l = 1; l <= 5; l++) {
    const row: typeof rows[0] = [];
    for (let s = 1; s <= 5; s++) {
      const r = l * s;
      const result = findLevel(r, thresholds);
      const color = RISK_LEVEL_COLORS[result.riskLevel] || "#52c41a";
      row.push({ l, s, r, level: result.riskLevel, color });
    }
    rows.push(row);
  }
  return rows;
}
