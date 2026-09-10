/* ── L×S 风险评估计算表解析（预览页顶部统计用） ── */

export interface RiskTableRow {
  key: number;
  accidentType: string;
  l: number;
  s: number;
  r: number;
  level: string;
}

export function getRiskLevelTag(r: number): { label: string; color: string } {
  if (r <= 8) return { label: "低风险", color: "green" };
  if (r <= 12) return { label: "一般风险", color: "orange" };
  if (r <= 16) return { label: "较大风险", color: "volcano" };
  return { label: "重大风险", color: "red" };
}

export function countByLevel(rows: RiskTableRow[]): Record<string, number> {
  const counts: Record<string, number> = {
    重大风险: 0,
    较大风险: 0,
    一般风险: 0,
    低风险: 0,
  };
  for (const row of rows) {
    const tag = getRiskLevelTag(row.r);
    counts[tag.label] = (counts[tag.label] || 0) + 1;
  }
  return counts;
}

type RiskHeader = {
  rowIndex: number;
  lIdx: number;
  sIdx: number;
  rIdx: number;
  typeIdx: number;
  levelIdx: number;
};

const TR_RE = /<tr[^>]*>[\s\S]*?<\/tr>/gi;
const CELL_RE = /<t[dh][^>]*>([\s\S]*?)<\/t[dh]>/gi;

function cellsOf(tr: string): string[] {
  const cells: string[] = [];
  const matches = tr.matchAll(CELL_RE);
  for (const m of matches) {
    cells.push(m[1].replace(/<[^>]+>/g, "").replace(/&nbsp;/gi, " ").trim());
  }
  return cells;
}

function toNumber(raw: string | undefined): number | null {
  if (!raw) return null;
  const m = raw.match(/\d+/);
  return m ? parseInt(m[0], 10) : null;
}

function isLHeader(cell: string): boolean {
  const t = cell.replace(/\s+/g, "");
  return /^l$/i.test(t)
    || /^l[（(:：]/.test(t)
    || /^l值/i.test(t)
    || t.includes("可能性")
    || t.includes("可能度");
}

function isSHeader(cell: string): boolean {
  const t = cell.replace(/\s+/g, "");
  return /^s$/i.test(t)
    || /^s[（(:：]/.test(t)
    || /^s值/i.test(t)
    || t.includes("严重性")
    || t.includes("后果严重");
}

function isRHeader(cell: string): boolean {
  const t = cell.replace(/\s+/g, "");
  return /^r$/i.test(t)
    || /^r[（(:：]/.test(t)
    || /^r值/i.test(t)
    || t.includes("风险值")
    || t.includes("风险度");
}

/** 在单个 <table> 中找到含 L/S/R 列名的表头行并返回各列下标。 */
function findRiskHeader(rows: string[][]): RiskHeader | null {
  for (let i = 0; i < rows.length; i += 1) {
    const row = rows[i];
    const lIdx = row.findIndex(isLHeader);
    const sIdx = row.findIndex(isSHeader);
    const rIdx = row.findIndex(isRHeader);
    if (lIdx >= 0 && sIdx >= 0 && rIdx >= 0
      && new Set([lIdx, sIdx, rIdx]).size === 3) {
      const typeIdx = row.findIndex((c) => c.includes("事故类型"));
      let levelIdx = row.findIndex((c) => c.includes("风险等级"));
      if (levelIdx < 0) levelIdx = row.findIndex((c) => c === "等级");
      return { rowIndex: i, lIdx, sIdx, rIdx, typeIdx, levelIdx };
    }
  }
  return null;
}

/**
 * 从报告 HTML 中解析 L×S 评估表。
 * 旧实现按固定第 2/3/4 列取 L/S/R 且扫描全文所有 <tr>，
 * 会把化学品 CAS 表（64-17-5 / 7722-76-1）误解析成 R=7722，
 * 也会漏掉「序号|评估对象|事故类型|L|S|R|风险等级」等带前导列的版式。
 * 现改为按表头列位（L/S/R 列名）定位，只解析匹配的表格。
 */
export function parseRiskTable(html: string): RiskTableRow[] {
  const rows: RiskTableRow[] = [];
  const tables = html.match(/<table[^>]*>[\s\S]*?<\/table>/gi) || [];

  for (const table of tables) {
    const trs = table.match(TR_RE) || [];
    const rowCells = trs.map(cellsOf);
    const header = findRiskHeader(rowCells);
    if (!header) continue;

    for (let i = header.rowIndex + 1; i < rowCells.length; i += 1) {
      const cells = rowCells[i];
      const l = toNumber(cells[header.lIdx]);
      const s = toNumber(cells[header.sIdx]);
      const r = toNumber(cells[header.rIdx]);
      if (l === null || s === null || r === null) continue;
      rows.push({
        key: rows.length + 1,
        accidentType: header.typeIdx >= 0 ? (cells[header.typeIdx] ?? "") : (cells[0] ?? ""),
        l,
        s,
        r,
        level: header.levelIdx >= 0 ? (cells[header.levelIdx] ?? "") : "",
      });
    }
  }
  return rows;
}
