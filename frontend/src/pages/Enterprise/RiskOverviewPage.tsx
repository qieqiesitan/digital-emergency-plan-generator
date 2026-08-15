import { useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Badge, Card, Segmented, Button, Tree, Tag, Spin, Space, Empty, Select } from "antd";
import { ArrowLeftOutlined } from "@ant-design/icons";
import { useQuery } from "@tanstack/react-query";
import { getFullHierarchy } from "@/services/riskManagementService";
import { listEnterpriseFloors } from "@/services/riskMappingWorkbenchService";
import RiskDistributionStage from "@/components/enterprise/riskMapping/RiskDistributionStage";
import RiskOverviewMatrix from "@/components/enterprise/RiskOverviewMatrix";
import RiskOverviewStats from "@/components/enterprise/RiskOverviewStats";
import { RISK_LEVEL_COLORS } from "@/utils/riskMethodEngine";
import type { HierarchyEvent, HierarchyZone } from "@/types/riskManagement";

type ViewMode = "quad" | "floorplan" | "data";
type ColorMode = "current" | "inherent";

export default function RiskOverviewPage() {
  const { id: enterpriseId } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [viewMode, setViewMode] = useState<ViewMode>("quad");
  const [colorMode, setColorMode] = useState<ColorMode>(() => {
    const saved = localStorage.getItem("risk-overview-color-mode");
    return saved === "inherent" ? "inherent" : "current";
  });
  const [rightView, setRightView] = useState<"tree" | "topology">(() => (localStorage.getItem("risk-overview-right") as "tree" | "topology") || "tree");
  const [highlightZone, setHighlightZone] = useState<string | null>(null);
  const [treeSelectedKeys, setTreeSelectedKeys] = useState<React.Key[]>([]);
  const [floorId, setFloorId] = useState<string | undefined>(undefined);

  const { data: floors = [] } = useQuery({
    queryKey: ["risk-floors", enterpriseId],
    queryFn: () => listEnterpriseFloors(enterpriseId!),
    enabled: !!enterpriseId,
  });

  // 当前生效楼层：用户显式选择优先，否则回退默认楼层（派生值，避免 effect 内 setState）
  const effectiveFloorId = useMemo(() => {
    if (floorId) return floorId;
    const def = floors.find(f => f.is_default) ?? floors[0];
    return def?.id;
  }, [floorId, floors]);

  const { data: zones = [], isLoading } = useQuery({
    queryKey: ["risk-hierarchy", enterpriseId, effectiveFloorId],
    queryFn: () => getFullHierarchy(enterpriseId!, effectiveFloorId),
    enabled: !!enterpriseId,
  });

  // 点击分布图分区 → 联动层级树与拓扑高亮
  const handleZoneClick = (zoneId: string) => {
    setHighlightZone(prev => (prev === zoneId ? null : zoneId));
    setTreeSelectedKeys(prev => (prev.includes(zoneId) ? [] : [zoneId]));
  };

  // 切换楼层 → 树与分布图数据按新楼层刷新，并清理旧楼层的选中/高亮残留
  const handleFloorChange = (value: string) => {
    setFloorId(value);
    setHighlightZone(null);
    setTreeSelectedKeys([]);
  };

  // 切换现有/固有模式 → 清理旧模式的选中/高亮残留
  const handleColorModeChange = (mode: ColorMode) => {
    setColorMode(mode);
    setHighlightZone(null);
    setTreeSelectedKeys([]);
    localStorage.setItem("risk-overview-color-mode", mode);
  };

  // Build compact tree
  const treeData = useMemo(() => {
    const eventLevel = (e: HierarchyEvent) => (colorMode === "inherent" ? (e.inherent_risk_level ?? e.risk_level) : e.risk_level) || "低";
    return zones.map(z => ({ title: <span>🏭 {z.name} {getMaxLevel(z, colorMode) !== "低" && <Tag color={RISK_LEVEL_COLORS[getMaxLevel(z, colorMode)]}>{getMaxLevel(z, colorMode)}</Tag>}<OpenHazardBadge count={z.open_hazard_count} /></span>, key: z.id, children: z.objects?.map(o => ({ title: <span>📦 {o.name}{o.is_risk_point ? " ◆" : ""}<OpenHazardBadge count={o.open_hazard_count} /></span>, key: o.id, children: [...(o.events||[]).map(e => ({ title: <span>⚠ {e.accident_type} <Tag color={RISK_LEVEL_COLORS[eventLevel(e)]}>{eventLevel(e)}</Tag></span>, key: e.id, isLeaf: true })), ...(o.units||[]).map(u => ({ title: <span>⚙ {u.name}</span>, key: u.id, children: (u.events||[]).map(e => ({ title: <span>⚠ {e.accident_type} <Tag color={RISK_LEVEL_COLORS[eventLevel(e)]}>{eventLevel(e)}</Tag></span>, key: e.id, isLeaf: true })) }))] })) || [] }));
  }, [zones, colorMode]);

  if (isLoading) return <Spin size="large" style={{ display: "block", margin: "100px auto" }} />;

  const gridStyle: React.CSSProperties =
    viewMode === "quad"
      ? { display: "grid", gridTemplateColumns: "1fr 1fr", gridTemplateRows: "1fr 1fr", gap: 16, height: "calc(100vh - 140px)", minHeight: 0 }
      : viewMode === "floorplan"
      ? { display: "grid", gridTemplateColumns: "65% 1fr", gridTemplateRows: "1fr 1fr", gap: 16, height: "calc(100vh - 140px)", minHeight: 0 }
      : { display: "grid", gridTemplateColumns: "1fr 1fr", gridTemplateRows: "55% 45%", gap: 16, height: "calc(100vh - 140px)", minHeight: 0 };

  return (
    <div style={{ padding: "0 0 16px 0" }}>
      <Space style={{ marginBottom: 16 }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate(-1)}>返回</Button>
        <Select
          value={effectiveFloorId}
          placeholder="选择楼层"
          style={{ width: 180 }}
          options={floors.map(f => ({ label: f.name, value: f.id }))}
          onChange={handleFloorChange}
        />
        <Segmented options={[{ label: "现有风险图", value: "current" }, { label: "固有风险图", value: "inherent" }]} value={colorMode} onChange={v => handleColorModeChange(v as ColorMode)} />
        <Segmented options={[{ label: "四象限", value: "quad" }, { label: "分布图优先", value: "floorplan" }, { label: "数据优先", value: "data" }]} value={viewMode} onChange={v => setViewMode(v as ViewMode)} />
      </Space>
      {zones.length === 0 ? (
        <Empty
          description={floors.length ? "当前楼层暂无风险管控数据，请切换楼层查看" : "暂无风险管控数据"}
          style={{ marginTop: 80 }}
        />
      ) : (
        <div style={gridStyle}>
          {/* Q1: Floor Plan Heatmap */}
          <Card
            size="small"
            title="① 四色分布热区"
            style={{ overflow: "hidden", height: "100%", minHeight: 0, display: "flex", flexDirection: "column", ...cardArea(viewMode, 1) }}
            styles={{ body: { flex: 1, minHeight: 0, padding: 12, position: "relative", overflow: "hidden" } }}
          >
            <RiskDistributionStage floorId={effectiveFloorId} highlightZone={highlightZone} onZoneClick={handleZoneClick} mode={colorMode} />
          </Card>
          {/* Q2: Risk Matrix */}
          <Card size="small" title="② 风险矩阵热力图" style={{ height: "100%", minHeight: 0, display: "flex", flexDirection: "column", ...cardArea(viewMode, 2) }} styles={{ body: { flex: 1, minHeight: 0, overflow: "auto" } }}><RiskOverviewMatrix zones={zones} onEventFilter={() => {}} mode={colorMode} /></Card>
          {/* Q3: Stats */}
          {(viewMode === "quad" || viewMode === "data") && <Card size="small" title="③ 风险统计" style={{ height: "100%", minHeight: 0, display: "flex", flexDirection: "column", ...cardArea(viewMode, 3) }} styles={{ body: { flex: 1, minHeight: 0, overflow: "auto" } }}><RiskOverviewStats zones={zones} mode={colorMode} /></Card>}
          {/* Q4: Tree/Topology */}
          <Card size="small" title={<Space><span>④</span><Segmented size="small" options={[{ label: "层级树", value: "tree" }, { label: "管控拓扑图", value: "topology" }]} value={rightView} onChange={v => { setRightView(v as "tree" | "topology"); localStorage.setItem("risk-overview-right", v as string); }} /></Space>} style={{ height: "100%", minHeight: 0, display: "flex", flexDirection: "column", ...cardArea(viewMode, 4) }} styles={{ body: { flex: 1, minHeight: 0, overflow: "auto" } }}>
            {rightView === "tree" ? (
              <Tree
                treeData={treeData}
                defaultExpandAll
                blockNode
                selectedKeys={treeSelectedKeys}
                style={{ maxHeight: "calc(100% - 30px)", overflow: "auto" }}
                onSelect={(keys) => {
                  setTreeSelectedKeys(keys);
                  if (keys[0]) {
                    const zone = zones.find(z => z.id === keys[0] || z.objects?.some(o => o.id === keys[0]));
                    if (zone) setHighlightZone(zone.id);
                  }
                }}
              />
            ) : (
              <TopologySVG zones={zones} highlightZone={highlightZone} mode={colorMode} />
            )}
          </Card>
        </div>
      )}
    </div>
  );
}

