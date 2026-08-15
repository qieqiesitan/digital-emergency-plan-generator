import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  App as AntApp,
  Badge,
  Button,
  Card,
  Col,
  Empty,
  Row,
  Skeleton,
  Space,
  Statistic,
  Table,
  Tag,
  Tooltip,
  Typography,
} from "antd";
import type { TableColumnsType } from "antd";
import { DownloadOutlined, FileExcelOutlined } from "@ant-design/icons";
import { useQuery } from "@tanstack/react-query";
import {
  exportHazardLedger,
  exportHazardReport,
  getHazardDashboard,
} from "@/services/hazardService";
import { PageHeader } from "@/components/common/PageHeader";

const { Text } = Typography;

const PIE_COLORS = [
  "#1677ff",
  "#52c41a",
  "#faad14",
  "#f5222d",
  "#722ed1",
  "#13c2c2",
  "#eb2f96",
  "#8c8c8c",
];

const STATUS_TAG_COLORS: Record<string, string> = {
  registered: "default",
  grading: "orange",
  pending_approval: "gold",
  rectifying: "blue",
  reviewing: "cyan",
  second_review: "purple",
  closed: "green",
};

const STATUS_LABELS: Record<string, string> = {
  registered: "已登记",
  grading: "待分级",
  pending_approval: "待审批",
  rectifying: "整改中",
  reviewing: "复查中",
  second_review: "二次复核",
  closed: "已销号",
};

function fmtNumber(v: number | null | undefined, suffix = ""): string {
  if (v === null || v === undefined) return "—";
  return `${v}${suffix}`;
}

function fmtMom(v: number | null | undefined): string {
  if (v === null || v === undefined) return "—";
  return `${v > 0 ? "+" : ""}${v}%`;
}

function polarToCartesian(cx: number, cy: number, r: number, angleDeg: number) {
  const rad = ((angleDeg - 90) * Math.PI) / 180;
  return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) };
}

function pieArcPath(cx: number, cy: number, r: number, startDeg: number, endDeg: number) {
  const start = polarToCartesian(cx, cy, r, endDeg);
  const end = polarToCartesian(cx, cy, r, startDeg);
  const largeArc = endDeg - startDeg > 180 ? 1 : 0;
  return `M ${cx} ${cy} L ${start.x} ${start.y} A ${r} ${r} 0 ${largeArc} 0 ${end.x} ${end.y} Z`;
}

/** 隐患类型分布饼图（轻量 SVG，无重型图表依赖，§12）。 */
function TypePieChart({ data }: { data: { hazard_type: string; count: number }[] }) {
  const total = data.reduce((sum, d) => sum + d.count, 0);
  if (!total) {
    return <Empty description="暂无隐患数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />;
  }
  const cx = 90;
  const cy = 90;
  const r = 72;
  const slices = data.reduce<Array<{
    hazard_type: string;
    count: number;
    color: string;
    path: string;
    percent: number;
    endDeg: number;
  }>>((acc, d, i) => {
    const startDeg = acc.length ? acc[acc.length - 1].endDeg : 0;
    const endDeg = startDeg + (d.count / total) * 360;
    acc.push({
      ...d,
      color: PIE_COLORS[i % PIE_COLORS.length],
      path: pieArcPath(cx, cy, r, startDeg, endDeg),
      percent: total ? Math.round((d.count / total) * 100) : 0,
      endDeg,
    });
    return acc;
  }, []);
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 20, flexWrap: "wrap" }}>
      <svg width={180} height={180} viewBox="0 0 180 180" role="img" aria-label="隐患类型分布饼图">
        {slices.map(s => (
          <path key={s.hazard_type} d={s.path} fill={s.color} stroke="#fff" strokeWidth={2} />
        ))}
        <text x={cx} y={cy - 4} textAnchor="middle" fontSize={20} fontWeight={600} fill="#333">
          {total}
        </text>
        <text x={cx} y={cy + 16} textAnchor="middle" fontSize={12} fill="#8c8c8c">
          隐患总数
        </text>
      </svg>
      <div style={{ display: "flex", flexDirection: "column", gap: 8, minWidth: 160 }}>
        {slices.map(s => (
          <Space key={s.hazard_type} size={8}>
            <span
              style={{
                display: "inline-block",
                width: 12,
                height: 12,
                borderRadius: 3,
                background: s.color,
              }}
            />
            <Text style={{ fontSize: 13 }}>{s.hazard_type}</Text>
            <Text type="secondary" style={{ fontSize: 13 }}>
              {s.count}（{s.percent}%）
            </Text>
          </Space>
        ))}
      </div>
    </div>
  );
}

