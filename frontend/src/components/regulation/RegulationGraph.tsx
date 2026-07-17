import { useEffect, useRef, useState } from "react";
import { Spin, Card, Tag, Empty, Tooltip, Segmented, Space, Typography, Button } from "antd";
import {
  ZoomInOutlined, ZoomOutOutlined, ExpandOutlined,
} from "@ant-design/icons";
import { useQuery } from "@tanstack/react-query";
import { fetchRegulationGraph } from "@/services/regulationService";
import type { RegulationNode } from "@/types/regulation";

const { Text } = Typography;

const COLORS: Record<string, string> = {
  law: "#1677ff", standard: "#52c41a", policy: "#faad14", topic: "#eb2f96",
};
const TYPE_LABELS: Record<string, string> = {
  law: "法律", standard: "标准", policy: "政策", topic: "主题",
};
const EDGE_COLORS: Record<string, string> = {
  "替代": "#ff4d4f", "下位法": "#1677ff", "适用": "#52c41a",
};

interface SimNode {
  id: string; x: number; y: number; vx: number; vy: number;
  radius: number; data: RegulationNode;
}

function simulate(nodes: SimNode[], edges: { source: string; target: string }[], W: number, H: number) {
  // Init positions in rough type-based clusters
  const groups: Record<string, SimNode[]> = {};
  for (const n of nodes) {
    const t = n.data.node_type || "topic";
    (groups[t] = groups[t] || []).push(n);
  }
  const keys = Object.keys(groups);
  for (let i = 0; i < keys.length; i++) {
    const g = groups[keys[i]];
    const angle = (2 * Math.PI * i) / keys.length;
    const cx = W / 2 + Math.cos(angle) * 280;
    const cy = H / 2 + Math.sin(angle) * 200;
    for (let j = 0; j < g.length; j++) {
      const a = (2 * Math.PI * j) / g.length;
      const r = 60 + g.length * 8;
      g[j].x = cx + Math.cos(a) * r;
      g[j].y = cy + Math.sin(a) * r;
      g[j].vx = 0; g[j].vy = 0;
    }
  }
  // Force simulation
  for (let iter = 0; iter < 150; iter++) {
    const alpha = 1 - iter / 150;
    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        const dx = nodes[j].x - nodes[i].x;
        const dy = nodes[j].y - nodes[i].y;
        const dist = Math.sqrt(dx * dx + dy * dy) || 1;
        const force = alpha * 8 * (nodes[i].radius + nodes[j].radius + 80) / dist;
        nodes[i].vx -= (dx / dist) * force;
        nodes[i].vy -= (dy / dist) * force;
        nodes[j].vx += (dx / dist) * force;
        nodes[j].vy += (dy / dist) * force;
      }
    }
    for (const e of edges) {
      const s = nodes.find((n) => n.id === e.source);
      const t = nodes.find((n) => n.id === e.target);
      if (!s || !t) continue;
      const dx = t.x - s.x;
      const dy = t.y - s.y;
      const dist = Math.sqrt(dx * dx + dy * dy) || 1;
      const ideal = s.radius + t.radius + 160;
      const force = alpha * 0.25 * (dist - ideal) / dist;
      s.vx += dx * force;
      s.vy += dy * force;
      t.vx -= dx * force;
      t.vy -= dy * force;
    }
    for (const n of nodes) {
      n.vx += (W / 2 - n.x) * 0.0005 * alpha;
      n.vy += (H / 2 - n.y) * 0.0005 * alpha;
      n.vx *= 0.88;
      n.vy *= 0.88;
      n.x += n.vx;
      n.y += n.vy;
      n.x = Math.max(n.radius, Math.min(W - n.radius, n.x));
      n.y = Math.max(n.radius, Math.min(H - n.radius, n.y));
    }
  }
}

