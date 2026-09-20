import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  Alert,
  App as AntApp,
  Button,
  Card,
  Collapse,
  Descriptions,
  Form,
  Input,
  List,
  Modal,
  Space,
  Tag,
  Typography,
} from "antd";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import GasTestTable from "@/components/enterprise/workTicket/GasTestTable";
import { PageHeader } from "@/components/common/PageHeader";
import {
  addPackageGasTest,
  errorDetail,
  getBatchDetail,
  submitBatchAll,
  transitionBatch,
  updateBatch,
} from "@/services/workTicketService";
import type { BatchSubmitAllResult, GasTestPayload } from "@/types/workTicket";
import { TICKET_STATUS_COLOR, TICKET_STATUS_LABEL } from "@/types/workTicket";

const { Text } = Typography;

/**
 * 作业包工作台：共享信息一次填写 → 逐票补齐专有字段 → 逐票或批量提交。
 *
 * 页面刻意不做"一键批准"：批量提交只是逐张票调用各自的提交门禁，
 * 失败票单独列出，不影响其他票。
 */
export default function WorkTicketBatchWorkspacePage() {
  const { id, batchId } = useParams<{ id: string; batchId: string }>();
  const navigate = useNavigate();
  const { message } = AntApp.useApp();
  const queryClient = useQueryClient();
  const [form] = Form.useForm();
  const [gasTests, setGasTests] = useState<GasTestPayload[]>([]);
  const [submitResult, setSubmitResult] = useState<BatchSubmitAllResult | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["work-ticket-batch", batchId],
    queryFn: () => getBatchDetail(batchId as string),
    enabled: Boolean(batchId),
  });

  const batch = data?.batch;
  const tickets = data?.tickets ?? [];
  const draftCount = tickets.filter((t) => t.status === "draft").length;

  const saveShared = useMutation({
    mutationFn: (values: Record<string, string>) =>
      updateBatch(batchId as string, {
        title: values.title,
        shared_values: {
          applicant_unit: values.applicant_unit || null,
          work_unit: values.work_unit || null,
          work_leader: values.work_leader || null,
        },
        content_base: values.content_base || null,
        risk_basis: values.risk_basis || null,
      }),
    onSuccess: (result) => {
      message.success(`已更新共享信息，回写 ${result.affected} 张未提交票`);
      queryClient.invalidateQueries({ queryKey: ["work-ticket-batch", batchId] });
    },
    onError: (err) => message.error(errorDetail(err, "更新失败")),
  });

  const saveGasTests = async () => {
    if (!batchId || gasTests.length === 0) return;
    try {
      for (const gas of gasTests) {
        await addPackageGasTest(batchId, gas);
      }
      setGasTests([]);
      message.success("包级检测已保存，同包的动火/受限空间票会共享读取");
      queryClient.invalidateQueries({ queryKey: ["work-ticket-batch", batchId] });
    } catch (err) {
      message.error(errorDetail(err, "检测记录保存失败"));
    }
  };

  const submitAll = async () => {
    if (!batchId) return;
    try {
      const result = await submitBatchAll(batchId);
      setSubmitResult(result);
      queryClient.invalidateQueries({ queryKey: ["work-ticket-batch", batchId] });
      if (result.results.every((r) => r.ok)) {
        message.success(`${result.succeeded} 张票已全部提交`);
      } else {
        message.warning(`已提交 ${result.succeeded} 张，其余未通过校验`);
      }
    } catch (err) {
      message.error(errorDetail(err, "批量提交失败"));
    }
  };

  const closeBatch = async () => {
    if (!batchId) return;
    try {
      await transitionBatch(batchId, "close");
      message.success("作业包已关闭");
      queryClient.invalidateQueries({ queryKey: ["work-ticket-batch", batchId] });
    } catch (err) {
      message.error(errorDetail(err, "关闭失败"));
    }
  };

  return (
    <div>
      <PageHeader
        title={batch?.title ?? "作业包"}
        subtitle="共享信息一次填写；每张票仍走各自的审批流程与提交门禁"
        onBack={() => navigate(`/enterprises/${id}/work-ticket`)}
      />

      {batch && (
        <Card size="small" loading={isLoading} style={{ marginBottom: 16 }}>
          <Descriptions size="small" column={2}>
            <Descriptions.Item label="状态">
              <Tag>{batch.status}</Tag>
            </Descriptions.Item>
            <Descriptions.Item label="作业地点">{batch.location_text || "—"}</Descriptions.Item>
            <Descriptions.Item label="作业时段">
              {batch.work_period_start && batch.work_period_end
                ? `${batch.work_period_start.slice(0, 16).replace("T", " ")} ~ ${batch.work_period_end
                    .slice(0, 16)
                    .replace("T", " ")}`
                : "—"}
            </Descriptions.Item>
            <Descriptions.Item label="票据">{`${tickets.length} 张（草稿 ${draftCount} 张）`}</Descriptions.Item>
          </Descriptions>
          <Collapse
            ghost
            items={[
              {
                key: "edit",
                label: "编辑共享信息（只回写未提交的票）",
                children: (
                  <Form
                    form={form}
                    layout="vertical"
                    initialValues={{
                      title: batch.title,
                      applicant_unit: batch.shared_values?.applicant_unit ?? "",
                      work_unit: batch.shared_values?.work_unit ?? "",
                      work_leader: batch.shared_values?.work_leader ?? "",
                      content_base: batch.content_base ?? "",
                      risk_basis: batch.risk_basis ?? "",
                    }}
                    onFinish={(values) => saveShared.mutate(values)}
                  >
                    <Form.Item name="title" label="任务名称" rules={[{ required: true }]}>
                      <Input />
                    </Form.Item>
                    <Space wrap>
                      <Form.Item name="applicant_unit" label="申请单位">
                        <Input style={{ width: 220 }} />
                      </Form.Item>
                      <Form.Item name="work_unit" label="作业单位">
                        <Input style={{ width: 180 }} />
                      </Form.Item>
                      <Form.Item name="work_leader" label="负责人">
                        <Input style={{ width: 140 }} />
                      </Form.Item>
                    </Space>
                    <Form.Item name="content_base" label="任务描述">
                      <Input.TextArea rows={2} />
                    </Form.Item>
                    <Form.Item name="risk_basis" label="风险辨识基础">
                      <Input.TextArea rows={2} />
                    </Form.Item>
                    <Button type="primary" htmlType="submit" loading={saveShared.isPending}>
                      保存共享信息
                    </Button>
                  </Form>
                ),
              },
            ]}
          />
        </Card>
      )}

      <Card size="small" title="作业票" style={{ marginBottom: 16 }}>
        <List
          dataSource={tickets}
          renderItem={(ticket) => (
            <List.Item
              actions={[
                <Button
                  key="open"
                  size="small"
                  type={ticket.status === "draft" ? "primary" : "default"}
                  onClick={() => navigate(`/enterprises/${id}/work-ticket/${ticket.id}`)}
                >
                  {ticket.status === "draft" ? "继续填写" : "查看"}
                </Button>,
              ]}
            >
              <List.Item.Meta
                title={
                  <Space>
                    <Text strong>{ticket.code}</Text>
                    <Tag color={TICKET_STATUS_COLOR[ticket.status] ?? "default"}>
                      {TICKET_STATUS_LABEL[ticket.status] ?? ticket.status}
                    </Tag>
                    {ticket.level && <Tag>{ticket.level}</Tag>}
                  </Space>
                }
                description={
                  <Space size={16} wrap>
                    <Text type="secondary">
                      关联票号：{(ticket.values?.related_tickets as string) || "—"}
                    </Text>
                    <Text type="secondary">
                      风险辨识：{((ticket.values?.risk_identification as string) || "—").slice(0, 30)}
                    </Text>
                  </Space>
                }
              />
            </List.Item>
          )}
        />
      </Card>

      <Card
        size="small"
        title="包级气体检测（同包的动火/受限空间票共享读取）"
        style={{ marginBottom: 16 }}
      >
        <Alert
          type="warning"
          showIcon
          style={{ marginBottom: 8 }}
          title="不豁免 30 分钟时效"
          description="包级记录与票级记录走同一条时效判定：作业前统一检测一轮后应尽快提交相关票。"
        />
        <GasTestTable records={gasTests} onChange={setGasTests} />
        <Button
          style={{ marginTop: 8 }}
          disabled={gasTests.length === 0}
          onClick={saveGasTests}
        >
          保存包级检测
        </Button>
        {(data?.package_gas_tests?.length ?? 0) > 0 && (
          <div style={{ marginTop: 8 }}>
            <Text type="secondary">
              已录入 {data?.package_gas_tests.length} 条包级检测记录
            </Text>
          </div>
        )}
      </Card>

      <Space>
        <Button type="primary" onClick={submitAll} disabled={draftCount === 0}>
          批量提交草稿票（{draftCount} 张）
        </Button>
        <Button onClick={closeBatch}>关闭作业包</Button>
      </Space>

      <Modal
        open={submitResult !== null}
        title="批量提交结果"
        footer={<Button onClick={() => setSubmitResult(null)}>关闭</Button>}
        onCancel={() => setSubmitResult(null)}
      >
        <List
          dataSource={submitResult?.results ?? []}
          renderItem={(row) => (
            <List.Item>
              <Space orientation="vertical" size={2} style={{ width: "100%" }}>
                <Space>
                  <Text strong>{row.code}</Text>
                  {row.ok ? <Tag color="success">已提交</Tag> : <Tag color="error">未通过</Tag>}
                </Space>
                {row.errors.length > 0 && (
                  <Text type="secondary">{row.errors.join("；")}</Text>
                )}
              </Space>
            </List.Item>
          )}
        />
      </Modal>
    </div>
  );
}
