import { useState } from "react";
import { App as AntApp, Card, Col, Row, Space, Statistic, Switch, Table, Tag, Typography } from "antd";
import type { TableColumnsType } from "antd";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { PageHeader } from "@/components/common/PageHeader";
import {
  getAiUsage,
  listCapabilities,
  updateCapability,
  type AiCapability,
  type CapabilityUpdatePayload,
  type CapabilityUsage,
} from "@/services/platformService";

const { Text } = Typography;

/**
 * AI 能力管理页。
 *
 * 上半部分是「能力注册表」（哪个模块有什么 AI 能力、关联哪个提示词、用哪个模型、开不开），
 * 下半部分是「调用统计」（近 30 天按能力的调用数 / 失败率 / 截断数 / 平均耗时）。
 *
 * 为什么要单独盯「截断数」：流式调用被中途掐断时 success 仍可能为 True，
 * 结果是半截文本却看不出来——这个指标就是给那种静默故障用的。
 */
export default function AiCapabilityPage() {
  const { message } = AntApp.useApp();
  const queryClient = useQueryClient();
  const [savingCode, setSavingCode] = useState<string | null>(null);

  const { data: capabilities = [], isLoading } = useQuery({
    queryKey: ["ai-capabilities"],
    queryFn: listCapabilities,
  });
  const { data: usage, isLoading: usageLoading } = useQuery({
    queryKey: ["ai-usage", 30],
    queryFn: () => getAiUsage(30),
  });

  const patch = async (code: string, payload: CapabilityUpdatePayload) => {
    setSavingCode(code);
    try {
      await updateCapability(code, payload);
      message.success("已更新");
      queryClient.invalidateQueries({ queryKey: ["ai-capabilities"] });
    } finally {
      setSavingCode(null);
    }
  };

  const capabilityColumns: TableColumnsType<AiCapability> = [
    { title: "模块", dataIndex: "module", width: 150 },
    {
      title: "能力",
      dataIndex: "name",
      render: (name: string, row) => (
        <Space direction="vertical" size={0}>
          <Text>{name}</Text>
          <Text type="secondary" style={{ fontSize: 12 }}>
            {row.code}
          </Text>
        </Space>
      ),
    },
    {
      title: "关联提示词",
      dataIndex: "prompt_ref",
      width: 180,
      render: (v: string | null) => (v ? <Tag>{v}</Tag> : <Text type="secondary">默认</Text>),
    },
    {
      title: "模型覆盖",
      dataIndex: "model_override",
      width: 180,
      render: (v: string | null) => v || <Text type="secondary">默认模型</Text>,
    },
    {
      title: "启用",
      dataIndex: "is_enabled",
      width: 90,
      render: (v: boolean, row) => (
        <Switch
          checked={v}
          loading={savingCode === row.code}
          onChange={(checked) => patch(row.code, { is_enabled: checked })}
        />
      ),
    },
    {
      title: "允许人工介入",
      dataIndex: "allow_manual",
      width: 130,
      render: (v: boolean, row) => (
        <Switch
          checked={v}
          loading={savingCode === row.code}
          onChange={(checked) => patch(row.code, { allow_manual: checked })}
        />
      ),
    },
  ];

  const usageColumns: TableColumnsType<CapabilityUsage> = [
    { title: "能力", dataIndex: "capability" },
    { title: "调用数", dataIndex: "calls", width: 100 },
    {
      title: "失败率",
      dataIndex: "failure_rate",
      width: 110,
      render: (v: number) => (
        <Text type={v > 0.1 ? "danger" : undefined}>{(v * 100).toFixed(1)}%</Text>
      ),
    },
    {
      title: "截断数",
      dataIndex: "truncated",
      width: 100,
      render: (v: number) => (v > 0 ? <Text type="warning">{v}</Text> : v),
    },
    {
      title: "平均耗时",
      dataIndex: "avg_duration_ms",
      width: 120,
      render: (v: number | null) => (v === null ? "—" : `${Math.round(v)} ms`),
    },
  ];

  return (
    <>
      <PageHeader
        title="AI 能力管理"
        subtitle="能力注册表与调用统计：哪个模块有什么能力、用哪个模型/提示词、跑得好不好"
      />
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={8}>
          <Card size="small">
            <Statistic title="近 30 天总调用" value={usage?.total_calls ?? 0} loading={usageLoading} />
          </Card>
        </Col>
        <Col span={8}>
          <Card size="small">
            <Statistic title="近 30 天总 token" value={usage?.total_tokens ?? 0} loading={usageLoading} />
          </Card>
        </Col>
        <Col span={8}>
          <Card size="small">
            <Statistic
              title="截断数（静默故障）"
              value={usage?.total_truncated ?? 0}
              loading={usageLoading}
              valueStyle={usage?.total_truncated ? { color: "#d4380d" } : undefined}
            />
          </Card>
        </Col>
      </Row>
      <Card title="能力注册表" size="small" style={{ marginBottom: 16 }}>
        <Table<AiCapability>
          rowKey="code"
          size="small"
          loading={isLoading}
          dataSource={capabilities}
          columns={capabilityColumns}
          pagination={false}
        />
      </Card>
      <Card title="调用统计（近 30 天）" size="small">
        <Table<CapabilityUsage>
          rowKey="capability"
          size="small"
          loading={usageLoading}
          dataSource={usage?.by_capability ?? []}
          columns={usageColumns}
          pagination={false}
        />
      </Card>
    </>
  );
}
