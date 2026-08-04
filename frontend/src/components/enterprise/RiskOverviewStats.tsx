import React, { useMemo } from "react";
import type { HierarchyZone } from "@/types/riskManagement";

interface Props {
  zones: HierarchyZone[];
}

interface StatsData {
  totalZones: number;
  totalObjects: number;
  totalEvents: number;
  totalMeasures: number;
  implementedMeasures: number;
  riskDistribution: { name: string; value: number; color: string }[];
  accidentTypeTop5: { name: string; count: number }[];
}

const PIE_COLORS: Record<string, string> = {
  "重大": "#ff4d4f",
  "较大": "#fa8c16",
  "一般": "#fadb14",
  "低": "#52c41a",
  "未知": "#d9d9d9",
};

function computeStats(zones: HierarchyZone[]): StatsData {
  let totalZones = 0;
  let totalObjects = 0;
  let totalEvents = 0;
  let totalMeasures = 0;
  let implementedMeasures = 0;
  const riskLevelCounts: Record<string, number> = {};
  const accidentTypeCounts: Record<string, number> = {};

  for (const zone of zones) {
    totalZones++;
    for (const obj of zone.objects || []) {
      totalObjects++;
      // Direct events on object
      for (const ev of obj.events || []) {
        totalEvents++;
        totalMeasures += (ev.measures || []).length;
        implementedMeasures += (ev.measures || []).filter((m) => m.status === "implemented").length;
        const rl = ev.risk_level || "未知";
        riskLevelCounts[rl] = (riskLevelCounts[rl] || 0) + 1;
        const at = ev.accident_type || "未知";
        accidentTypeCounts[at] = (accidentTypeCounts[at] || 0) + 1;
      }
      // Events under units
      for (const unit of obj.units || []) {
        for (const ev of unit.events || []) {
          totalEvents++;
          totalMeasures += (ev.measures || []).length;
          implementedMeasures += (ev.measures || []).filter((m) => m.status === "implemented").length;
          const rl = ev.risk_level || "未知";
          riskLevelCounts[rl] = (riskLevelCounts[rl] || 0) + 1;
          const at = ev.accident_type || "未知";
          accidentTypeCounts[at] = (accidentTypeCounts[at] || 0) + 1;
        }
      }
    }
  }

  // Risk distribution for pie chart
  const riskDistribution = ["重大", "较大", "一般", "低"]
    .filter((level) => (riskLevelCounts[level] || 0) > 0)
    .map((name) => ({
      name,
      value: riskLevelCounts[name] || 0,
      color: PIE_COLORS[name] || "#d9d9d9",
    }));
  if ((riskLevelCounts["未知"] || 0) > 0) {
    riskDistribution.push({ name: "未知", value: riskLevelCounts["未知"], color: PIE_COLORS["未知"] });
  }

  // Accident type top 5
  const accidentTypeTop5 = Object.entries(accidentTypeCounts)
    .sort(([, a], [, b]) => b - a)
    .slice(0, 5)
    .map(([name, count]) => ({ name, count }));

  return {
    totalZones,
    totalObjects,
    totalEvents,
    totalMeasures,
    implementedMeasures,
    riskDistribution,
    accidentTypeTop5,
  };
}

const CARD_STYLE: React.CSSProperties = {
  display: "flex",
  flexDirection: "column",
  height: "100%",
  overflow: "auto",
  padding: 12,
};

const HEADING_STYLE: React.CSSProperties = {
  fontSize: 13,
  fontWeight: 600,
  color: "#333",
  marginBottom: 8,
  flexShrink: 0,
};

export default function RiskOverviewStats({ zones }: Props) {
  const stats = useMemo(() => computeStats(zones), [zones]);

  const implementedPercent =
    stats.totalMeasures > 0 ? Math.round((stats.implementedMeasures / stats.totalMeasures) * 100) : 0;

  const summaryItems = [
    { label: "分区", value: stats.totalZones },
    { label: "分析对象", value: stats.totalObjects },
    { label: "风险事件", value: stats.totalEvents },
    { label: "管控措施", value: stats.totalMeasures },
    { label: "措施落实率", value: `${implementedPercent}%` },
  ];
  const maxRiskCount = stats.riskDistribution.reduce((max, item) => Math.max(max, item.value), 1);
  const maxAccidentCount = stats.accidentTypeTop5.reduce((max, item) => Math.max(max, item.count), 1);

  if (zones.length === 0) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100%", color: "#8c8c8c" }}>
        暂无统计数据
      </div>
    );
  }

  return (
    <div style={CARD_STYLE}>
      {/* Charts row */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, flex: 1, minHeight: 0 }}>
        {/* Risk level distribution */}
        <div style={{ display: "flex", flexDirection: "column", minWidth: 0 }}>
          <div style={HEADING_STYLE}>风险等级分布</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 8, flex: 1, minHeight: 0, overflow: "auto" }}>
            {stats.riskDistribution.length > 0 ? stats.riskDistribution.map((item) => (
              <div key={item.name}>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, marginBottom: 4 }}>
                  <span>{item.name}</span>
                  <span>{item.value}</span>
                </div>
                <div style={{ height: 12, background: "#f5f5f5", borderRadius: 6, overflow: "hidden" }}>
                  <div
                    style={{
                      width: `${(item.value / maxRiskCount) * 100}%`,
                      height: "100%",
                      background: item.color,
                      borderRadius: 6,
                    }}
                  />
                </div>
              </div>
            )) : <div style={{ color: "#999", fontSize: 12 }}>暂无风险等级数据</div>}
          </div>
        </div>
        {/* Accident type top 5 */}
        <div style={{ display: "flex", flexDirection: "column", minWidth: 0 }}>
          <div style={HEADING_STYLE}>事故类型 Top 5</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 8, flex: 1, minHeight: 0, overflow: "auto" }}>
            {stats.accidentTypeTop5.length > 0 ? stats.accidentTypeTop5.map((item) => (
              <div key={item.name}>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, marginBottom: 4, gap: 8 }}>
                  <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", flex: 1 }}>{item.name}</span>
                  <span>{item.count}</span>
                </div>
                <div style={{ height: 12, background: "#f5f5f5", borderRadius: 6, overflow: "hidden" }}>
                  <div
                    style={{
                      width: `${(item.count / maxAccidentCount) * 100}%`,
                      height: "100%",
                      background: "#1677ff",
                      borderRadius: 6,
                    }}
                  />
                </div>
              </div>
            )) : <div style={{ color: "#999", fontSize: 12 }}>暂无事故类型数据</div>}
          </div>
        </div>
      </div>
      {/* Summary row */}
      <div
        style={{
          display: "flex",
          gap: 0,
          marginTop: 8,
          border: "1px solid #f0f0f0",
          borderRadius: 6,
          overflow: "hidden",
          flexShrink: 0,
        }}
      >
        {summaryItems.map((item, idx) => (
          <div
            key={item.label}
            style={{
              flex: 1,
              textAlign: "center",
              padding: "8px 4px",
              borderRight: idx < summaryItems.length - 1 ? "1px solid #f0f0f0" : "none",
              background: "#fafafa",
            }}
          >
            <div style={{ fontSize: 20, fontWeight: 700, color: "#1677ff", lineHeight: "28px" }}>{item.value}</div>
            <div style={{ fontSize: 11, color: "#999", lineHeight: "18px" }}>{item.label}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
