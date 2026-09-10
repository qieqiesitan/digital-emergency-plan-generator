import { describe, expect, it } from "vitest";
import { countByLevel, getRiskLevelTag, parseRiskTable } from "./riskTableParser";

/** 正文中与 L×S 无关的表格（危险化学品 CAS 表），旧实现会误把 7722-76-1 解析成 R=7722。 */
const CAS_TABLE = `
<table>
  <tr><th>参数</th><th>乙醇</th><th>异丙醇</th><th>过硫酸钾</th><th>其他</th></tr>
  <tr><td>CAS号</td><td>64-17-5</td><td>67-63-0</td><td>7722-76-1</td><td>（无固定CAS）</td></tr>
  <tr><td>密度</td><td>0.789 g/cm³</td><td>0.786 g/cm³</td><td>1.80 g/cm³</td><td>（待补充）</td></tr>
</table>`;

/** 现行版式：序号 | 评估对象（部位） | 事故类型 | L | S | R | 风险等级 */
const LS_TABLE_7COL = `
<table>
  <tr><th>序号</th><th>评估对象（部位）</th><th>事故类型</th><th>L</th><th>S</th><th>R</th><th>风险等级</th></tr>
  <tr><td>1</td><td>厨房/燃气灶台/使用操作单元</td><td>火灾爆炸</td><td>3</td><td>5</td><td>15</td><td>较大风险</td></tr>
  <tr><td>2</td><td>厨房/燃气灶台/使用操作单元</td><td>火灾</td><td>3</td><td>4</td><td>12</td><td>一般风险</td></tr>
  <tr><td>34</td><td>办公区/办公区域/办公区整体</td><td>人员滑倒/摔伤</td><td>1</td><td>3</td><td>3</td><td>低风险</td></tr>
</table>`;

/** 旧版式：序号 | 事故类型 | L | S | R | 风险等级 */
const LS_TABLE_6COL = `
<table>
  <tr><th>序号</th><th>事故类型</th><th>L</th><th>S</th><th>R</th><th>风险等级</th></tr>
  <tr><td>1</td><td>机械伤害</td><td>2</td><td>3</td><td>6</td><td>低风险</td></tr>
</table>`;

/** 带中文列名的变体 */
const LS_TABLE_CHINESE_HEADER = `
<table>
  <tr><th>序号</th><th>事故类型</th><th>可能性 L</th><th>严重性 S</th><th>风险值 R(L×S)</th><th>风险等级</th></tr>
  <tr><td>1</td><td>中毒</td><td>2</td><td>4</td><td>8</td><td>低风险</td></tr>
</table>`;

describe("parseRiskTable", () => {
  it("忽略非 L×S 表格，不再把 CAS 号解析成 R=7722", () => {
    expect(parseRiskTable(CAS_TABLE)).toEqual([]);
  });

  it("按表头列位解析现行 7 列版式", () => {
    const rows = parseRiskTable(LS_TABLE_7COL);
    expect(rows).toHaveLength(3);
    expect(rows[0]).toEqual({
      key: 1,
      accidentType: "火灾爆炸",
      l: 3,
      s: 5,
      r: 15,
      level: "较大风险",
    });
    expect(rows[2]).toEqual({
      key: 3,
      accidentType: "人员滑倒/摔伤",
      l: 1,
      s: 3,
      r: 3,
      level: "低风险",
    });
  });

  it("兼容旧版 6 列版式与中文列名表头", () => {
    const old = parseRiskTable(LS_TABLE_6COL);
    expect(old[0]).toMatchObject({ accidentType: "机械伤害", l: 2, s: 3, r: 6 });

    const chinese = parseRiskTable(LS_TABLE_CHINESE_HEADER);
    expect(chinese[0]).toMatchObject({ accidentType: "中毒", l: 2, s: 4, r: 8 });
  });

  it("混合全文时只取 L×S 表中的行", () => {
    const rows = parseRiskTable(CAS_TABLE + LS_TABLE_7COL);
    expect(rows).toHaveLength(3);
    expect(Math.max(...rows.map((r) => r.r))).toBe(15);
  });
});

describe("getRiskLevelTag / countByLevel", () => {
  it("按 R 值判定等级", () => {
    expect(getRiskLevelTag(8).label).toBe("低风险");
    expect(getRiskLevelTag(12).label).toBe("一般风险");
    expect(getRiskLevelTag(15).label).toBe("较大风险");
    expect(getRiskLevelTag(20).label).toBe("重大风险");
  });

  it("统计各等级数量", () => {
    const rows = parseRiskTable(LS_TABLE_7COL);
    expect(countByLevel(rows)).toEqual({
      低风险: 1,
      一般风险: 1,
      较大风险: 1,
      重大风险: 0,
    });
  });
});
