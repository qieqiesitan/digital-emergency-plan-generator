import { useState } from "react";
import { useParams } from "react-router-dom";
import {
  Alert,
  Button,
  Result,
  Segmented,
  Spin,
  Table,
  Tag,
  Tooltip,
  Typography,
} from "antd";
import type { TableColumnsType } from "antd";
import { useQuery } from "@tanstack/react-query";
import axios from "axios";
import { fetchPublicHazard } from "@/services/hazardService";
import type { HazardPublicityItem } from "@/types/hazard";

const LEVEL_LABELS: Record<string, string> = {
  major: "重大",
  general: "一般",
};

const SCOPE_OPTIONS = [
  { label: "全部", value: "all" },
  { label: "进行中", value: "ongoing" },
  { label: "已闭环", value: "closed" },
];

function formatTime(iso?: string) {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString();
}

/** 隐患公示公开页（/h/:token，免登录脱敏只读，§11.2）。 */
export default function PublicHazardPage() {
  const { token = "" } = useParams<{ token: string }>();
  const [scope, setScope] = useState<string>("all");

  const { data, error, isLoading, isError, refetch } = useQuery({
    queryKey: ["public-hazard", token, scope],
    queryFn: () => fetchPublicHazard(token, scope === "all" ? undefined : scope),
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

  const columns: TableColumnsType<HazardPublicityItem> = [
    { title: "编号", dataIndex: "code", width: 110 },
    {
      title: "标题",
      dataIndex: "title",
      ellipsis: true,
      render: (v: string) => (
        <Tooltip title={v}>
          <span>{v}</span>
        </Tooltip>
      ),
    },
    {
      title: "等级",
      dataIndex: "level",
      width: 80,
      render: (v: string) => {
        if (!v) return <span>—</span>;
        return (
          <Tag color={v === "major" ? "red" : "blue"}>{LEVEL_LABELS[v] || v}</Tag>
        );
      },
    },
    { title: "状态", dataIndex: "status", width: 100 },
    {
      title: "整改情况",
      dataIndex: "rectification",
      ellipsis: true,
      render: (v: string) => (
        <Tooltip title={v}>
          <span>{v}</span>
        </Tooltip>
      ),
    },
    { title: "来源", dataIndex: "source_type", width: 110 },
  ];

  return (
    <div style={{ margin: "0 auto", maxWidth: 1000, padding: "24px 16px 32px" }}>
      <Alert
        type="info"
        showIcon
        message="公开只读页面 · 数据已脱敏 · 无需登录"
        style={{ marginBottom: 20 }}
      />
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 16,
          flexWrap: "wrap",
          gap: 12,
        }}
      >
        <div>
          <Typography.Title level={4} style={{ marginBottom: 4 }}>
            {data.enterprise_name} 隐患整改公示
          </Typography.Title>
          <Typography.Text type="secondary">
            生成时间：{formatTime(data.generated_at)}
            {data.masked ? (
              <Tag color="green" style={{ marginLeft: 8 }}>
                已脱敏
              </Tag>
            ) : null}
          </Typography.Text>
        </div>
        <Segmented
          options={SCOPE_OPTIONS}
          value={scope}
          onChange={value => setScope(String(value))}
        />
      </div>
      <Table<HazardPublicityItem>
        rowKey="code"
        dataSource={data.items}
        columns={columns}
        size="middle"
        scroll={{ x: 760 }}
        pagination={{ pageSize: 20, showTotal: t => `共 ${t} 条` }}
        locale={{ emptyText: "暂无公示数据" }}
      />
      <div style={{ color: "#8c8c8c", fontSize: 12, marginTop: 16, textAlign: "center" }}>
        公开只读页面 · 数据为实时生成 · 无需登录
      </div>
    </div>
  );
}
