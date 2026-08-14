import { useMemo } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { App as AntApp, Button, Card, Empty, Space, Spin, Table, Tag, Tooltip, Typography } from "antd";
import type { TableColumnsType } from "antd";
import { useQuery } from "@tanstack/react-query";
import { getRiskPublicity, resetRiskPublicityToken } from "@/services/riskManagementService";
import type { ControlListRow, PublicityZone } from "@/services/riskManagementService";
import { PageHeader } from "@/components/common/PageHeader";
import { RISK_LEVEL_COLORS } from "@/utils/riskMethodEngine";
import { toCanvasX, toCanvasY } from "@/utils/riskMappingGeometry";

const MAP_WIDTH = 1200;
const MAP_HEIGHT = 640;
const LEGEND = [
  { level: "重大", color: RISK_LEVEL_COLORS["重大"] },
  { level: "较大", color: RISK_LEVEL_COLORS["较大"] },
  { level: "一般", color: RISK_LEVEL_COLORS["一般"] },
  { level: "低", color: RISK_LEVEL_COLORS["低"] },
];

function formatTime(iso?: string) {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString();
}

/**
 * 四色分布图适配器：RiskDistributionStage 组件按自身契约从 /overview 拉取数据，
 * 不接受外部 zones 入参；公示页改用后端 risk-publicity.zones 数据，以同口径
 * （分区多边形 + effective_color 有效色）用 SVG 渲染静态四色图，便于打印。
 */
function PublicityMap({ zones }: { zones: PublicityZone[] }) {
  const zonesWithPolygon = zones.filter(z => z.floor_plan_polygon?.polygons?.length);
  if (!zonesWithPolygon.length) {
    return <Empty description="暂无四色分布图数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />;
  }
  return (
    <div>
      <div
        style={{
          border: "1px solid #f0f0f0",
          borderRadius: 8,
          background: "#fafafa",
          overflow: "auto",
        }}
      >
        <svg
          width="100%"
          viewBox={`0 0 ${MAP_WIDTH} ${MAP_HEIGHT}`}
          style={{ minWidth: 720, display: "block" }}
          role="img"
          aria-label="重大风险四色分布图"
        >
          {zonesWithPolygon.map(z =>
            (z.floor_plan_polygon?.polygons ?? []).map(p => (
              <polygon
                key={`${z.id}-${p.id}`}
                points={p.points
                  .map(pt => `${toCanvasX(pt.x, MAP_WIDTH)},${toCanvasY(pt.y, MAP_HEIGHT)}`)
                  .join(" ")}
                fill={z.effective_color || "#d9d9d9"}
                stroke={z.effective_color || "#d9d9d9"}
                strokeWidth={2}
                opacity={0.45}
              />
            )),
          )}
          {zonesWithPolygon.map(z => {
            const first = z.floor_plan_polygon?.polygons?.[0]?.points?.[0];
            return first ? (
              <text
                key={z.id}
                x={toCanvasX(first.x, MAP_WIDTH)}
                y={toCanvasY(first.y, MAP_HEIGHT) - 10}
                fontSize={16}
                fontWeight={600}
                fill="#333"
              >
                {z.name}
              </text>
            ) : null;
          })}
        </svg>
      </div>
      <Space style={{ marginTop: 8 }} wrap>
        {LEGEND.map(item => (
          <Space key={item.level} size={6}>
            <span
              style={{
                display: "inline-block",
                width: 14,
                height: 14,
                borderRadius: 3,
                background: item.color,
                border: "1px solid rgba(0,0,0,.12)",
              }}
            />
            <Typography.Text type="secondary">{item.level}</Typography.Text>
          </Space>
        ))}
      </Space>
    </div>
  );
}

