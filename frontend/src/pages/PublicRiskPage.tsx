import axios from "axios";
import { useParams } from "react-router-dom";
import { Alert, Button, Result, Spin, Table, Tag, Tooltip, Typography } from "antd";
import type { TableColumnsType } from "antd";
import { useQuery } from "@tanstack/react-query";
import { fetchPublicRisk } from "@/services/riskManagementService";
import type { PublicRiskRow } from "@/services/riskManagementService";
import { RISK_LEVEL_COLORS } from "@/utils/riskMethodEngine";

function formatTime(iso?: string) {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString();
}

/** 重大风险公示公开只读页（/p/risk/:token，无登录守卫）。 */
export default function PublicRiskPage() {
  const { token = "" } = useParams<{ token: string }>();

  const { data, error, isLoading, isError, refetch } = useQuery({
    queryKey: ["public-risk", token],
    queryFn: () => fetchPublicRisk(token),
    retry: false,
    enabled: !!token,
  });

  if (isLoading) {
    return <Spin size="large" style={{ display: "block", margin: "100px auto" }} />;
  }

  if (isError || !data) {
    const isNotFound = axios.isAxiosError(error) && error.response?.status === 404;
    if (isNotFound) {
      return (
        <Result
          status="404"
          title="链接已失效"
          subTitle="该公示链接已失效，请联系企业管理员获取最新链接"
        />
      );
    }
    return (
      <Result
        status="warning"
        title="加载失败"
        subTitle="网络异常或服务暂不可用，请稍后重试"
        extra={
          <Button type="primary" onClick={() => void refetch()}>
            重试
          </Button>
        }
      />
    );
  }

  const columns: TableColumnsType<PublicRiskRow> = [
    { title: "分区", dataIndex: "zone", width: 110, ellipsis: true },
    { title: "风险点", dataIndex: "object", width: 130, ellipsis: true },
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
      title: "主要措施",
      dataIndex: "measures",
      ellipsis: true,
      render: (measures: string) => (
        <Tooltip title={measures}><span>{measures}</span></Tooltip>
      ),
    },
  ];

  return (
    <div style={{ margin: "0 auto", maxWidth: 1000, padding: "24px 16px 32px" }}>
      <Alert
        type="info"
        showIcon
        message="公开只读页面 · 数据已脱敏 · 无需登录"
        style={{ marginBottom: 20 }}
      />
      <div style={{ marginBottom: 16 }}>
        <Typography.Title level={4} style={{ marginBottom: 4 }}>
          {data.enterprise_name} 重大风险公示
        </Typography.Title>
        <Typography.Text type="secondary">
          生成时间：{formatTime(data.generated_at)}
        </Typography.Text>
      </div>
      <Table<PublicRiskRow>
        rowKey={(record, index) => `${record.zone}-${record.object}-${record.accident}-${index}`}
        dataSource={data.items}
        columns={columns}
        size="middle"
        scroll={{ x: 900 }}
        pagination={{ pageSize: 20, showTotal: t => `共 ${t} 条` }}
        locale={{ emptyText: "暂无重大风险公示数据" }}
      />
      <div style={{ color: "#8c8c8c", fontSize: 12, marginTop: 16, textAlign: "center" }}>
        公开只读页面 · 数据为实时生成 · 无需登录
      </div>
    </div>
  );
}
