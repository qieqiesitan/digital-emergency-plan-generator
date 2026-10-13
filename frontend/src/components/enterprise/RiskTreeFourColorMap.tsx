import { Button, Empty, Select } from "antd";
import RiskDistributionStage from "@/components/enterprise/riskMapping/RiskDistributionStage";
import type { EnterpriseFloor } from "@/types/riskMappingWorkbench";

interface Props {
  /** 企业楼层列表（含默认楼层与底图信息） */
  floors: EnterpriseFloor[];
  /** 当前展示楼层；null = 用默认楼层兜底 */
  floorId: string | null;
  /** 需要高亮的分区 id（与左侧风险树选中节点联动） */
  highlightZoneId: string | null;
  onFloorChange: (floorId: string) => void;
  onZoneClick: (zoneId: string) => void;
  onManageFloors: () => void;
}

/**
 * 风险树右侧的四色图卡片：只读展示底图 + 分区色块 + 风险点，
 * 与左侧树双向联动（选中节点高亮分区 / 点击分区反选树）。
 * data-floor-id / data-highlight-zone 供 e2e 断言联动状态。
 */
export default function RiskTreeFourColorMap({
  floors,
  floorId,
  highlightZoneId,
  onFloorChange,
  onZoneClick,
  onManageFloors,
}: Props) {
  const effectiveFloorId = floorId ?? floors.find((f) => f.is_default)?.id ?? floors[0]?.id ?? null;
  const floor = floors.find((f) => f.id === effectiveFloorId) ?? null;
  const floorIsEmpty = !!floor && !floor.floor_plan_url && (floor.zone_count ?? 0) === 0;

  return (
    <div
      data-testid="risk-tree-map-panel"
      data-floor-id={effectiveFloorId ?? ""}
      data-highlight-zone={highlightZoneId ?? ""}
      style={{
        flex: 1,
        minHeight: 0,
        display: "flex",
        flexDirection: "column",
        background: "#fff",
        borderRadius: 8,
        boxShadow: "0 2px 8px rgba(0,0,0,.08)",
        overflow: "hidden",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          padding: "8px 12px",
          borderBottom: "1px solid #f0f0f0",
          flexShrink: 0,
        }}
      >
        <span style={{ fontSize: 13, fontWeight: 600 }}>{"🗺"} 四色图</span>
        {floors.length > 1 && (
          <Select
            size="small"
            value={effectiveFloorId ?? undefined}
            style={{ minWidth: 110 }}
            aria-label="四色图楼层"
            options={floors.map((f) => ({ value: f.id, label: f.is_default ? `${f.name}（默认）` : f.name }))}
            onChange={onFloorChange}
          />
        )}
        <span style={{ marginLeft: "auto", fontSize: 12, color: "#8c8c8c", whiteSpace: "nowrap" }}>
          {highlightZoneId ? "已高亮选中分区" : "选中左侧节点联动"}
        </span>
      </div>
      <div style={{ flex: 1, minHeight: 0, position: "relative" }}>
        {floors.length === 0 ? (
          <div style={{ paddingTop: 48, textAlign: "center" }}>
            <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无楼层，先上传四色图/底图" />
            <Button size="small" onClick={onManageFloors}>去楼层管理</Button>
          </div>
        ) : floorIsEmpty ? (
          <div style={{ paddingTop: 48, textAlign: "center" }}>
            <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={`「${floor?.name ?? ""}」还没有底图与分区`} />
            <Button size="small" onClick={onManageFloors}>去楼层管理</Button>
          </div>
        ) : (
          <RiskDistributionStage
            floorId={effectiveFloorId ?? undefined}
            highlightZone={highlightZoneId}
            onZoneClick={onZoneClick}
          />
        )}
      </div>
    </div>
  );
}