/** 近 12 月隐患趋势折线图（轻量 SVG，无重型图表依赖，§12）。 */
function MonthlyTrendChart({ data }: { data: { month: string; count: number }[] }) {
  if (!data.length) {
    return <Empty description="暂无趋势数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />;
  }
  const width = 640;
  const height = 240;
  const padL = 36;
  const padR = 12;
  const padT = 16;
  const padB = 30;
  const innerW = width - padL - padR;
  const innerH = height - padT - padB;
  const maxCount = Math.max(1, ...data.map(d => d.count));
  const points = data.map((d, i) => {
    const x = padL + (data.length > 1 ? (innerW * i) / (data.length - 1) : innerW / 2);
    const y = padT + innerH - (d.count / maxCount) * innerH;
    return { ...d, x, y };
  });
  const gridLines = [0, 0.25, 0.5, 0.75, 1].map(f => ({
    y: padT + innerH - f * innerH,
    value: Math.round(maxCount * f),
  }));
  return (
    <div style={{ overflowX: "auto" }}>
      <svg
        width="100%"
        viewBox={`0 0 ${width} ${height}`}
        style={{ minWidth: 420, display: "block" }}
        role="img"
        aria-label="近 12 月隐患趋势折线图"
      >
        {gridLines.map(g => (
          <g key={g.value}>
            <line x1={padL} y1={g.y} x2={width - padR} y2={g.y} stroke="#f0f0f0" strokeDasharray="4 4" />
            <text x={padL - 6} y={g.y + 4} textAnchor="end" fontSize={11} fill="#999">
              {g.value}
            </text>
          </g>
        ))}
        <polyline
          points={points.map(p => `${p.x},${p.y}`).join(" ")}
          fill="none"
          stroke="#1677ff"
          strokeWidth={2}
          strokeLinejoin="round"
          strokeLinecap="round"
        />
        {points.map(p => (
          <circle key={p.month} cx={p.x} cy={p.y} r={3.5} fill="#1677ff" />
        ))}
        {points.map((p, i) =>
          i % 2 === 0 || i === points.length - 1 ? (
            <text key={`label-${p.month}`} x={p.x} y={height - 8} textAnchor="middle" fontSize={11} fill="#999">
              {p.month.slice(5)}
            </text>
          ) : null,
        )}
      </svg>
    </div>
  );
}

