import { useState } from "react";
import {
  App as AntApp,
  Button,
  Empty,
  Form,
  Input,
  List,
  Modal,
  Select,
  Space,
  Tag,
  Typography,
} from "antd";
import { PlusOutlined } from "@ant-design/icons";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import type { EvidenceItem } from "@/types/majorHazard";

const { Text } = Typography;

interface Props {
  /** 多态归属：如 "major_hazard_unit"。作业票将来也用它，传 "work_ticket"。 */
  ownerType: string;
  ownerId: string;
  /** 查询函数，调用方注入（避免本组件依赖具体 service）。 */
  listFn: (ownerId: string) => Promise<EvidenceItem[]>;
  attachFn: (
    ownerId: string,
    items: Array<{
      article_anchor: string;
      regulation_id?: string;
      relation?: string;
      note?: string;
    }>,
  ) => Promise<{ created: number }>;
  /** 可选：一键挂载的常用条文。 */
  presets?: Array<{ article_anchor: string; relation?: string; note?: string }>;
  title?: string;
}

const RELATIONS = [
  { value: "依据", label: "依据" },
  { value: "引用", label: "引用" },
  { value: "冲突", label: "冲突" },
];

/**
 * 法规依据面板。
 *
 * 做成通用组件而不是写死在重大危险源页里——计划 8 的作业票措施库要用同一套交互
 * （每条安全措施也能点开看 GB 30871 的原文条款）。归属用 ownerType/ownerId 多态标识，
 * 与后端 evidence_refs 表的结构一致。
 */
export default function EvidencePanel({
  ownerType,
  ownerId,
  listFn,
  attachFn,
  presets,
  title = "法规依据",
}: Props) {
  const qc = useQueryClient();
  const { message } = AntApp.useApp();
  const [open, setOpen] = useState(false);
  const [form] = Form.useForm<{
    article_anchor: string;
    regulation_id?: string;
    relation: string;
    note?: string;
  }>();

  const queryKey = ["evidence", ownerType, ownerId];
  const { data, isLoading } = useQuery({
    queryKey,
    queryFn: () => listFn(ownerId),
    enabled: !!ownerId,
  });

  const attach = async (items: Parameters<typeof attachFn>[1]) => {
    const res = await attachFn(ownerId, items);
    if (res.created === 0) {
      message.info("该依据已存在，未重复添加");
    } else {
      message.success(`已添加 ${res.created} 条依据`);
    }
    qc.invalidateQueries({ queryKey });
  };

  const submit = async () => {
    const v = await form.validateFields();
    await attach([
      {
        article_anchor: v.article_anchor.trim(),
        regulation_id: v.regulation_id?.trim() || undefined,
        relation: v.relation,
        note: v.note?.trim() || undefined,
      },
    ]);
    setOpen(false);
    form.resetFields();
  };

  return (
    <div>
      <Space style={{ marginBottom: 8 }}>
        <Button
          type="primary"
          size="small"
          icon={<PlusOutlined />}
          onClick={() => setOpen(true)}
        >
          添加依据
        </Button>
        {presets?.length ? (
          <Button
            size="small"
            onClick={() =>
              attach(
                presets.map((p) => ({
                  article_anchor: p.article_anchor,
                  relation: p.relation ?? "依据",
                  note: p.note,
                })),
              )
            }
          >
            一键挂载标准依据（{presets.length} 条）
          </Button>
        ) : null}
      </Space>

      {!isLoading && !data?.length ? (
        <Empty description={`尚无${title}`} image={Empty.PRESENTED_IMAGE_SIMPLE} />
      ) : (
        <List
          size="small"
          loading={isLoading}
          dataSource={data ?? []}
          renderItem={(e) => (
            <List.Item>
              <Space orientation="vertical" size={0}>
                <Space>
                  <Text strong>{e.article_anchor}</Text>
                  <Tag color={e.relation === "冲突" ? "red" : "blue"}>{e.relation}</Tag>
                </Space>
                {e.note ? <Text type="secondary">{e.note}</Text> : null}
              </Space>
            </List.Item>
          )}
        />
      )}

      <Modal
        open={open}
        title="添加法规依据"
        onCancel={() => setOpen(false)}
        onOk={submit}
        destroyOnHidden
      >
        <Form form={form} layout="vertical" initialValues={{ relation: "依据" }}>
          <Form.Item
            name="article_anchor"
            label="条文锚点"
            rules={[{ required: true, message: "请填写条文锚点" }]}
            extra="格式：标准号 + 条款号，例如 GB 18218-2018 4.2.1"
          >
            <Input placeholder="GB 18218-2018 4.2.1" />
          </Form.Item>
          <Form.Item name="regulation_id" label="法规 id（可选）">
            <Input placeholder="留空则只按锚点记录" />
          </Form.Item>
          <Form.Item name="relation" label="关系">
            <Select options={RELATIONS} />
          </Form.Item>
          <Form.Item name="note" label="备注（可选）">
            <Input.TextArea rows={2} placeholder="说明为什么引用这条" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
