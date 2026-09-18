import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { App as AntApp, Button, Select, Space, Table, Tag, Tooltip, Typography } from "antd";
import type { TableColumnsType } from "antd";
import { PrinterOutlined, PlusOutlined } from "@ant-design/icons";
import { useQuery } from "@tanstack/react-query";
import { PageHeader } from "@/components/common/PageHeader";
import { downloadTicketDocx, listTickets } from "@/services/workTicketService";
import {
  DISABLED_TICKET_TYPES,
  ENABLED_TICKET_TYPES,
  TICKET_STATUS_COLOR,
  TICKET_STATUS_LABEL,
  TICKET_TYPE_LABEL,
  approverFor,
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
      render: (value: string | null, record) =>
        nodeLabel(
          value,
          approverFor(
            record.ticket_type as "DHZY" | "YXKJ",
            record.level,
          ),
        ),
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
          <Select
            allowClear
            placeholder="全部"
            style={{ width: 150 }}
            value={ticketType}
            onChange={setTicketType}
            options={ENABLED_TICKET_TYPES.map((code) => ({
              value: code,
              label: TICKET_TYPE_LABEL[code],
            }))}
          />
          {DISABLED_TICKET_TYPES.map((label) => (
            <Tooltip key={label} title="未启用（计划 9 按模板复制开放）">
              <Tag color="default" style={{ cursor: "not-allowed", color: "#bfbfbf" }}>
                {label}
              </Tag>
            </Tooltip>
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
