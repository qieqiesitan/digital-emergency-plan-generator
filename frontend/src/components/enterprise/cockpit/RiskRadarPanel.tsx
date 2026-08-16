import type { ZoneRisk } from "@/types/cockpit";
import { RISK_LEVEL_COLORS } from "@/types/cockpit";

const DOTS = [
  { top: "34%", left: "62%", color: "#ff4d4f", delay: 0 },
  { top: "58%", left: "32%", color: "#ff9f43", delay: 0.5 },
  { top: "24%", left: "40%", color: "#ffd666", delay: 1 },
  { top: "66%", left: "58%", color: "#40a9ff", delay: 1.4 },
  { top: "48%", left: "74%", color: "#ff9f43", delay: 0.8 },
];

interface Props {
  riskIndex: number;
  zoneRisks: ZoneRisk[];
}

const LEVEL_ORDER = ["major", "larger", "general", "low"] as const;

export default function RiskRadarPanel({ riskIndex, zoneRisks }: Props) {
  return (
    <div className="cp-panel" style={{ flex: 1 }}>
      <i className="cp-corner tl" /><i className="cp-corner tr" />
      <i className="cp-corner bl" /><i className="cp-corner br" />
      <div className="cp-h" style={{ justifyContent: "space-between" }}>
        <span style={{ display: "flex", alignItems: "center", gap: 8 }}>风险雷达 <b>LIVE</b></span>
        <span className="right">扫描中 · 每 4.2s 刷新</span>
      </div>
      <div className="cp-radar">
        <div className="r r1" /><div className="r r2" /><div className="r r3" /><div className="r r4" />
        <div className="x h" /><div className="x v" />
        <div className="cp-sweep" />
        <div className="cp-orbit"><i /></div>
        <div className="cp-orbit o2"><i /></div>
        {DOTS.map((d, i) => (
          <div
            key={i}
            className="cp-riskdot"
            style={{ top: d.top, left: d.left, background: d.color, color: d.color, boxShadow: `0 0 12px ${d.color}`, animationDelay: `${d.delay}s` }}
          />
        ))}
        <div className="cp-radar-center">
          <b>{riskIndex > 0 ? riskIndex : "--"}</b>
          <span>综合风险指数</span>
        </div>
      </div>
      <div className="cp-radar-cap">风险点实时定位 · 圆心为风险指数 <b>{riskIndex > 0 ? riskIndex : "--"} / 100</b></div>
      <div className="cp-h" style={{ marginTop: 12 }}>
        <span style={{ display: "flex", alignItems: "center", gap: 8 }}>分区风险分布</span>
        <span className="right">按管控区域</span>
      </div>
      <div className="cp-bars">
        {zoneRisks.length === 0 ? (
          <div className="cp-empty">暂无分区数据</div>
        ) : (
          zoneRisks.slice(0, 4).map((z) => (
            <div className="cp-bar-row" key={z.zone_name}>
              <span className="nm">{z.zone_name}</span>
              <div className="cp-bar">
                {LEVEL_ORDER.map((k) =>
                  z.counts[k] > 0 ? (
                    <i key={k} style={{ width: `${(z.counts[k] / z.total) * 100}%`, background: RISK_LEVEL_COLORS[k] }} />
                  ) : null,
                )}
              </div>
              <span className="tot">{z.total}</span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
