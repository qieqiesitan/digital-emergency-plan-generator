import { RISK_LEVEL_COLORS } from "@/utils/riskMethodEngine";

const LEGEND_ITEMS: [string, string][] = [
  ...Object.entries(RISK_LEVEL_COLORS),
  ["未评估", "#d9d9d9"],
];

export default function WorkbenchLegend() {
  return (
    <div
      style={{
        position: "absolute",
        left: 12,
        bottom: 12,
        background: "rgba(255,255,255,.92)",
        borderRadius: 8,
        padding: 8,
        fontSize: 12,
        zIndex: 1,
      }}
    >
      {LEGEND_ITEMS.map(([level, color]) => (
        <div key={level} style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span style={{ width: 14, height: 14, background: color, borderRadius: 3, display: "inline-block" }} />
          {level}
        </div>
      ))}
    </div>
  );
}
