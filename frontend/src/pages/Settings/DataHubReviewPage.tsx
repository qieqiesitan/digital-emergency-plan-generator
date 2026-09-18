import { useState } from "react";
import type { Key } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { App as AntApp, Button, Card, Empty, Space, Table, Tag, Typography } from "antd";
import type { TableColumnsType } from "antd";
import { ArrowLeftOutlined, CheckOutlined, StopOutlined } from "@ant-design/icons";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { PageHeader } from "@/components/common/PageHeader";
import { confirmItems, listItems, skipItems } from "@/services/ingestService";
import type { IngestItem } from "@/types/ingest";
import { CONFIDENCE_LABELS, describePayload } from "@/utils/ingestPayload";

const { Text } = Typography;

const CONFIDENCE_COLOR: Record<string, string> = {
  high: "green",
  medium: "gold",
  low: "red",
};

/**
 * 待确认队列（DataHub 的核心页面）。
 *
 * 交互红线（来自视觉走查确认）：
 * - 整批默认全选 + 勾掉错的；
 * - 低置信度默认**不勾**，并在行内注明原因；
 * - 不做"高置信度自动入库"——无确认不入正式表。
 */
export default function DataHubReviewPage() {
  const { jobId = "" } = useParams<{ jobId: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { message } = AntApp.useApp();
  const [overrides, setOverrides] = useState<Record<string, boolean>>({});
  const [submitting, setSubmitting] = useState(false);

  const { data: items = [], isLoading } = useQuery({
    queryKey: ["ingest-items", jobId],
    queryFn: () => listItems(jobId, "pending"),
    enabled: !!jobId,
  });

  // 勾选状态 = 用户覆盖值 ?? 后端建议值（低置信度默认不勾）。
  // 刻意不用 effect 同步：刷新列表后旧条目的覆盖值自然失效，不会残留错勾。
  const isChecked = (item: IngestItem) => overrides[item.id] ?? item.default_checked;
  const checkedIds = items.filter(isChecked).map((i) => i.id);
  const defaultCheckedCount = items.filter((i) => i.default_checked).length;
  const lowCount = items.filter((i) => i.confidence === "low").length;

  const setAll = (value: boolean) =>
    setOverrides(Object.fromEntries(items.map((i) => [i.id, value])));

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["ingest-items", jobId] });
    queryClient.invalidateQueries({ queryKey: ["ingest-jobs"] });
  };

  const handleConfirm = async () => {
    setSubmitting(true);
    try {
      const out = await confirmItems(checkedIds);
      if (out.confirmed > 0) {
        message.success(`已入库 ${out.confirmed} 条`);
      }
      if (out.failed.length) {
        const reasons = Array.from(new Set(out.failed.map((f) => f.reason)));
        message.warning(
          `有 ${out.failed.length} 条入库失败：${reasons.slice(0, 3).join("；")}`,
        );
      }
      setOverrides({});
      refresh();
    } finally {
      setSubmitting(false);
    }
  };

  const handleSkip = async () => {
    setSubmitting(true);
    try {
      const out = await skipItems(checkedIds);
      message.success(`已跳过 ${out.skipped} 条（数据保留，可在数据源历史中追溯）`);
      setOverrides({});
      refresh();
    } finally {
      setSubmitting(false);
    }
  };

  const columns: TableColumnsType<IngestItem> = [
    { title: "目标实体", dataIndex: "target_entity", width: 220 },
    {
      title: "抽取内容",
      dataIndex: "raw_payload",
      render: (payload: Record<string, unknown>) => describePayload(payload),
    },
    {
      title: "来源定位",
      dataIndex: "source_locator",
      width: 220,
      render: (v: string | null, row) => (
        <Space orientation="vertical" size={0}>
          <Text>{v || "—"}</Text>
          {row.confidence === "low" && (
            <Text type="danger" style={{ fontSize: 12 }}>
              {row.review_note || "置信度低，请核对原文后再决定是否入库"}
            </Text>
          )}
        </Space>
      ),
    },
    {
      title: "置信度",
      dataIndex: "confidence",
      width: 100,
      render: (v: string) => (
        <Tag color={CONFIDENCE_COLOR[v] ?? "default"}>{CONFIDENCE_LABELS[v] ?? v}</Tag>
      ),
    },
  ];

  const rowSelection = {
    selectedRowKeys: checkedIds,
    onChange: (keys: Key[]) => {
      const next: Record<string, boolean> = {};
      for (const item of items) next[item.id] = keys.includes(item.id);
      setOverrides(next);
    },
  };

  return (
    <>
      <PageHeader
        title="待确认队列"
        subtitle="确认后才写入业务台账；低置信度条目默认不勾选"
        extra={
          <Button icon={<ArrowLeftOutlined />} onClick={() => navigate("/settings/data-hub")}>
            返回数据接入
          </Button>
        }
      />
      <Card>
        {items.length === 0 && !isLoading ? (
          <Empty description="该批次没有待确认条目" />
        ) : (
          <>
            <Space split="｜" style={{ marginBottom: 12 }} wrap>
              <Text>抽取 {items.length} 条</Text>
              <Text>默认选中 {defaultCheckedCount} 条</Text>
              <Text type={lowCount ? "danger" : "secondary"}>
                低置信度 {lowCount} 条（默认不勾）
              </Text>
            </Space>
            <Table<IngestItem>
              rowKey="id"
              size="small"
              loading={isLoading}
              dataSource={items}
              columns={columns}
              rowSelection={rowSelection}
              pagination={false}
              onRow={(record) => ({
                style: record.confidence === "low" ? { background: "#fff1f0" } : undefined,
              })}
              expandable={{
                expandedRowRender: (record) => (
                  <pre style={{ margin: 0, fontSize: 12, whiteSpace: "pre-wrap" }}>
                    {JSON.stringify(record.raw_payload, null, 2)}
                  </pre>
                ),
              }}
            />
            <div
              style={{
                marginTop: 16,
                display: "flex",
                justifyContent: "space-between",
                flexWrap: "wrap",
                gap: 8,
              }}
            >
              <Space>
                <Button onClick={() => setAll(true)}>全选</Button>
                <Button onClick={() => setAll(false)}>全不选</Button>
              </Space>
              <Space>
                <Button
                  danger
                  icon={<StopOutlined />}
                  disabled={!checkedIds.length}
                  loading={submitting}
                  onClick={handleSkip}
                >
                  跳过选中
                </Button>
                <Button
                  type="primary"
                  icon={<CheckOutlined />}
                  disabled={!checkedIds.length}
                  loading={submitting}
                  onClick={handleConfirm}
                >
                  确认入库（{checkedIds.length} 条）
                </Button>
              </Space>
            </div>
          </>
        )}
      </Card>
    </>
  );
}
