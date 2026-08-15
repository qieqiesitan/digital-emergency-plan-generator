import React, { useMemo, useCallback, useState } from "react";
import { Tooltip } from "antd";
import type { HierarchyZone, HierarchyEvent } from "@/types/riskManagement";
import { RISK_LEVEL_COLORS } from "@/utils/riskMethodEngine";

interface Props {
  zones: HierarchyZone[];
  onEventFilter: (ids: string[]) => void;
  mode?: "current" | "inherent";
}

interface CellData {
  l: number;
  s: number;
  events: { id: string; name: string; riskLevel: string }[];
  color: string;
}

function resolveRiskLevel(r: number): string {
  if (r >= 20) return "重大";
  if (r >= 15) return "较大";
  if (r >= 9) return "一般";
  return "低";
}

function isCellActive(activeCell: CellData | null, cell: CellData): boolean {
  if (!activeCell) return false;
  return activeCell.l === cell.l && activeCell.s === cell.s;
}

export default function RiskOverviewMatrix({ zones, onEventFilter, mode = "current" }: Props) {
  const grid = useMemo(() => {
    const cellMap = new Map<string, CellData>();

    function collectEvents(events: HierarchyEvent[]): void {
      for (const ev of events) {
        const l = ev.method_params?.L ?? ev.method_params?.l ?? 0;
        const s = ev.method_params?.S ?? ev.method_params?.s ?? 0;
        if (l < 1 || l > 5 || s < 1 || s > 5) continue;
        const key = `${l}-${s}`;
        if (!cellMap.has(key)) {
          const r = l * s;
          cellMap.set(key, { l, s, events: [], color: RISK_LEVEL_COLORS[resolveRiskLevel(r)] || "#52c41a" });
        }
        cellMap.get(key)!.events.push({
          id: ev.id,
          name: ev.accident_type,
          riskLevel:
            (mode === "inherent" ? (ev.inherent_risk_level ?? ev.risk_level) : ev.risk_level) ||
            resolveRiskLevel(l * s),
        });
      }
    }

    for (const zone of zones) {
      for (const obj of (zone.objects || [])) {
        if (obj.events) collectEvents(obj.events);
        for (const unit of (obj.units || [])) {
          if (unit.events) collectEvents(unit.events);
        }
      }
    }

    const rows: CellData[][] = [];
    for (let l = 1; l <= 5; l++) {
      const row: CellData[] = [];
      for (let s = 1; s <= 5; s++) {
        const key = `${l}-${s}`;
        row.push(
          cellMap.get(key) || {
            l,
            s,
            events: [],
            color: RISK_LEVEL_COLORS["低"] || "#52c41a",
          }
        );
      }
      rows.push(row);
    }
    return rows;
  }, [zones, mode]);

  const [activeCell, setActiveCell] = useState<CellData | null>(null);

  const handleCellClick = useCallback(
    (cell: CellData) => {
      if (cell.events.length === 0) return;
      if (isCellActive(activeCell, cell)) {
        setActiveCell(null);
        onEventFilter([]);
      } else {
        setActiveCell(cell);
        onEventFilter(cell.events.map((e) => e.id));
      }
    },
    [activeCell, onEventFilter]
  );

  const getTextColor = (cell: CellData): string => {
    const r = cell.l * cell.s;
    return r >= 15 ? "#fff" : "#333";
  };

  if (zones.length === 0) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100%", color: "#8c8c8c" }}>
        暂无风险数据
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", overflow: "auto", padding: 8 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8, flexShrink: 0 }}>
        <span style={{ fontSize: 13, fontWeight: 600, color: "#333" }}>LS 风险矩阵</span>
        <span style={{ fontSize: 11, color: "#999" }}>（点击单元格筛选）</span>
      </div>
      <div style={{ overflowX: "auto", flex: 1 }}>
        <div
          style={{
            display: "inline-grid",
            gridTemplateColumns: "40px repeat(5, 1fr)",
            gridTemplateRows: "32px repeat(5, 1fr)",
            gap: 2,
            background: "#f0f0f0",
            border: "1px solid #e8e8e8",
            borderRadius: 6,
            overflow: "hidden",
            minWidth: 300,
            minHeight: 240,
          }}
        >
          <div
            style={{
              background: "#fafafa",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 11,
              color: "#999",
              fontWeight: 600,
            }}
          >
            L\S
          </div>
          {[1, 2, 3, 4, 5].map((s) => (
            <div
              key={`s-${s}`}
              style={{
                background: "#fafafa",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: 11,
                color: "#666",
                fontWeight: 600,
              }}
            >
              S={s}
            </div>
          ))}
          {grid.map((row, li) => (
            <React.Fragment key={`row-${li}`}>
              <div
                style={{
                  background: "#fafafa",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: 11,
                  color: "#666",
                  fontWeight: 600,
                }}
              >
                L={li + 1}
              </div>
              {row.map((cell) => {
                const r = cell.l * cell.s;
                const count = cell.events.length;
                const active = isCellActive(activeCell, cell);
                const hasEvents = count > 0;
                return (
                  <Tooltip
                    key={`${cell.l}-${cell.s}`}
                    title={
                      hasEvents ? (
                        <div style={{ maxHeight: 200, overflowY: "auto" }}>
                          <div style={{ fontWeight: 600, marginBottom: 4 }}>
                            L={cell.l}, S={cell.s}, R={r} ({resolveRiskLevel(r)})
                          </div>
                          {cell.events.map((ev) => (
                            <div key={ev.id} style={{ fontSize: 12, padding: "1px 0" }}>
                              {ev.name} <span style={{ color: "#aaa" }}>{ev.riskLevel}</span>
                            </div>
                          ))}
                        </div>
                      ) : undefined
                    }
                  >
                    <div
                      onClick={() => handleCellClick(cell)}
                      style={{
                        background: cell.color,
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        fontSize: 18,
                        fontWeight: 700,
                        color: hasEvents ? getTextColor(cell) : "rgba(0,0,0,0.15)",
                        cursor: hasEvents ? "pointer" : "default",
                        opacity: hasEvents ? (active ? 1 : 0.85) : 0.25,
                        border: active ? "3px solid #1677ff" : "2px solid transparent",
                        borderRadius: active ? 3 : 0,
                        transition: "opacity 0.15s, border 0.15s",
                      }}
                      onMouseEnter={(e) => {
                        if (hasEvents) (e.currentTarget as HTMLDivElement).style.opacity = "1";
                      }}
                      onMouseLeave={(e) => {
                        if (hasEvents) (e.currentTarget as HTMLDivElement).style.opacity = active ? "1" : "0.85";
                      }}
                    >
                      {hasEvents ? count : "-"}
                    </div>
                  </Tooltip>
                );
              })}
            </React.Fragment>
          ))}
        </div>
      </div>
      <div style={{ display: "flex", gap: 12, marginTop: 8, flexWrap: "wrap", flexShrink: 0 }}>
        {Object.entries(RISK_LEVEL_COLORS).map(([level, color]) => (
          <div key={level} style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 11, color: "#666" }}>
            <div style={{ width: 10, height: 10, background: color, borderRadius: 2 }} />
            {level}
          </div>
        ))}
      </div>
    </div>
  );
}
