import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  Alert,
  App as AntApp,
  Button,
  Input,
  Modal,
  Space,
  Switch,
  Table,
  Tag,
  Typography,
} from "antd";
import type { TableColumnsType } from "antd";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { PageHeader } from "@/components/common/PageHeader";
import { actOnNode, errorDetail, listTickets } from "@/services/workTicketService";
import type { WorkTicketInstance } from "@/types/workTicket";
import { TICKET_TYPE_LABEL, approverFor, nodeLabel } from "@/types/workTicket";

const { Text } = Typography;

/**
 * 审批工作台：审批中的票集中在这里办理。
 *
 * 待办口径：默认「只看我的待办」——后端 `assigned_to_me` 按当前节点可签署人
 * （GB 30871-2022 附录B 表B.1 的 `role_code` / `countersign_units`，在组织架构里
 * 按岗位匹配成员）过滤；企业主可关掉开关查看本企业全部审批中的票。
 * 绑定为成员的审批人即便不传该参数，后端也只返回与其有关的票。
 */
export default function WorkTicketApprovalPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { message } = AntApp.useApp();
  const [acting, setActing] = useState<WorkTicketInstance | null>(null);
  const [action, setAction] = useState<"approve" | "reject">("approve");
  const [opinion, setOpinion] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [mineOnly, setMineOnly] = useState(true);

  const { data, isLoading } = useQuery({
    queryKey: ["work-ticket-tickets", id, "approving", mineOnly],
    queryFn: () =>
      listTickets(id as string, { status: "approving", assigned_to_me: mineOnly }),
    enabled: Boolean(id),
  });

  const openDialog = (record: WorkTicketInstance, next: "approve" | "reject") => {
    setActing(record);
    setAction(next);
    setOpinion("");
  };

  const handleConfirm = async () => {
    if (!acting) return;
    setSubmitting(true);
    try {
      const result = await actOnNode(acting.id, {
        action,
        opinion: opinion || undefined,
      });
      if (action === "reject") {
        message.success("已退回，票据状态为已退回");
      } else if (result.status === "approved") {
        message.success("审批完成，票据已批准");
      } else if (typeof result.pending_signs === "number" && result.pending_signs > 0) {
        message.info(`已签署，仍有 ${result.pending_signs} 人待签（会签节点）`);
      } else {
        message.success(`已流转到：${nodeLabel(result.node)}`);
      }
      setActing(null);
      await qc.invalidateQueries({ queryKey: ["work-ticket-tickets", id] });
    } catch (err) {
      message.error(errorDetail(err, "审批操作失败"));
    } finally {
      setSubmitting(false);
    }
  };

  const columns: TableColumnsType<WorkTicketInstance> = [
    { title: "票号", dataIndex: "code" },
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
      title: "当前节点 / 法定审批人",
      width: 220,
      render: (_, record) => (
        <Space size={4}>
          <Tag color="processing">{nodeLabel(record.current_node_key)}</Tag>
          <Text type="secondary">
            {approverFor(record.ticket_type as "DHZY" | "YXKJ", record.level) ?? "未配置"}
          </Text>
        </Space>
      ),
    },
    {
      title: "操作",
      width: 180,
      render: (_, record) => (
        <Space size={4}>
          <Button type="link" size="small" onClick={() => openDialog(record, "approve")}>
            同意
          </Button>
          <Button
            type="link"
            size="small"
            danger
            onClick={() => openDialog(record, "reject")}
          >
            退回
          </Button>
          <Button
            type="link"
            size="small"
            onClick={() => navigate(`/enterprises/${id}/work-ticket/${record.id}`)}
          >
            详情
          </Button>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <PageHeader title="审批工作台" subtitle="本企业审批中的作业票" />

      <Space orientation="vertical" size={12} style={{ width: "100%" }}>
        <Alert
          type="info"
          showIcon
          title="法定审批环节不可跳过"
          description="审批人依据 GB 30871-2022 附录B 表B.1；退回后票据回到已退回状态，需修改后重新提交。"
        />
        <Space size={8}>
          <Switch checked={mineOnly} onChange={setMineOnly} size="small" />
          <Text>只看我的待办</Text>
          <Text type="secondary">
            （关闭后企业主可查看本企业全部审批中的票；审批成员始终只看到与自己有关的票）
          </Text>
        </Space>
        <Table
          rowKey="id"
          size="small"
          loading={isLoading}
          columns={columns}
          dataSource={data ?? []}
          pagination={{ pageSize: 10, showSizeChanger: false }}
          locale={{ emptyText: mineOnly ? "当前没有轮到你审批的作业票" : "暂无审批中的作业票" }}
        />
      </Space>

      <Modal
        open={Boolean(acting)}
        title={action === "approve" ? "同意" : "退回"}
        okText={action === "approve" ? "确认同意" : "确认退回"}
        okButtonProps={{ danger: action === "reject" }}
        confirmLoading={submitting}
        onOk={handleConfirm}
        onCancel={() => setActing(null)}
      >
        <Space orientation="vertical" size={8} style={{ width: "100%" }}>
          <Text>{acting?.code}</Text>
          <Input.TextArea
            rows={3}
            value={opinion}
            onChange={(e) => setOpinion(e.target.value)}
            placeholder="审批意见（可选）"
          />
        </Space>
      </Modal>
    </div>
  );
}