/** 同账号多企业未闭环对比（横向条形，轻量 div，§12）。 */
function EnterpriseCompareChart({ data }: { data: { enterprise_id: string; name: string; open_count: number }[] }) {
  if (!data.length) {
    return <Empty description="当前账号名下暂无其他企业" image={Empty.PRESENTED_IMAGE_SIMPLE} />;
  }
  const maxCount = Math.max(1, ...data.map(d => d.open_count));
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      {data.map(d => (
        <div key={d.enterprise_id}>
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
            <Tooltip title={d.name}>
              <Text style={{ fontSize: 13, maxWidth: 180 }} ellipsis>
                {d.name}
              </Text>
            </Tooltip>
            <Text type="secondary" style={{ fontSize: 13 }}>
              {d.open_count} 条
            </Text>
          </div>
          <div style={{ background: "#f0f0f0", borderRadius: 4, height: 10, overflow: "hidden" }}>
            <div
              style={{
                width: `${(d.open_count / maxCount) * 100}%`,
                height: "100%",
                background: "#1677ff",
                borderRadius: 4,
              }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}

/** 隐患驾驶舱（§12）：指标卡 + 图表 + 未读角标 + 导出。 */
export default function HazardDashboardPage() {
  const { id: enterpriseId = "" } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { message } = AntApp.useApp();
  const [exporting, setExporting] = useState<"ledger" | "report" | null>(null);

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["hazard-dashboard", enterpriseId],
    queryFn: () => getHazardDashboard(enterpriseId),
    enabled: !!enterpriseId,
  });

  const handleExport = async (kind: "ledger" | "report") => {
    if (exporting) return;
    setExporting(kind);
    try {
      const res = kind === "ledger" ? await exportHazardLedger(enterpriseId) : await exportHazardReport(enterpriseId);
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const a = document.createElement("a");
      a.href = url;
      a.download = kind === "ledger" ? "hazard_ledger.xlsx" : "hazard_report.xlsx";
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
      message.success(kind === "ledger" ? "台账导出成功" : "监管台账导出成功");
    } catch {
      message.error("导出失败，请稍后重试");
    } finally {
      setExporting(null);
    }
  };

  if (isLoading) {
    return <Skeleton active paragraph={{ rows: 8 }} />;
  }

  if (isError || !data) {
    return (
      <div>
        <PageHeader title="隐患驾驶舱" onBack={() => navigate(-1)} />
        <Empty description="驾驶舱数据加载失败，请稍后重试">
          <Button type="primary" onClick={() => void refetch()}>
            重新加载
          </Button>
        </Empty>
      </div>
    );
  }

  const payload = data;
  const unreadTypes = Object.entries(payload.unread.by_type).map(([type, count]) => `${type}: ${count}`);
  const unreadTip = [
    `企业内未读总数 ${payload.unread.total}`,
    `我的未读 ${payload.unread.mine}`,
    unreadTypes.length ? `类型分布：${unreadTypes.join("，")}` : "",
  ]
    .filter(Boolean)
    .join("；");

  const majorColumns: TableColumnsType<{ code: string; title: string; deadline: string | null; status: string }> = [
    { title: "编号", dataIndex: "code", width: 110 },
    { title: "标题", dataIndex: "title", ellipsis: true },
    {
      title: "整改期限",
      dataIndex: "deadline",
      width: 120,
      render: (v: string | null) => (v ? v.slice(0, 10) : "—"),
    },
    {
      title: "状态",
      dataIndex: "status",
      width: 100,
      render: (v: string) => (
        <Tag color={STATUS_TAG_COLORS[v] || "default"}>{STATUS_LABELS[v] || v}</Tag>
      ),
    },
  ];

  const m = payload.metrics;
  const metricCards = [
    {
      key: "open_hazards",
      title: "未闭环隐患",
      value: m.open_hazards as number | null,
      suffix: "条",
      color: "#1677ff",
    },
    {
      key: "open_risk_points",
      title: "未闭环风险点",
      value: m.open_risk_points as number | null,
      suffix: "个",
      color: "#1677ff",
    },
    {
      key: "rectification_rate",
      title: "整改及时率",
      value: m.rectification_rate,
      suffix: "%",
      color: "#52c41a",
      footer: `按期闭环 ${m.on_time_closed} / 应闭环 ${m.due_this_month}`,
    },
    {
      key: "avg_days",
      title: "平均整改周期",
      value: m.avg_rectification_days,
      suffix: "天",
      color: "#722ed1",
      footer: "本月闭环记录（闭环时间 − 登记时间）",
    },
    {
      key: "major",
      title: "重大挂牌",
      value: m.major_count as number | null,
      suffix: "条",
      color: "#f5222d",
      footer: `已挂牌审批 ${m.major_approved}`,
    },
    {
      key: "overdue",
      title: "超期",
      value: m.overdue_count as number | null,
      suffix: "条",
      color: "#f5222d",
      footer: `隐患记录 ${m.overdue_records} · 排查任务 ${m.overdue_tasks}`,
    },
    {
      key: "monthly",
      title: "本月新增",
      value: m.monthly_new as number | null,
      suffix: "条",
      color: "#13c2c2",
      footer: `环比 ${fmtMom(m.monthly_new_mom)}`,
    },
    {
      key: "scan_pending",
      title: "扫码待确认",
      value: m.scan_pending as number | null,
      suffix: "条",
      color: "#faad14",
      footer: "公开上报 registered 待处理",
    },
  ];

  return (
    <div>
      <PageHeader
        title="隐患驾驶舱"
        subtitle="企业隐患排查治理综合态势（指标口径与后端 dashboard 一致）"
        onBack={() => navigate(-1)}
        extra={
          <Space wrap>
            <Tooltip title={unreadTip}>
              <Badge count={payload.unread.mine} size="small" overflowCount={99}>
                <Button>我的未读</Button>
              </Badge>
            </Tooltip>
            <Button
              icon={<DownloadOutlined />}
              loading={exporting === "ledger"}
              onClick={() => void handleExport("ledger")}
            >
              台账导出
            </Button>
            <Button
              icon={<FileExcelOutlined />}
              loading={exporting === "report"}
              onClick={() => void handleExport("report")}
            >
              监管导出
            </Button>
          </Space>
        }
      />

      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        {metricCards.map(card => (
          <Col xs={24} sm={12} lg={6} key={card.key}>
            <Card size="small">
              <Statistic
                title={card.title}
                value={card.value ?? 0}
                valueStyle={{ color: card.color }}
                suffix={card.suffix}
                formatter={() => fmtNumber(card.value, card.suffix)}
              />
              {card.footer ? (
                <Text type="secondary" style={{ fontSize: 12 }}>
                  {card.footer}
                </Text>
              ) : null}
            </Card>
          </Col>
        ))}
      </Row>

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={12}>
          <Card size="small" title="隐患类型分布" style={{ marginBottom: 16 }}>
            <TypePieChart data={payload.charts.type_distribution} />
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card size="small" title="月度趋势（近 12 月）" style={{ marginBottom: 16 }}>
            <MonthlyTrendChart data={payload.charts.monthly_trend} />
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card size="small" title="重大隐患专表" style={{ marginBottom: 16 }}>
            <Table<{ code: string; title: string; deadline: string | null; status: string }>
              rowKey="code"
              dataSource={payload.charts.major_records}
              columns={majorColumns}
              size="small"
              pagination={false}
              locale={{ emptyText: "暂无重大隐患" }}
              scroll={{ y: 260 }}
            />
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card size="small" title="企业对比（同账号多企业未闭环）" style={{ marginBottom: 16 }}>
            <EnterpriseCompareChart data={payload.charts.enterprise_comparison} />
          </Card>
        </Col>
      </Row>
    </div>
  );
}
