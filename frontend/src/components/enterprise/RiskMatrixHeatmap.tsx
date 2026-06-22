import React from "react";

interface RiskMatrixHeatmapProps {
  /** Optional highlighted cells: [L, S] pairs to highlight */
  highlights?: Array<{ l: number; s: number; label?: string }>;
  /** Optional: show compact version */
  compact?: boolean;
}

/**
 * LxS 风险矩阵热力图
 * 5x5 grid where R = L x S
 * Colors: green (low) -> yellow (medium) -> orange (high) -> red (critical)
 */
export default function RiskMatrixHeatmap({ highlights, compact }: RiskMatrixHeatmapProps) {
  const lLevels = [1, 2, 3, 4, 5];
  const sLevels = [1, 2, 3, 4, 5];

  const getRiskColor = (r: number): string => {
    if (r >= 20) return "#ff4d4f"; // critical red
    if (r >= 15) return "#fa8c16"; // high orange
    if (r >= 9) return "#fadb14"; // medium yellow
    return "#52c41a"; // low green
  };

  const getRiskLabel = (r: number): string => {
    if (r >= 20) return "重大";
    if (r >= 15) return "较大";
    if (r >= 9) return "一般";
    return "低";
  };

  const isHighlighted = (l: number, s: number): boolean => {
    return highlights?.some((h) => h.l === l && h.s === s) ?? false;
  };

  const getHighlightLabel = (l: number, s: number): string | undefined => {
    return highlights?.find((h) => h.l === l && h.s === s)?.label;
  };

  const cellSize = compact ? 48 : 64;

  return (
    <div style={{ overflowX: "auto" }}>
      <div
        style={{
          display: "inline-grid",
          gridTemplateColumns: `${compact ? 48 : 60}px repeat(5, ${cellSize}px)`,
          gridTemplateRows: `${compact ? 28 : 36}px repeat(5, ${cellSize}px)`,
          gap: 1,
          background: "#d9d9d9",
          border: "1px solid #d9d9d9",
          borderRadius: 6,
          overflow: "hidden",
        }}
      >
        {/* Corner cell */}
        <div
          style={{
            background: "#f5f5f5",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: compact ? 11 : 12,
            color: "#666",
            fontWeight: 600,
          }}
        >
          L\S
        </div>
        {/* S headers */}
        {sLevels.map((s) => (
          <div
            key={`s-${s}`}
            style={{
              background: "#f5f5f5",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: compact ? 11 : 12,
              color: "#333",
              fontWeight: 600,
            }}
          >
            S={s}
          </div>
        ))}
        {/* Matrix rows */}
        {lLevels.map((l) => (
          <React.Fragment key={`row-${l}`}>
            {/* L header */}
            <div
              style={{
                background: "#f5f5f5",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: compact ? 11 : 12,
                color: "#333",
                fontWeight: 600,
              }}
            >
              L={l}
            </div>
            {/* Cells */}
            {sLevels.map((s) => {
              const r = l * s;
              const bgColor = getRiskColor(r);
              const highlighted = isHighlighted(l, s);
              const label = getHighlightLabel(l, s);
              return (
                <div
                  key={`${l}-${s}`}
                  title={`L=${l}, S=${s}, R=${r} (${getRiskLabel(r)}风险)`}
                  style={{
                    background: bgColor,
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "center",
                    justifyContent: "center",
                    fontSize: compact ? 10 : 12,
                    color: r >= 15 ? "#fff" : r >= 9 ? "#333" : "#fff",
                    fontWeight: 600,
                    position: "relative",
                    border: highlighted ? "3px solid #000" : undefined,
                    borderRadius: highlighted ? 4 : 0,
                    cursor: "default",
                    transition: "transform 0.1s",
                  }}
                  onMouseEnter={(e) => {
                    (e.currentTarget as HTMLElement).style.transform = "scale(1.05)";
                  }}
                  onMouseLeave={(e) => {
                    (e.currentTarget as HTMLElement).style.transform = "scale(1)";
                  }}
                >
                  <span>{r}</span>
                  {!compact && (
                    <span style={{ fontSize: 9, opacity: 0.8 }}>
                      {getRiskLabel(r)}
                    </span>
                  )}
                  {label && (
                    <span
                      style={{
                        fontSize: 8,
                        position: "absolute",
                        bottom: 2,
                        color: r >= 15 ? "#fff" : "#000",
                      }}
                    >
                      {label}
                    </span>
                  )}
                </div>
              );
            })}
          </React.Fragment>
        ))}
      </div>

      {/* Legend */}
      <div
        style={{
          display: "flex",
          gap: 16,
          marginTop: 12,
          flexWrap: "wrap",
        }}
      >
        {[
          { color: "#52c41a", label: "低风险 (R<8)" },
          { color: "#fadb14", label: "一般风险 (R=9-12)" },
          { color: "#fa8c16", label: "较大风险 (R=15-16)" },
          { color: "#ff4d4f", label: "重大风险 (R=20-25)" },
        ].map((item) => (
          <div
            key={item.label}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 6,
              fontSize: 12,
              color: "#666",
            }}
          >
            <div
              style={{
                width: 14,
                height: 14,
                background: item.color,
                borderRadius: 3,
                border: "1px solid rgba(0,0,0,0.1)",
              }}
            />
            {item.label}
          </div>
        ))}
      </div>
    </div>
  );
}
