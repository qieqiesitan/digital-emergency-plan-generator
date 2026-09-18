import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Alert, App as AntApp, Button, Card, Descriptions, Space, Table, Tag, Timeline, Typography } from "antd";
import type { TableColumnsType } from "antd";
import { PrinterOutlined, SendOutlined } from "@ant-design/icons";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import dayjs from "dayjs";
import { PageHeader } from "@/components/common/PageHeader";
import {
  downloadTicketDocx,
  errorDetail,
  getTicketDetail,
  listTemplates,
  submitTicket,
} from "@/services/workTicketService";
import type { GasTestRecord, WorkTicketMeasureDef } from "@/types/workTicket";
import {
  TICKET_STATUS_COLOR,
  TICKET_STATUS_LABEL,
  TICKET_TYPE_LABEL,
  approverFor,
  nodeLabel,
} from "@/types/workTicket";

const { Text } = Typography;

/** 票面值可能是字符串、数组（时间段）或空——统一转成可读文本。 */
function renderValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "—";
  if (Array.isArray(value)) {
    return value
      .map((v) => (dayjs.isDayjs(v) ? v.format("YYYY-MM-DD HH:mm") : String(v)))
      .join(" ~ ");
  }
  if (typeof value === "object") {
    return JSON.stringify(value);
  }
  const text = String(value);
  return dayjs(text).isValid() && /\d{4}-\d{2}-\d{2}T/.test(text)
    ? dayjs(text).format("YYYY-MM-DD HH:mm")
    : text;
}

/**
 * 票面只读视图 + 气体检测 + 措施确认 + 审批记录，并提供「打印票面」。
 *
 * 打印按钮每点一次都会在后端固化一个新版本的快照（version 递增），
 * 因此这里不做"重复打印"确认弹窗——重复打印本身就是审计需要的留痕。
 */
