import type {
  AiSignReviewResponse,
  RightColumn,
  SignCategory,
  SignItem,
} from "@/types/riskNoticeCard";

/** 标志类别展示顺序（GB 2894-2025：警告→禁止→指令→提示，与后端一致）。 */
export const SIGN_CATEGORY_ORDER: SignCategory[] = [
  "warning",
  "prohibition",
  "instruction",
  "notice",
];

/** 每类最多数量（与后端 normalize_signs 默认一致）。 */
export const MAX_SIGNS_PER_CATEGORY = 2;

/** 标志总数上限（与后端 normalize_signs 默认一致）。 */
export const MAX_TOTAL_SIGNS = 8;

/** 按 svg_name 前缀推断标志类别（svg_name 均以类别英文开头）。 */
export function categoryOf(svgName: string): SignCategory {
  if (svgName.startsWith("warning")) return "warning";
  if (svgName.startsWith("prohibition")) return "prohibition";
  if (svgName.startsWith("instruction")) return "instruction";
  return "notice";
}

/** 预览图地址（svg_name 无扩展名，与卡片渲染一致）。 */
export function signSrc(svgName: string): string {
  return `/signs/${svgName}.svg`;
}

/** 按类别排序（warning→prohibition→instruction→notice），类内保持原相对顺序。 */
export function sortSignsByCategory(signs: SignItem[]): SignItem[] {
  const position = new Map(SIGN_CATEGORY_ORDER.map((category, index) => [category, index]));
  return [...signs].sort(
    (a, b) => (position.get(a.category) ?? SIGN_CATEGORY_ORDER.length) -
      (position.get(b.category) ?? SIGN_CATEGORY_ORDER.length),
  );
}

/** svg_name → SignItem 查找表（候选库/当前标志均可）。 */
export function buildSignLookup(signs: SignItem[]): Map<string, SignItem> {
  return new Map(signs.map((sign) => [sign.svg_name, sign]));
}

/** 当前标志的中文名查找表（svg_name → name）。 */
export function buildNameLookup(signs: SignItem[]): Map<string, string> {
  return new Map(signs.map((sign) => [sign.svg_name, sign.name]));
}

/** 建议理由查找表（中文名 → 理由）。 */
export function buildReasonLookup(
  suggestion: AiSignReviewResponse["suggestion"],
): Map<string, string> {
  return new Map(suggestion.reasons.map((r) => [r.sign_name, r.reason]));
}

/** 统计各类别数量。 */
export function countSignsByCategory(signs: SignItem[]): Map<SignCategory, number> {
  const counts = new Map<SignCategory, number>();
  for (const sign of signs) {
    counts.set(sign.category, (counts.get(sign.category) ?? 0) + 1);
  }
  return counts;
}

/**
 * 把 AI 建议应用到当前标志：remove 去掉、add 加入（按 svg_name 匹配），
 * add 优先取候选库的中文名/类别（无候选库时按 svg_name 前缀推断兜底），
 * 返回按类别排序的新标志列表（与后端 normalize_signs 结果一致）。
 */
export function applySignSuggestion(
  current: SignItem[],
  suggestion: AiSignReviewResponse["suggestion"],
  catalog: SignItem[] = [],
): SignItem[] {
  const remove = new Set(suggestion.remove);
  const kept = current.filter((sign) => !remove.has(sign.svg_name));
  const existing = new Set(kept.map((sign) => sign.svg_name));
  const catalogLookup = buildSignLookup(catalog);
  const added: SignItem[] = suggestion.add
    .filter((svg) => !existing.has(svg))
    .map((svg) => {
      const fromCatalog = catalogLookup.get(svg);
      return (
        fromCatalog ?? {
          category: categoryOf(svg),
          name: svg,
          svg_name: svg,
        }
      );
    });
  return sortSignsByCategory([...kept, ...added]);
}

/**
 * 采用 AI 优化时组装完整快照 content：右栏四块原样保留，
 * 叠加当前已展示的标志与来源（signs/signs_source），
 * 避免后端 RightColumn 缺省把快照标志写空、覆盖已采用/人工调整的标志。
 * signs_source 缺失时回落 "rule"（前端按缺省处理）。
 */
export function mergeOptimizedContent(
  optimized: RightColumn,
  signs: SignItem[],
  signs_source: "rule" | "ai" | "manual" | undefined,
): RightColumn & { signs: SignItem[]; signs_source: "rule" | "ai" | "manual" } {
  return {
    ...optimized,
    signs,
    signs_source: signs_source ?? "rule",
  };
}
