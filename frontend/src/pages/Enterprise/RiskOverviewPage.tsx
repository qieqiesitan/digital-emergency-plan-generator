 import { useState, useMemo } from "react";
 import { Card, Segmented, Button, Tree, Tag, Tooltip, Spin, Space } from "antd";
 import { ArrowLeftOutlined } from '@ant-design/icons';
 import { useQuery } from '@tanstack/react-query';
 import { useNavigate } from 'react-router-dom';
 import { getFullHierarchy } from '@/services/riskManagementService';
 import RiskOverviewMatrix from '@/components/enterprise/RiskOverviewMatrix';
 import RiskOverviewStats from '@/components/enterprise/RiskOverviewStats';
 import { RISK_LEVEL_COLORS } from '@/utils/riskMethodEngine';
 import type { HierarchyZone } from '@/types/riskManagement';
 
 interface Props { enterpriseId: string; }
 
 type ViewMode = 'quad' | 'floorplan-first' | 'data-first';
 type RightPanelView = 'tree' | 'topology';
 
 export default function RiskOverviewPage({ enterpriseId }: Props) {
   const navigate = useNavigate();
   const [viewMode, setViewMode] = useState<ViewMode>('quad');
   const [rightView, setRightView] = useState<RightPanelView>(() => (localStorage.getItem('risk-overview-right') as RightPanelView) || 'tree');
   const [filterIds, setFilterIds] = useState<string[]>([]);
 
   const { data: zones = [], isLoading } = useQuery({ queryKey: ['risk-hierarchy', enterpriseId], queryFn: () => getFullHierarchy(enterpriseId) });
 
   const treeData = useMemo(() => buildCompactTree(zones), [zones]);
 
   if (isLoading) return <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />;
 
   const isQuad = viewMode === 'quad';
   const isFloorFirst = viewMode === 'floorplan-first';
   const gridStyle: React.CSSProperties = isQuad ? { display:'grid', gridTemplateColumns:'1fr 1fr', gridTemplateRows:'1fr 1fr', gap:16, height:'calc(100vh - 140px)' }
     : isFloorFirst ? { display:'grid', gridTemplateColumns:'1fr', gridTemplateRows:'60% 40%', gap:16, height:'calc(100vh - 140px)' }
     : { display:'grid', gridTemplateColumns:'40% 1fr', gridTemplateRows:'1fr', gap:16, height:'calc(100vh - 140px)' };
 
   return (
     <div style={{ padding: '0 0 16px 0' }}>
       <Space style={{ marginBottom: 16 }}>
         <Button icon={<ArrowLeftOutlined />} onClick={() => navigate(-1)}>返回</Button>
         <Segmented options={[{ label:'四象限', value:'quad' }, { label:'平面图优先', value:'floorplan-first' }, { label:'数据优先', value:'data-first' }]} value={viewMode} onChange={v => setViewMode(v as ViewMode)} />
         <span style={{ marginLeft:'auto', fontSize:13, color:'#8c8c8c' }}>XX有限公司 — 风险管控总览</span>
       </Space>
       <div style={gridStyle}>
         <Card size="small" title="① 厂区平面图热区" style={{ overflow:'hidden' }}>
           <div style={{ height:'100%', minHeight:150, background:'#f9f9f9', borderRadius:6, display:'flex', alignItems:'center', justifyContent:'center', border:'1px dashed #d9d9d9' }}>
             <svg viewBox="0 0 400 280" style={{ width:'100%', maxHeight:280 }}>
               <rect x="20" y="20" width="360" height="240" fill="#fafafa" stroke="#d9d9d9" strokeWidth="1"/>
               {zones.map((z, i) => {
                 const maxLevel = getMaxLevel(z);
                 const color = RISK_LEVEL_COLORS[maxLevel] || '#d9d9d9';
                 const pts = z.floor_plan_polygon as any;
                 if (!pts?.points) return <rect key={i} x={50+i*100} y={40} width={80} height={60} fill={color} opacity={0.25} stroke={color} strokeWidth={2} rx={2} />;
                 return <polygon key={i} points={pts.points.map((p:any) => `${p.x/100*360+20},${p.y/100*240+20}`).join(' ')} fill={color} opacity={0.25} stroke={color} strokeWidth={2} />;
               })}
               {zones.flatMap(z => z.objects.filter(o => o.is_risk_point)).map((o, i) => <circle key={i} cx={50+o.name.length*8} cy={80+i*30} r={4} fill="#ff4d4f" />)}
             </svg>
           </div>
         </Card>
         <Card size="small" title="② 风险矩阵热力图"><RiskOverviewMatrix zones={zones} onEventFilter={setFilterIds} /></Card>
         {isQuad && <Card size="small" title="③ 风险统计"><RiskOverviewStats zones={zones} /></Card>}
         <Card size="small" title={
           <Space><span>④</span><Segmented size="small" options={[{label:'层级树',value:'tree'},{label:'管控拓扑图',value:'topology'}]} value={rightView} onChange={v => { setRightView(v as RightPanelView); localStorage.setItem('risk-overview-right', v as string); }} /></Space>
         }>
           {rightView === 'tree' ? <Tree treeData={treeData} defaultExpandAll blockNode style={{ maxHeight:'calc(100% - 10px)', overflow:'auto' }} /> : <TopologyView zones={zones} />}
         </Card>
         {!isQuad && <Card size="small" title="③ 风险统计"><RiskOverviewStats zones={zones} /></Card>}
       </div>
     </div>
   );
 }
 
 function getMaxLevel(zone: HierarchyZone): string {
   const levels: Record<string, number> = { '重大':4, '较大':3, '一般':2, '低':1 };
   let max = '低';
   const check = (l?: string|null) => { if (l && (levels[l]||0) > (levels[max]||0)) max = l; };
   for (const o of zone.objects) { for (const e of o.events) check(e.risk_level); for (const u of o.units) for (const e of u.events) check(e.risk_level); }
   return max;
 }
 
 function buildCompactTree(zones: HierarchyZone[]): any[] {
   return zones.map(z => ({
     title: <span>🏭 {z.name} {getMaxLevel(z) !== '低' && <Tag color={RISK_LEVEL_COLORS[getMaxLevel(z)]}>{getMaxLevel(z)}</Tag>}</span>,
     key: z.id,
     children: z.objects.map(o => ({
       title: <span>📦 {o.name}{o.is_risk_point?' ◆':''}</span>, key: o.id,
       children: [...o.events.map(e => ({ title: <span>⚠ {e.accident_type} <Tag color={RISK_LEVEL_COLORS[e.risk_level||'低']}>{e.risk_level||'?'} {e.risk_score}</Tag></span>, key: e.id, isLeaf: true })),
         ...o.units.map(u => ({ title: <span>⚙ {u.name}</span>, key: u.id, children: u.events.map(e => ({ title: <span>⚠ {e.accident_type} <Tag color={RISK_LEVEL_COLORS[e.risk_level||'低']}>{e.risk_level||'?'}</Tag></span>, key: e.id, isLeaf: true })) }))
       ],
     })),
   }));
 }
 
 function TopologyView({ zones }: { zones: HierarchyZone[] }) {
   const w = 600, h = 260, cx = w/2;
   return (
     <div style={{ overflow:'auto', minHeight:200 }}>
       <svg viewBox={`0 0 ${w} ${h}`} style={{ minWidth:w, width:'100%' }}>
         <rect x={cx-60} y={2} width={120} height={22} rx={4} fill="#fff" stroke="#d9d9d9"/><text x={cx} y={16} textAnchor="middle" fontSize={10} fontWeight={600}>XX有限公司</text>
         {zones.slice(0,3).map((z, i) => {
           const lvl = getMaxLevel(z); const clr = RISK_LEVEL_COLORS[lvl]||'#d9d9d9';
           const x = 40 + i*200; const y = 60;
           return <g key={z.id}>
             <line x1={cx} y1={24} x2={x+50} y2={y} stroke="#d9d9d9" strokeWidth={1}/>
             <rect x={x} y={y} width={100} height={20} rx={4} fill="#fff" stroke={clr} strokeWidth={1.5}/><rect x={x} y={y} width={3} height={20} rx={2} fill={clr}/>
             <text x={x+52} y={y+14} textAnchor="middle" fontSize={9} fontWeight={600}>{z.name}</text>
           </g>;
         })}
         <rect x={10} y={h-14} width={10} height={10} rx={3} fill="#fff1f0" stroke="#ffa39e"/><text x={23} y={h-4} fontSize={8} fill="#8c8c8c">重大</text>
         <rect x={60} y={h-14} width={10} height={10} rx={3} fill="#fff7e6" stroke="#ffd591"/><text x={73} y={h-4} fontSize={8} fill="#8c8c8c">较大</text>
         <rect x={110} y={h-14} width={10} height={10} rx={3} fill="#fffbe6" stroke="#ffe58f"/><text x={123} y={h-4} fontSize={8} fill="#8c8c8c">一般</text>
         <rect x={160} y={h-14} width={10} height={10} rx={3} fill="#f6ffed" stroke="#b7eb8f"/><text x={173} y={h-4} fontSize={8} fill="#8c8c8c">低</text>
       </svg>
     </div>
   );
 }