/** 重大风险公示页（四色图 + 重大风险清单 + 公开链接管理）。 */
export default function RiskPublicityPage() {
  const { id: enterpriseId = "" } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { modal, message } = AntApp.useApp();

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["risk-publicity", enterpriseId],
    queryFn: () => getRiskPublicity(enterpriseId).then(r => r.data.data),
    enabled: !!enterpriseId,
  });

  const floorGroups = useMemo(() => {
    const groups: { floorId: string; floorName: string; zones: PublicityZone[] }[] = [];
    for (const z of data?.zones ?? []) {
      const key = z.floor_id || "default";
      let group = groups.find(g => g.floorId === key);
      if (!group) {
        group = { floorId: key, floorName: z.floor_name || "未命名楼层", zones: [] };
        groups.push(group);
      }
      group.zones.push(z);
    }
    return groups;
  }, [data]);

  const publicUrl = data ? `${window.location.origin}/p/risk/${data.token}` : "";

  const copyLink = async () => {
    try {
      await navigator.clipboard.writeText(publicUrl);
      message.success("公开链接已复制");
    } catch {
      message.error("复制失败，请手动复制");
    }
  };

  const handleResetToken = () => {
    modal.confirm({
      title: "确认重置公开链接？",
      content: "重置后原链接将立即失效，需要重新公示新链接。",
      okText: "确认重置",
      cancelText: "取消",
      onOk: close => {
        resetRiskPublicityToken(enterpriseId)
          .then(() => {
            message.success("链接已重置");
            void refetch();
            close();
          })
          .catch(() => {
            message.error("重置失败，请稍后重试");
          });
      },
    });
  };

  const columns: TableColumnsType<ControlListRow> = [
    { title: "分区", dataIndex: "zone", width: 110, ellipsis: true },
    { title: "风险点", dataIndex: "object", width: 130, ellipsis: true },
    { title: "位置", dataIndex: "location", width: 120, ellipsis: true },
    { title: "事故类型", dataIndex: "accident", width: 110, ellipsis: true },
    {
      title: "现有等级",
      dataIndex: "current",
      width: 80,
      render: (level?: string) => {
        const color = level ? RISK_LEVEL_COLORS[level] : undefined;
        return color ? <Tag color={color}>{level}</Tag> : <span>—</span>;
      },
    },
    { title: "管控层级", dataIndex: "control_level", width: 85 },
    { title: "责任单位", dataIndex: "unit_name", width: 120, ellipsis: true },
    {
      title: "告知卡入口",
      dataIndex: "object_id",
      width: 110,
      render: (objectId?: string) =>
        objectId ? (
          <Button type="link" size="small" onClick={() => navigate(`/enterprises/${enterpriseId}/risk-notice-cards/${objectId}`)}>
            查看告知卡
          </Button>
        ) : (
          <span>—</span>
        ),
    },
    {
      title: "主要措施",
      dataIndex: "measures",
      ellipsis: true,
      render: (measures: string) => (
        <Tooltip title={measures}><span>{measures}</span></Tooltip>
      ),
    },
  ];

  if (isLoading) {
    return <Spin size="large" style={{ display: "block", margin: "100px auto" }} />;
  }

  return (
    <div className="risk-publicity-page">
      <style>{`@media print {
        .risk-publicity-page .risk-publicity-actions,
        .risk-publicity-page button { display: none !important; }
      }`}</style>
      <PageHeader
        title="重大风险公示"
        subtitle="面向全员公示重大风险及管控信息，可打印公告或复制公开脱敏链接"
        onBack={() => navigate(-1)}
      />

      {isError || !data ? (
        <Empty description="公示数据加载失败，请稍后重试">
          <Button type="primary" onClick={() => void refetch()}>重新加载</Button>
        </Empty>
      ) : (
        <>
          <Card
            size="small"
            title="公开链接（数据已脱敏，无需登录）"
            className="risk-publicity-actions"
            style={{ marginBottom: 16 }}
            extra={
              <Space>
                <Button onClick={() => void refetch()}>刷新</Button>
                <Button danger onClick={handleResetToken}>重置链接</Button>
              </Space>
            }
          >
            <Space wrap>
              <Typography.Text code copyable={{ text: publicUrl }} style={{ fontSize: 13 }}>
                {publicUrl}
              </Typography.Text>
              <Button onClick={() => void copyLink()}>复制</Button>
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                生成时间：{formatTime(data.generated_at)}
              </Typography.Text>
            </Space>
          </Card>

          {floorGroups.map(group => (
          <Card
            key={group.floorId}
            size="small"
            title={`四色分布图（${group.floorName}）`}
            style={{ marginBottom: 16 }}
          >
              <PublicityMap zones={group.zones} />
            </Card>
          ))}

          <Card size="small" title="重大风险清单">
            <Table<ControlListRow>
              rowKey={(record, index) => `${record.zone}-${record.object}-${record.accident}-${index}`}
              dataSource={data.items}
              columns={columns}
              size="small"
              scroll={{ x: 1120 }}
              pagination={{ pageSize: 20, showTotal: t => `共 ${t} 条` }}
              locale={{ emptyText: "暂无重大风险" }}
            />
          </Card>
        </>
      )}
    </div>
  );
}