// 各视图下卡片在网格中的显式位置,避免依赖 DOM 顺序产生隐式行溢出
function cardArea(mode: ViewMode, n: 1 | 2 | 3 | 4): React.CSSProperties {
  switch (mode) {
    case "quad":
      // 2x2 均衡:①分布图 ②矩阵 / ③统计 ④树
      return n === 1 || n === 3
        ? { gridColumn: 1, gridRow: n === 1 ? 1 : 2 }
        : { gridColumn: 2, gridRow: n === 2 ? 1 : 2 };
    case "floorplan":
      // 分布图独占左列整高,右侧竖排 ②矩阵 + ④树;③统计在该视图不渲染
      if (n === 1) return { gridColumn: 1, gridRow: "1 / 3" };
      return { gridColumn: 2, gridRow: n === 2 ? 1 : 2 };
    case "data":
      // 上排数据为主(③统计 + ②矩阵),下排图形(①分布图 + ④树)
      if (n === 1) return { gridColumn: 1, gridRow: 2 };
      if (n === 2) return { gridColumn: 2, gridRow: 1 };
      if (n === 3) return { gridColumn: 1, gridRow: 1 };
      return { gridColumn: 2, gridRow: 2 };
  }
}

// Helper: get max risk level in a zone
function getMaxLevel(zone: HierarchyZone, mode: ColorMode = "current"): string {
  const levels: Record<string, number> = { "重大": 4, "较大": 3, "一般": 2, "低": 1 };
  let max = "低";
  const check = (l?: string | null) => { if (l && (levels[l] || 0) > (levels[max] || 0)) max = l; };
  for (const o of zone.objects || []) {
    for (const e of o.events || []) check(mode === "inherent" ? (e.inherent_risk_level ?? e.risk_level) : e.risk_level);
    for (const u of o.units || []) for (const e of u.events || []) check(mode === "inherent" ? (e.inherent_risk_level ?? e.risk_level) : e.risk_level);
  }
  return max;
}

