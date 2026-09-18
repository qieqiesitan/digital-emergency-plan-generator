import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Alert, App as AntApp, Button, Input, Modal, Space, Table, Tag, Typography } from "antd";
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
 * 待办范围目前是"本企业全部审批中的票"：法定审批人（GB 30871-2022 附录B 表B.1）
 * 落在 `work_ticket_flow_nodes.role_code` 上，而系统角色表里还没有这几个角色码，
 * 后端也没有"我的待办"接口，所以这里先按企业 + 审批中筛选，并把每张票的
 * 法定审批人显示出来。按角色收窄待办需要后端补接口（见本任务汇报的遗留项）。
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

  const { data, isLoading } = useQuery({
    queryKey: ["work-ticket-tickets", id, "approving"],
    queryFn: () => listTickets(id as string, { status: "approving" }),
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
      await qc.invalidateQueries({ queryKey: ["work-ticket-tickets", id, "approving"] });
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

      <Space direction="vertical" size={12} style={{ width: "100%" }}>
        <Alert
          type="info"
          showIcon
          message="法定审批环节不可跳过"
          description="审批人依据 GB 30871-2022 附录B 表B.1；退回后票据回到已退回状态，需修改后重新提交。"
        />
        <Table
          rowKey="id"
          size="small"
          loading={isLoading}
          columns={columns}
          dataSource={data ?? []}
          pagination={{ pageSize: 10, showSizeChanger: false }}
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
        <Space direction="vertical" size={8} style={{ width: "100%" }}>
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
