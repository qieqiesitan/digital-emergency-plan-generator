import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { App as AntApp, Button, Select, Space, Table, Tag, Typography } from "antd";
import type { TableColumnsType } from "antd";
import { PrinterOutlined, PlusOutlined } from "@ant-design/icons";
import { useQuery } from "@tanstack/react-query";
import { PageHeader } from "@/components/common/PageHeader";
import { downloadTicketDocx, listTemplates, listTickets } from "@/services/workTicketService";
import {
  ALL_TICKET_TYPES,
  TICKET_STATUS_COLOR,
  TICKET_STATUS_LABEL,
  TICKET_TYPE_LABEL,
  nodeLabel,
} from "@/types/workTicket";
import type { WorkTicketInstance } from "@/types/workTicket";

const { Text } = Typography;

/**
 * 作业票列表（**单入口**）。
 *
 * 视觉走查第 1 条的落点：侧边栏不为 8 类票各开一个菜单，进页面后用类型筛选切换；
 * 未启用的 6 类在这里灰显说明，点不动——避免用户以为"这里也能开票"。
 */
export default function WorkTicketListPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { message } = AntApp.useApp();
  const [ticketType, setTicketType] = useState<string | undefined>();
  const [status, setStatus] = useState<string | undefined>();

  const { data, isLoading } = useQuery({
    queryKey: ["work-ticket-tickets", id, ticketType, status],
    queryFn: () =>
      listTickets(id as string, { ticket_type: ticketType, status }),
    enabled: Boolean(id),
  });
  const { data: templates } = useQuery({
    queryKey: ["work-ticket-templates"],
    queryFn: listTemplates,
  });
  const enabledTypes = new Set((templates ?? []).map((t) => t.code));

  const handlePrint = async (record: WorkTicketInstance) => {
    try {
      await downloadTicketDocx(record.id, record.code);
      message.success("已生成票面并固化打印快照");
    } catch (err) {
      message.error((err as Error).message);
    }
  };

  const columns: TableColumnsType<WorkTicketInstance> = [
    { title: "票号", dataIndex: "code", width: 240 },
    {
      title: "类型",
      dataIndex: "ticket_type",
      width: 110,
      render: (value: string) =>
        TICKET_TYPE_LABEL[value as keyof typeof TICKET_TYPE_LABEL] ?? value,
    },
    {
      title: "级别",
      dataIndex: "level",
      width: 80,
      render: (value?: string | null) => value || "—",
    },
    {
      title: "状态",
      dataIndex: "status",
      width: 100,
      render: (value: string) => (
        <Tag color={TICKET_STATUS_COLOR[value] ?? "default"}>
          {TICKET_STATUS_LABEL[value] ?? value}
        </Tag>
      ),
    },
    {
      title: "当前节点",
      dataIndex: "current_node_key",
      width: 180,
      render: (value: string | null) => nodeLabel(value),
    },
    {
      title: "创建时间",
      dataIndex: "created_at",
      width: 170,
      render: (value?: string | null) =>
        value ? new Date(value).toLocaleString("zh-CN") : "—",
    },
    {
      title: "操作",
      width: 150,
      render: (_, record) => (
        <Space size={4}>
          <Button
            type="link"
            size="small"
            onClick={() => navigate(`/enterprises/${id}/work-ticket/${record.id}`)}
          >
            查看
          </Button>
          <Button
            type="link"
            size="small"
            icon={<PrinterOutlined />}
            onClick={() => handlePrint(record)}
          >
            打印
          </Button>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <PageHeader
        title="特殊作业票"
        subtitle="8 类作业票共用这一个入口：先用类型筛选切换，再开票"
        extra={
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => navigate(`/enterprises/${id}/work-ticket/new`)}
          >
            开票
          </Button>
        }
      />

      <Space direction="vertical" style={{ width: "100%" }} size={12}>
        <Space wrap size={8} align="center">
          <Text type="secondary">类型</Text>
          {ALL_TICKET_TYPES.map((t) => (
            <Tag.CheckableTag
              key={t.code}
              checked={ticketType === t.code}
              onChange={() => setTicketType(ticketType === t.code ? undefined : t.code)}
              style={
                enabledTypes.has(t.code)
                  ? undefined
                  : { opacity: 0.45, pointerEvents: "none", cursor: "not-allowed" }
              }
            >
              {t.label}
              {!enabledTypes.has(t.code) && <span style={{ fontSize: 11 }}>（未启用）</span>}
            </Tag.CheckableTag>
          ))}
        </Space>

        <Space wrap size={8} align="center">
          <Text type="secondary">状态</Text>
          <Select
            allowClear
            placeholder="全部"
            style={{ width: 150 }}
            value={status}
            onChange={setStatus}
            options={Object.entries(TICKET_STATUS_LABEL).map(([value, label]) => ({
              value,
              label,
            }))}
          />
        </Space>

        <Table
          rowKey="id"
          size="small"
          loading={isLoading}
          columns={columns}
          dataSource={data ?? []}
          pagination={{ pageSize: 10, showSizeChanger: false }}
        />
      </Space>
    </div>
  );
}