// Helper: 未闭环隐患 badge（规格 §11.1 派生计数展示，仅 >0 渲染）
function OpenHazardBadge({ count }: { count?: number }) {
  if (!count || count <= 0) return null;
  return <Badge color="red" text={`未闭环 ${count}`} style={{ marginLeft: 6 }} />;
}

// Q4: Topology SVG
function TopologySVG({ zones, highlightZone, mode }: { zones: HierarchyZone[]; highlightZone: string | null; mode: ColorMode }) {
  const cols = Math.min(4, Math.max(1, zones.length));
  const rows = Math.max(1, Math.ceil(zones.length / 4));
  const W = Math.max(600, 60 + cols * 140);
  const H = Math.max(300, 90 + rows * 100);
  return (
    <div style={{ overflow: "auto", maxHeight: "calc(100% - 30px)" }}>
      <svg viewBox={`0 0 ${W} ${H}`} style={{ minWidth: W, width: "100%" }}>
        <rect x={W/2-50} y={5} width={100} height={20} rx={4} fill="#f0f0f0" stroke="#d9d9d9" />;
        <text x={W/2} y={19} textAnchor="middle" fontSize={10} fontWeight={600}>企业风险总览</text>
        {zones.map((z, i) => {
          const lvl = getMaxLevel(z, mode); const clr = RISK_LEVEL_COLORS[lvl] || "#d9d9d9";
          const x = 30 + (i % 4) * 140; const y = 50 + Math.floor(i / 4) * 100;
          return (
            <g key={z.id}>
              <line x1={W/2} y1={25} x2={x+50} y2={y} stroke="#d9d9d9" strokeWidth={1} />
              <rect x={x} y={y} width={100} height={22} rx={4} fill="#fff" stroke={highlightZone === z.id ? clr : "#d9d9d9"} strokeWidth={highlightZone === z.id ? 2 : 1} />
              <rect x={x} y={y} width={4} height={22} rx={2} fill={clr} />
              <text x={x+55} y={y+15} textAnchor="middle" fontSize={10} fontWeight={600}>{z.name}</text>
              {(z.objects || []).slice(0, 3).map((o, j) => (
                <text key={o.id} x={x+55} y={y+35+j*14} textAnchor="middle" fontSize={9} fill="#8c8c8c">
                  {"📦 " + o.name + (o.is_risk_point ? " ◆" : "")}
                </text>
              ))}
              {z.objects && z.objects.length > 3 && <text x={x+55} y={y+35+3*14} textAnchor="middle" fontSize={9} fill="#8c8c8c">+{z.objects.length - 3} 更多</text>}
            </g>
          );
        })}
        <rect x={10} y={H-16} width={10} height={10} rx={3} fill="#fff1f0" stroke="#ffa39e" /><text x={23} y={H-6} fontSize={8} fill="#8c8c8c">重大</text>
        <rect x={60} y={H-16} width={10} height={10} rx={3} fill="#fff7e6" stroke="#ffd591" /><text x={73} y={H-6} fontSize={8} fill="#8c8c8c">较大</text>
        <rect x={110} y={H-16} width={10} height={10} rx={3} fill="#fffbe6" stroke="#ffe58f" /><text x={123} y={H-6} fontSize={8} fill="#8c8c8c">一般</text>
        <rect x={160} y={H-16} width={10} height={10} rx={3} fill="#f6ffed" stroke="#b7eb8f" /><text x={173} y={H-6} fontSize={8} fill="#8c8c8c">低</text>
      </svg>
    </div>
  );
}
