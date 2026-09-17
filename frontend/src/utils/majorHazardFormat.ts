// 重大危险源展示格式化。纯函数，便于单测。

/** 后端 Decimal 走线是字符串，这里统一转换；非法值返回 null 而不是 0。 */
export function toNumber(v: string | number | null | undefined): number | null {
  if (v === null || v === undefined || v === "") return null;
  const n = typeof v === "number" ? v : Number(v);
  return Number.isFinite(n) ? n : null;
}

/** 去尾零：5.000000 -> "5"，0.300000 -> "0.3"；无法解析返回 "—"。 */
export function formatQty(v: string | number | null | undefined, digits = 6): string {
  const n = toNumber(v);
  if (n === null) return "—";
  return String(Number(n.toFixed(digits)));
}

export type LevelColor = "red" | "orange" | "gold" | "blue" | "default";

/** 等级色板：一级最重。 */
export function levelColor(level?: string | null): LevelColor {
  switch (level) {
    case "一级":
      return "red";
    case "二级":
      return "orange";
    case "三级":
      return "gold";
    case "四级":
      return "blue";
    default:
      return "default";
  }
}

/**
 * 列表"结论"列文案。
 *
 * 必须区分「不构成」（算过了，安全）与「未计算」（没算过）——两者在界面上
 * 都没有等级，看起来一样，但含义相反。混为一谈会让一张没填完的单元表
 * 在台账里显示成"安全"。
 */
export function computeConclusionText(
  latest?: { is_major_hazard: boolean; level?: string | null } | null,
): string {
  if (!latest) return "未计算";
  return latest.is_major_hazard ? latest.level || "构成" : "不构成";
}

/** 单元类型中文名。 */
export const UNIT_TYPE_LABEL: Record<string, string> = {
  production: "生产单元",
  storage: "储存单元",
};

/** α 分档提示（GB 18218 表5），供计算页在输入框旁展示。 */
export const ALPHA_HINT =
  "0 人=0.5 ｜ 1~29 人=1.0 ｜ 30~49 人=1.2 ｜ 50~99 人=1.5 ｜ ≥100 人=2.0";
