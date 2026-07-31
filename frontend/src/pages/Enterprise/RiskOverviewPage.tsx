 import { useState, useMemo, useRef, useEffect } from "react";
 import { useNavigate, useParams } from "react-router-dom";
 import { Card, Segmented, Button, Tree, Tag, Tooltip, Spin, Space, Empty } from "antd";
 import { ArrowLeftOutlined } from "@ant-design/icons";
 import { useQuery } from "@tanstack/react-query";
 import { getFullHierarchy } from "@/services/riskManagementService";
 import RiskOverviewMatrix from "@/components/enterprise/RiskOverviewMatrix";
 import RiskOverviewStats from "@/components/enterprise/RiskOverviewStats";
 import { RISK_LEVEL_COLORS } from "@/utils/riskMethodEngine";
 import type { HierarchyZone, HierarchyObject, HierarchyUnit, HierarchyEvent } from "@/types/riskManagement";
 
 type ViewMode = "quad" | "floorplan" | "data";
 
 export default function RiskOverviewPage() {
   const { id: enterpriseId } = useParams<{ id: string }>();
   const navigate = useNavigate();
   const [viewMode, setViewMode] = useState<ViewMode>("quad");
   const [rightView, setRightView] = useState<"tree" | "topology">(() => (localStorage.getItem("risk-overview-right") as "tree" | "topology") || "tree");
   const [filterIds, setFilterIds] = useState<string[]>([]);
   const [highlightZone, setHighlightZone] = useState<string | null>(null);
 
   const { data: zones = [], isLoading } = useQuery({ queryKey: ["risk-hierarchy", enterpriseId], queryFn: () => getFullHierarchy(enterpriseId!), enabled: !!enterpriseId });
 
   // Build compact tree
   const treeData = useMemo(() => zones.map(z => ({ title: <span>🏭 {z.name} {getMaxLevel(z) !== "低" && <Tag color={RISK_LEVEL_COLORS[getMaxLevel(z)]}>{getMaxLevel(z)}</Tag>}</span>, key: z.id, children: z.objects?.map(o => ({ title: <span>📦 {o.name}{o.is_risk_point ? " ◆" : ""}</span>, key: o.id, children: [...(o.events||[]).map(e => ({ title: <span>⚠ {e.accident_type} <Tag color={RISK_LEVEL_COLORS[e.risk_level||"低"]}>{e.risk_level||"?"}</Tag></span>, key: e.id, isLeaf: true })), ...(o.units||[]).map(u => ({ title: <span>⚙ {u.name}</span>, key: u.id, children: (u.events||[]).map(e => ({ title: <span>⚠ {e.accident_type} <Tag color={RISK_LEVEL_COLORS[e.risk_level||"低"]}>{e.risk_level||"?"}</Tag></span>, key: e.id, isLeaf: true })) }))] })) || [] })), [zones]);
 
   if (isLoading) return <Spin size="large" style={{ display: "block", margin: "100px auto" }} />;
   if (!zones.length) return <Empty description="暂无风险管控数据" />;
 
   const gridStyle: React.CSSProperties = viewMode === "quad" ? { display: "grid", gridTemplateColumns: "1fr 1fr", gridTemplateRows: "1fr 1fr", gap: 16, height: "calc(100vh - 140px)" } : viewMode === "floorplan" ? { display: "grid", gridTemplateColumns: "1fr", gridTemplateRows: "60% 40%", gap: 16, height: "calc(100vh - 140px)" } : { display: "grid", gridTemplateColumns: "40% 1fr", gridTemplateRows: "1fr", gap: 16, height: "calc(100vh - 140px)" };
 
   return (
     <div style={{ padding: "0 0 16px 0" }}>
       <Space style={{ marginBottom: 16 }}>
         <Button icon={<ArrowLeftOutlined />} onClick={() => navigate(`/enterprises/${enterpriseId}`)}>返回</Button>
         <Segmented options={[{ label: "四象限", value: "quad" }, { label: "平面图优先", value: "floorplan" }, { label: "数据优先", value: "data" }]} value={viewMode} onChange={v => setViewMode(v as ViewMode)} />
       </Space>
       <div style={gridStyle}>
         {/* Q1: Floor Plan Heatmap */}
         <Card size="small" title="① 厂区平面图热区" style={{ overflow: "hidden" }}>
           <FloorPlanHeatmap zones={zones} highlightZone={highlightZone} onZoneClick={setHighlightZone} />
         </Card>
         {/* Q2: Risk Matrix */}
         <Card size="small" title="② 风险矩阵热力图"><RiskOverviewMatrix zones={zones} onEventFilter={setFilterIds} /></Card>
         {/* Q3: Stats */}
         {(viewMode === "quad" || viewMode === "data") && <Card size="small" title="③ 风险统计"><RiskOverviewStats zones={zones} /></Card>}
         {/* Q4: Tree/Topology */}
         <Card size="small" title={<Space><span>④</span><Segmented size="small" options={[{ label: "层级树", value: "tree" }, { label: "管控拓扑图", value: "topology" }]} value={rightView} onChange={v => { setRightView(v as "tree" | "topology"); localStorage.setItem("risk-overview-right", v as string); }} /></Space>}>
           {rightView === "tree" ? <Tree treeData={treeData} defaultExpandAll blockNode style={{ maxHeight: "calc(100% - 30px)", overflow: "auto" }} onSelect={(keys) => { if (keys[0]) { const zone = zones.find(z => z.id === keys[0] || z.objects?.some(o => o.id === keys[0])); if (zone) setHighlightZone(zone.id); } }} /> : <TopologySVG zones={zones} highlightZone={highlightZone} />}
         </Card>
       </div>
     </div>
   );
 }
 
 // Helper: get max risk level in a zone
 function getMaxLevel(zone: HierarchyZone): string {
   const levels: Record<string, number> = { "重大": 4, "较大": 3, "一般": 2, "低": 1 };
   let max = "低";
   const check = (l?: string | null) => { if (l && (levels[l] || 0) > (levels[max] || 0)) max = l; };
   for (const o of zone.objects || []) { for (const e of o.events || []) check(e.risk_level); for (const u of o.units || []) for (const e of u.events || []) check(e.risk_level); }
   return max;
 }
 
 // Q1: Floor Plan Heatmap
 function FloorPlanHeatmap({ zones, highlightZone, onZoneClick }: { zones: HierarchyZone[]; highlightZone: string | null; onZoneClick: (id: string | null) => void }) {
   const cols = Math.min(zones.length, 3);
   return (
     <div style={{ display: "grid", gridTemplateColumns: `repeat(${cols}, 1fr)`, gap: 8, height: "100%", overflow: "auto" }}>
       {zones.map(z => {
         const lvl = getMaxLevel(z);
         const color = RISK_LEVEL_COLORS[lvl] || "#d9d9d9";
         const isHighlighted = highlightZone === z.id;
         return (
           <div key={z.id} onClick={() => onZoneClick(isHighlighted ? null : z.id)} style={{ background: color + "20", border: `2px solid ${isHighlighted ? color : color + "60"}`, borderRadius: 8, padding: 12, cursor: "pointer", transition: "all .2s", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", minHeight: 100 }}>
             <div style={{ fontSize: 20 }}>🏭</div>
             <div style={{ fontSize: 13, fontWeight: 600, marginTop: 4 }}>{z.name}</div>
             <Tag color={color} style={{ marginTop: 4 }}>{lvl}风险</Tag>
             <div style={{ fontSize: 11, color: "#8c8c8c", marginTop: 2 }}>{z.objects?.length || 0} 对象</div>
           </div>
         );
       })}
     </div>
   );
 }
 
 // Q4: Topology SVG
 function TopologySVG({ zones, highlightZone }: { zones: HierarchyZone[]; highlightZone: string | null }) {
   const W = 600, H = 300;
   return (
     <div style={{ overflow: "auto", maxHeight: "calc(100% - 30px)" }}>
       <svg viewBox={`0 0 ${W} ${H}`} style={{ minWidth: W, width: "100%" }}>
         <rect x={W/2-50} y={5} width={100} height={20} rx={4} fill="#f0f0f0" stroke="#d9d9d9" />;
         <text x={W/2} y={19} textAnchor="middle" fontSize={10} fontWeight={600}>企业风险总览</text>
         {zones.slice(0, 4).map((z, i) => {
           const lvl = getMaxLevel(z); const clr = RISK_LEVEL_COLORS[lvl] || "#d9d9d9";
           const x = 30 + (i % 2) * 280; const y = 50 + Math.floor(i/2) * 100;
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