export function RegulationGraph() {
  const svgRef = useRef<SVGSVGElement>(null);
  const [sel, setSel] = useState<RegulationNode | null>(null);
  const [hover, setHover] = useState<string | null>(null);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [zoom, setZoom] = useState(1);
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [ready, setReady] = useState(false);
  const dragRef = useRef<{ sx: number; sy: number; px: number; py: number } | null>(null);
  const simNodes = useRef<SimNode[]>([]);
  const simEdges = useRef<{ source: string; target: string; relation: string }[]>([]);

  // Store pan/zoom in refs for the native wheel listener to avoid stale closures
  const panRef = useRef(pan);
  panRef.current = pan;
  const zoomRef = useRef(zoom);
  zoomRef.current = zoom;

  useEffect(() => {
    const svg = svgRef.current;
    if (!svg) return;
    const handleWheel = (e: WheelEvent) => {
      e.preventDefault();
      const rect = svg.getBoundingClientRect();
      const mx = e.clientX - rect.left;
      const my = e.clientY - rect.top;
      const z = zoomRef.current;
      const newZoom = Math.max(0.2, Math.min(4, z * (e.deltaY > 0 ? 0.92 : 1.08)));
      const scale = newZoom / z;
      setPan((prevPan) => ({ x: mx - scale * (mx - prevPan.x), y: my - scale * (my - prevPan.y) }));
      setZoom(newZoom);
    };
    svg.addEventListener("wheel", handleWheel, { passive: false });
    return () => svg.removeEventListener("wheel", handleWheel);
  }, []);
  const { data, isLoading } = useQuery({
    queryKey: ["regulationGraph"],
    queryFn: fetchRegulationGraph,
  });

  useEffect(() => {
    if (!data) return;
    const W = 1000, H = 650;
    let filtered = data.nodes.filter(
      (n) => n.status !== "abolished" || n.node_type === "topic"
    );
    if (statusFilter !== "all") {
      filtered = filtered.filter((n) => n.node_type === statusFilter);
    }
    const nodeMap = new Map(filtered.map((n) => [n.id, n]));
    const nodes: SimNode[] = filtered.map((n) => ({
      id: n.id, x: 0, y: 0, vx: 0, vy: 0,
      radius: n.node_type === "law" ? 26 : n.node_type === "topic" ? 16 : 22,
      data: n,
    }));
    const edges = data.edges
      .filter((e) => nodeMap.has(e.source) && nodeMap.has(e.target))
      .map((e) => ({ source: e.source, target: e.target, relation: e.relation }));
    simulate(nodes, edges, W, H);
    simNodes.current = nodes;
    simEdges.current = edges;
    setReady(true);
    setSel(null);
  }, [data, statusFilter]);

  if (isLoading) return <Spin style={{ display: "block", textAlign: "center", padding: 80 }} />;

  const nodes = simNodes.current;
  const edges = simEdges.current;

  if (!ready || !nodes.length) {
    return (
      <Card style={{ borderRadius: 12 }}>
        <Empty description="暂无图谱数据" image={Empty.PRESENTED_IMAGE_SIMPLE}>
          <Text type="secondary">请先在法规列表中入库法规，系统将自动构建关系图谱</Text>
        </Empty>
      </Card>
    );
  }

  const selEdges = sel ? edges.filter((e) => e.source === sel.id || e.target === sel.id) : [];
  const selNeighbors = sel ? new Set(selEdges.flatMap((e) => [e.source, e.target])) : new Set<string>();
  const hoverNeighbors = hover
    ? new Set(edges.filter((e) => e.source === hover || e.target === hover).flatMap((e) => [e.source, e.target]))
    : new Set<string>();

  const nodeTypes = [...new Set(nodes.map((n) => n.data.node_type))];


  const onMouseDown = (e: React.MouseEvent) => {
    if ((e.target as Element).closest("circle") || (e.target as Element).closest("text")) return;
    dragRef.current = { sx: e.clientX, sy: e.clientY, px: pan.x, py: pan.y };
  };

  const onMouseMove = (e: React.MouseEvent) => {
    if (!dragRef.current) return;
    setPan({
      x: dragRef.current.px + (e.clientX - dragRef.current.sx),
      y: dragRef.current.py + (e.clientY - dragRef.current.sy),
    });
  };

  const onMouseUp = () => { dragRef.current = null; };

  const resetView = () => { setPan({ x: 0, y: 0 }); setZoom(1); };

  return (
    <div style={{ display: "flex", gap: 16, alignItems: "flex-start" }}>
      <div style={{ flex: 1 }}>
        <Card
          title={
            <Space>
              <span>法规知识图谱</span>
              <Tag color="blue">{nodes.length} 节点</Tag>
              <Tag color="green">{edges.length} 关系</Tag>
            </Space>
          }
          size="small"
          style={{ borderRadius: 12 }}
          extra={
            <Space>
              <Segmented
                size="small"
                value={statusFilter}
                options={[
                  { label: "全部", value: "all" },
                  ...nodeTypes.map((t) => ({ label: TYPE_LABELS[t] || t, value: t })),
                ]}
                onChange={(v) => setStatusFilter(v as string)}
              />
              <Tooltip title="放大"><Button size="small" icon={<ZoomInOutlined />} onClick={() => setZoom((z) => Math.min(4, z * 1.2))} /></Tooltip>
              <Tooltip title="缩小"><Button size="small" icon={<ZoomOutOutlined />} onClick={() => setZoom((z) => Math.max(0.2, z * 0.8))} /></Tooltip>
              <Tooltip title="重置"><Button size="small" icon={<ExpandOutlined />} onClick={resetView} /></Tooltip>
            </Space>
          }
        >
          <div style={{
            background: "linear-gradient(135deg, #f5f7fa 0%, #e8ecf1 100%)",
            borderRadius: 10, overflow: "hidden", position: "relative",
          }}>
            <svg
              ref={svgRef}
              viewBox="0 0 1000 650"
              style={{
                width: "100%", height: 520, display: "block",
                cursor: dragRef.current ? "grabbing" : "grab",
              }}
              onMouseDown={onMouseDown}
              onMouseMove={onMouseMove}
              onMouseUp={onMouseUp}
              onMouseLeave={onMouseUp}
            >
              <defs>
                {Object.entries(COLORS).map(([k, c]) => (
                  <filter key={k} id={`g-${k}`} x="-50%" y="-50%" width="200%" height="200%">
                    <feGaussianBlur stdDeviation="2" result="b" />
                    <feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge>
                  </filter>
                ))}
              </defs>
              <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
                <path d="M 40 0 L 0 0 0 40" fill="none" stroke="#e0e0e0" strokeWidth="0.5" opacity="0.4" />
              </pattern>
              <rect width="1000" height="650" fill="url(#grid)" />

              <g transform={`translate(${pan.x},${pan.y}) scale(${zoom})`}>
                {/* Edges */}
                {edges.map((e, i) => {
                  const s = nodes.find((n) => n.id === e.source);
                  const t = nodes.find((n) => n.id === e.target);
                  if (!s || !t) return null;
                  const hl = (sel && (e.source === sel.id || e.target === sel.id)) ||
                    (hover && (e.source === hover || e.target === hover));
                  const dim = sel && !hl;
                  return (
                    <g key={`e${i}`} opacity={dim ? 0.08 : 1}>
                      <line
                        x1={s.x} y1={s.y} x2={t.x} y2={t.y}
                        stroke={hl ? "#1677ff" : "#d0d0d0"}
                        strokeWidth={hl ? 2.5 : 1}
                      />
                      <rect
                        x={(s.x + t.x) / 2 - 22} y={(s.y + t.y) / 2 - 10}
                        width={44} height={18} rx={9}
                        fill={hl ? "#e6f4ff" : "white"}
                        stroke={hl ? "#1677ff" : "#e0e0e0"} strokeWidth={0.5}
                      />
                      <text
                        x={(s.x + t.x) / 2} y={(s.y + t.y) / 2 + 4}
                        textAnchor="middle" fontSize={9}
                        fill={hl ? "#1677ff" : "#999"} fontWeight={hl ? 600 : 400}
                      >
                        {e.relation}
                      </text>
                    </g>
                  );
                })}

                {/* Nodes */}
                {nodes.map((n) => {
                  const c = COLORS[n.data.node_type] || "#999";
                  const isSel = sel?.id === n.id;
                  const isNeighbor = selNeighbors.has(n.id) || hoverNeighbors.has(n.id);
                  const dimmed = (sel || hover) && !isSel && !isNeighbor;
                  return (
                    <g
                      key={n.id}
                      onClick={() => setSel(isSel ? null : n.data)}
                      onMouseEnter={() => setHover(n.id)}
                      onMouseLeave={() => setHover(null)}
                      style={{ cursor: "pointer" }}
                      opacity={dimmed ? 0.15 : 1}
                    >
                      {isSel && (
                        <circle cx={n.x} cy={n.y} r={n.radius + 6} fill="none" stroke={c} strokeWidth={2} opacity={0.4}>
                          <animate attributeName="r" from={n.radius + 3} to={n.radius + 12} dur="1.5s" repeatCount="indefinite" />
                          <animate attributeName="opacity" from={0.5} to={0} dur="1.5s" repeatCount="indefinite" />
                        </circle>
                      )}
                      <circle cx={n.x} cy={n.y} r={n.radius} fill={c} stroke="#fff" strokeWidth={isSel ? 3 : 1.5} />
                      <text x={n.x} y={n.y + 1} textAnchor="middle" fontSize={n.data.node_type === "topic" ? 11 : 10} fill="#fff" fontWeight={700}>
                        {n.data.node_type === "law" ? "法" : n.data.node_type === "standard" ? "标" : n.data.node_type === "policy" ? "政" : "题"}
                      </text>
                      <text x={n.x} y={n.y + n.radius + 14} textAnchor="middle" fontSize={11} fontWeight={600} fill={isSel ? c : "#333"}>
                        {(n.data.code || n.data.label).slice(0, 16)}
                      </text>
                    </g>
                  );
                })}
              </g>
            </svg>

            {/* Mini navigation */}
            <div style={{
              position: "absolute", bottom: 10, right: 10,
              width: 120, height: 80, borderRadius: 6,
              background: "rgba(255,255,255,0.85)", border: "1px solid #e8e8e8",
              overflow: "hidden", boxShadow: "0 2px 6px rgba(0,0,0,0.06)",
            }}>
              <svg width={120} height={80} viewBox="0 0 1000 650">
                <rect width={1000} height={650} fill="#f0f2f5" />
                {edges.map((e, i) => {
                  const s = nodes.find((n) => n.id === e.source);
                  const t = nodes.find((n) => n.id === e.target);
                  if (!s || !t) return null;
                  return <line key={`m${i}`} x1={s.x} y1={s.y} x2={t.x} y2={t.y} stroke="#ddd" strokeWidth={0.5} />;
                })}
                {nodes.map((n) => (
                  <circle key={n.id} cx={n.x} cy={n.y} r={2} fill={COLORS[n.data.node_type] || "#999"} />
                ))}
                <rect x={-pan.x / zoom} y={-pan.y / zoom} width={1000 / zoom} height={650 / zoom}
                  fill="none" stroke="#1677ff" strokeWidth={1.5} rx={2} />
              </svg>
            </div>
          </div>
        </Card>

        {/* Legend */}
        <div style={{ display: "flex", gap: 24, marginTop: 14, justifyContent: "center", flexWrap: "wrap" }}>
          {Object.entries(TYPE_LABELS).map(([k, v]) => (
            <Space key={k} size={6}>
              <span style={{ width: 12, height: 12, borderRadius: "50%", background: COLORS[k], display: "inline-block" }} />
              <Text style={{ fontSize: 12, color: "#666" }}>{v}</Text>
            </Space>
          ))}
          <span style={{ color: "#ddd" }}>|</span>
          {Object.entries(EDGE_COLORS).map(([k, v]) => (
            <Space key={k} size={6}>
              <span style={{ width: 20, height: 2, background: v, display: "inline-block", borderRadius: 1 }} />
              <Text style={{ fontSize: 12, color: "#666" }}>{k}</Text>
            </Space>
          ))}
        </div>
      </div>

      {/* Detail panel */}
      {sel && (
        <div style={{ width: 280, flexShrink: 0 }}>
          <Card
            title={
              <Space>
                <span style={{ width: 10, height: 10, borderRadius: "50%", background: COLORS[sel.node_type] || "#999", display: "inline-block" }} />
                <Text strong style={{ fontSize: 13 }}>{sel.code || sel.label}</Text>
              </Space>
            }
            size="small"
            style={{ borderRadius: 12, position: "sticky", top: 24 }}
            extra={<a onClick={() => setSel(null)} style={{ cursor: "pointer", fontSize: 12 }}>关闭</a>}
          >
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              <div>
                <Text style={{ fontSize: 12, color: "#8c8c8c" }}>全称</Text>
                <div style={{ fontSize: 13, marginTop: 2 }}>{sel.full_name}</div>
              </div>
              <div style={{ display: "flex", gap: 8 }}>
                <Tag color={sel.status === "abolished" ? "red" : "green"}>
                  {sel.status === "effective" ? "现行有效" : "已废止"}
                </Tag>
                <Tag>{TYPE_LABELS[sel.node_type] || sel.node_type}</Tag>
              </div>
              {sel.effective_date && (
                <div><Text style={{ fontSize: 12, color: "#8c8c8c" }}>施行日期</Text><div style={{ fontSize: 13 }}>{sel.effective_date}</div></div>
              )}
              {sel.issuing_body && (
                <div><Text style={{ fontSize: 12, color: "#8c8c8c" }}>发布机关</Text><div style={{ fontSize: 13 }}>{sel.issuing_body}</div></div>
              )}
              {sel.article_count > 0 && (
                <div><Text style={{ fontSize: 12, color: "#8c8c8c" }}>条文数量</Text><div style={{ fontSize: 13, fontWeight: 600, color: "#1677ff" }}>{sel.article_count} 条</div></div>
              )}
              {sel.topics && sel.topics.length > 0 && (
                <div>
                  <Text style={{ fontSize: 12, color: "#8c8c8c", display: "block", marginBottom: 4 }}>适用主题</Text>
                  <Space wrap size={[4, 4]}>
                    {sel.topics.map((t: string) => <Tag key={t} color="blue">{t}</Tag>)}
                  </Space>
                </div>
              )}
              {selEdges.length > 0 && (
                <div>
                  <Text style={{ fontSize: 12, color: "#8c8c8c", display: "block", marginBottom: 4 }}>关联法规</Text>
                  <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                    {selEdges.map((e, i) => {
                      const other = e.source === sel.id ? e.target : e.source;
                      const otherNode = nodes.find((n) => n.id === other);
                      return (
                        <div key={i} style={{ fontSize: 12, display: "flex", alignItems: "center", gap: 6 }}>
                          <Tag color={EDGE_COLORS[e.relation] || "default"} style={{ fontSize: 10, lineHeight: "16px" }}>
                            {e.relation}
                          </Tag>
                          <Text ellipsis style={{ maxWidth: 180 }}>
                            {otherNode?.data?.code || otherNode?.data?.label || other}
                          </Text>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}