export default function WorkTicketDetailPage() {
  const { id, ticketId } = useParams<{ id: string; ticketId: string }>();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { message } = AntApp.useApp();
  const [submitting, setSubmitting] = useState(false);
  const [problems, setProblems] = useState<string[]>([]);

  const { data, isLoading } = useQuery({
    queryKey: ["work-ticket-detail", ticketId],
    queryFn: () => getTicketDetail(ticketId as string),
    enabled: Boolean(ticketId),
  });

  const { data: templates } = useQuery({
    queryKey: ["work-ticket-templates"],
    queryFn: listTemplates,
  });

  const ticket = data?.ticket;
  const template = templates?.find(
    (t) =>
      t.code === ticket?.ticket_type &&
      (ticket?.ticket_type === "YXKJ" || (t.level ?? null) === ticket?.level),
  );
  const approver = ticket
    ? approverFor(ticket.ticket_type as "DHZY" | "YXKJ", ticket.level)
    : null;
  const confirmedOrders = new Set(
    ((ticket?.values?.confirmed_measures as number[] | undefined) ?? []).map(Number),
  );

  const handlePrint = async () => {
    if (!ticket) return;
    try {
      await downloadTicketDocx(ticket.id, ticket.code);
      message.success("已生成票面并固化打印快照");
    } catch (err) {
      message.error((err as Error).message);
    }
  };

  const handleSubmit = async () => {
    if (!ticket) return;
    setSubmitting(true);
    setProblems([]);
    try {
      const result = await submitTicket(ticket.id);
      message.success(`已提交，当前节点：${result.node ?? "已批准"}`);
      await qc.invalidateQueries({ queryKey: ["work-ticket-detail", ticketId] });
    } catch (err) {
      setProblems(errorDetail(err, "提交失败").split("；").filter(Boolean));
    } finally {
      setSubmitting(false);
    }
  };

  const measureColumns: TableColumnsType<WorkTicketMeasureDef> = [
    { title: "序号", dataIndex: "sort_order", width: 70 },
    { title: "安全措施", dataIndex: "measure_text" },
    { title: "依据条款", dataIndex: "article_anchor", width: 180 },
    {
      title: "是否确认",
      width: 100,
      render: (_, record) =>
        confirmedOrders.has(record.sort_order) ? (
          <Tag color="success">已确认</Tag>
        ) : (
          <Tag>未确认</Tag>
        ),
    },
  ];

  const gasColumns: TableColumnsType<GasTestRecord> = [
    {
      title: "取样时间",
      dataIndex: "sampled_at",
      width: 170,
      render: (v: string) => (v ? dayjs(v).format("YYYY-MM-DD HH:mm") : "—"),
    },
    { title: "地点", dataIndex: "location", render: (v?: string | null) => v || "—" },
    { title: "气体", dataIndex: "gas_type", width: 120, render: (v?: string | null) => v || "—" },
    { title: "结果", dataIndex: "result", width: 120, render: (v?: string | null) => v || "—" },
    { title: "分析人", dataIndex: "tester", width: 100, render: (v?: string | null) => v || "—" },
    { title: "结论", dataIndex: "conclusion", width: 90, render: (v?: string | null) => v || "—" },
  ];

  return (
    <div>
      <PageHeader
        title={ticket?.code ?? "作业票"}
        subtitle={
          ticket
            ? `${TICKET_TYPE_LABEL[ticket.ticket_type as keyof typeof TICKET_TYPE_LABEL] ?? ticket.ticket_type}${
                ticket.level ? ` · ${ticket.level}` : ""
              }`
            : undefined
        }
        onBack={() => navigate(`/enterprises/${id}/work-ticket`)}
        extra={
          <Space>
            {ticket?.status === "draft" && (
              <Button
                type="primary"
                icon={<SendOutlined />}
                loading={submitting}
                onClick={handleSubmit}
              >
                提交审批
              </Button>
            )}
            <Button icon={<PrinterOutlined />} onClick={handlePrint} disabled={!ticket}>
              打印票面
            </Button>
          </Space>
        }
      />

      {problems.length > 0 && (
        <Alert
          type="error"
          showIcon
          style={{ marginBottom: 16 }}
          title="提交前校验未通过"
          description={
            <ul style={{ margin: 0, paddingLeft: 20 }}>
              {problems.map((p) => (
                <li key={p}>{p}</li>
              ))}
            </ul>
          }
        />
      )}

      <Space orientation="vertical" size={16} style={{ width: "100%" }}>
        <Card size="small" loading={isLoading} title="票面">
          <Descriptions column={2} size="small">
            <Descriptions.Item label="状态">
              {ticket && (
                <Tag color={TICKET_STATUS_COLOR[ticket.status] ?? "default"}>
                  {TICKET_STATUS_LABEL[ticket.status] ?? ticket.status}
                </Tag>
              )}
            </Descriptions.Item>
            <Descriptions.Item label="当前节点">
              {nodeLabel(ticket?.current_node_key, approver)}
            </Descriptions.Item>
            {(template?.fields ?? []).map((f) => (
              <Descriptions.Item key={f.field_key} label={f.label}>
                {renderValue(ticket?.values?.[f.field_key])}
              </Descriptions.Item>
            ))}
          </Descriptions>
        </Card>

        <Card size="small" title="气体检测记录">
          {(data?.gas_tests?.length ?? 0) === 0 ? (
            <Text type="secondary">尚未录入气体检测记录。</Text>
          ) : (
            <Table
              rowKey="id"
              size="small"
              pagination={false}
              columns={gasColumns}
              dataSource={data?.gas_tests ?? []}
            />
          )}
        </Card>

        <Card size="small" title="安全措施确认">
          <Table
            rowKey="sort_order"
            size="small"
            pagination={false}
            columns={measureColumns}
            dataSource={template?.measures ?? []}
          />
        </Card>

        <Card size="small" title="审批记录">
          {(data?.node_records?.length ?? 0) === 0 ? (
            <Text type="secondary">尚未产生审批记录。</Text>
          ) : (
            <Timeline
              items={(data?.node_records ?? []).map((r) => ({
                color: r.action === "reject" ? "red" : "green",
                children: (
                  <Space orientation="vertical" size={2}>
                    <Text strong>
                      {nodeLabel(r.node_key, approver)} · {r.action === "approve" ? "同意" : "退回"}
                    </Text>
                    {r.opinion && <Text type="secondary">意见：{r.opinion}</Text>}
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      {r.acted_by ? `${r.acted_by} · ` : ""}
                      {r.created_at ? dayjs(r.created_at).format("YYYY-MM-DD HH:mm") : ""}
                    </Text>
                  </Space>
                ),
              }))}
            />
          )}
        </Card>
      </Space>
    </div>
  );
}
