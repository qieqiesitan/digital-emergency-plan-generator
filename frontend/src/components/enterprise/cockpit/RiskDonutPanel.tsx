import type { RiskCounts, TopRisk } from "@/types/cockpit";
import { RISK_LEVEL_COLORS, RISK_LEVEL_LABELS } from "@/types/cockpit";

const LEVEL_CN_COLORS: Record<string, string> = {
  重大: "#ff4d4f",
  较大: "#ff9f43",
  一般: "#ffd666",
  低: "#40a9ff",
};

const ORDER: Array<keyof RiskCounts> = ["major", "larger", "general", "low"];

function donutBackground(counts: RiskCounts): string {
  if (counts.total <= 0) return "rgba(255,255,255,.06)";
  let cursor = 0;
  const stops = ORDER.map((key) => {
    const pct = (counts[key] / counts.total) * 100;
    const start = cursor;
    cursor += pct;
    return `${RISK_LEVEL_COLORS[key]} ${start}% ${cursor}%`;
  });
  return `conic-gradient(${stops.join(", ")})`;
}

interface Props {
  counts: RiskCounts;
  topRisks: TopRisk[];
}

export default function RiskDonutPanel({ counts, topRisks }: Props) {
  return (
    <div className="cp-panel">
      <i className="cp-corner tl" /><i className="cp-corner tr" />
      <i className="cp-corner bl" /><i className="cp-corner br" />
      <div className="cp-h">风险等级分布</div>
      <div className="cp-donut" style={{ background: donutBackground(counts) }} />
      <div className="cp-donut-center">
        <b>{counts.total > 0 ? counts.total : "--"}</b>
        <span>风险事件</span>
      </div>
      <div className="cp-legend">
        {ORDER.map((key) => (
          <div className="cp-lg" key={key}>
            <span><i style={{ background: RISK_LEVEL_COLORS[key] }} />{RISK_LEVEL_LABELS[key]}</span>
            <b>{counts[key]}</b>
          </div>
        ))}
      </div>
      <div className="cp-h" style={{ marginTop: 14 }}>重大风险 TOP</div>
      {topRisks.length === 0 ? (
        <div className="cp-empty">暂无高风险数据</div>
      ) : (
        topRisks.slice(0, 3).map((r) => (
          <div className="cp-todo" style={{ marginBottom: 0 }} key={r.name}>
            <span className="lv" style={{ background: LEVEL_CN_COLORS[r.level] || "#8aa3c8" }} />
            <div>
              <b>{r.name}</b>
              <span>综合得分 {r.score ?? "--"} · {r.responsible_unit ?? "未指定责任单位"}</span>
            </div>
          </div>
        ))
      )}
    </div>
  );
}
