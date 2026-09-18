import { useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import {
  Alert,
  App as AntApp,
  Button,
  Card,
  Checkbox,
  Col,
  DatePicker,
  Divider,
  Empty,
  Form,
  Input,
  Row,
  Select,
  Space,
  Typography,
} from "antd";
import { useQuery } from "@tanstack/react-query";
import dayjs from "dayjs";
import { PageHeader } from "@/components/common/PageHeader";
import EvidencePanel from "@/components/enterprise/majorHazard/EvidencePanel";
import {
  attachUnitEvidence,
  getUnitRecord,
  listUnitEvidence,
  listUnits,
  upsertUnitRecord,
} from "@/services/majorHazardService";
import type { MajorHazardRecord } from "@/types/majorHazard";

const { Text } = Typography;

/** GB 18218 与本模块直接相关的三条依据，供「一键挂载」。 */
const STANDARD_PRESETS = [
  {
    article_anchor: "GB 18218-2018 4.2.1",
    note: "辨识指标：s = Σqi/Qi >= 1 即构成重大危险源",
  },
  {
    article_anchor: "GB 18218-2018 4.3.2",
    note: "分级指标：R = α × Σβi × (qi/Qi)",
  },
  {
    article_anchor: "GB 18218-2018 表6",
    note: "分级标准：一级 R>=100；二级 50<=R<100；三级 10<=R<50；四级 R<10",
  },
];

/** 备案资料清单（按 GB 18218 配套备案惯例）。 */
const REQUIRED_DOCS = [
  { key: "base", label: "重大危险源基础资料" },
  { key: "area", label: "区域位置图" },
  { key: "plane", label: "平面布置图" },
  { key: "flow", label: "工艺流程图" },
  { key: "equipment", label: "设备一览表" },
  { key: "evaluate", label: "安全评价报告" },
  { key: "assess", label: "安全评估报告" },
  { key: "key", label: "重点部位/关键装置资料" },
  { key: "sign", label: "签字确认材料" },
  { key: "other", label: "其他补充材料" },
];

interface RecordForm {
  hazard_code?: string;
  filing_status: string;
  filing_no?: string;
  filing_date?: dayjs.Dayjs | null;
  chief_name?: string;
  chief_post?: string;
  chief_phone?: string;
  tech_name?: string;
  tech_post?: string;
  tech_phone?: string;
  oper_name?: string;
  oper_post?: string;
  oper_phone?: string;
}

const RESPONSIBLE_GROUPS = [
  ["chief", "主要负责人"],
  ["tech", "技术负责人"],
  ["oper", "操作负责人"],
] as const;

export default function MajorHazardRecordPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [sp, setSp] = useSearchParams();
  const { message } = AntApp.useApp();
  const [form] = Form.useForm<RecordForm>();
  const [docs, setDocs] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);

  const unitId = sp.get("unitId") ?? "";
  const { data: units } = useQuery({
    queryKey: ["major-hazard-units", id],
    queryFn: () => listUnits(id!),
    enabled: !!id,
  });
  const effectiveUnitId = unitId || units?.[0]?.id || "";

  // 后端在"尚未建档"时返回 404，service 已关掉全局 toast，
  // 这里把 404 当正常状态处理而不是错误。
  const { data: record, isError, error } = useQuery<MajorHazardRecord>({
    queryKey: ["major-hazard-record", effectiveUnitId],
    queryFn: () => getUnitRecord(effectiveUnitId),
    enabled: !!effectiveUnitId,
    retry: false,
  });

  const notFound =
    isError && (error as { response?: { status?: number } })?.response?.status === 404;

  // 表单初值从 record 派生；记录未到位时不渲染表单，因此 initialValues 一次生效即可。
  const initial: RecordForm = record
    ? {
        hazard_code: record.hazard_code ?? undefined,
        filing_status: record.filing_status,
        filing_no: record.filing_no ?? undefined,
        filing_date: record.filing_date ? dayjs(record.filing_date) : null,
        chief_name: record.chief_name ?? undefined,
        chief_post: record.chief_post ?? undefined,
        chief_phone: record.chief_phone ?? undefined,
        tech_name: record.tech_name ?? undefined,
        tech_post: record.tech_post ?? undefined,
        tech_phone: record.tech_phone ?? undefined,
        oper_name: record.oper_name ?? undefined,
        oper_post: record.oper_post ?? undefined,
        oper_phone: record.oper_phone ?? undefined,
      }
    : { filing_status: "未备案" };

  const save = async () => {
    const v = await form.validateFields();
    setSaving(true);
    try {
      await upsertUnitRecord(effectiveUnitId, id!, {
        ...v,
        filing_date: v.filing_date ? v.filing_date.format("YYYY-MM-DD") : null,
        completeness: Object.fromEntries(
          REQUIRED_DOCS.map((d) => [d.key, docs.includes(d.key)]),
        ),
      } as Partial<MajorHazardRecord>);
      message.success("档案已保存");
    } finally {
      setSaving(false);
    }
  };

  if (!effectiveUnitId) return <Empty description="请先从台账选择一个单元" />;

  return (
    <>
      <PageHeader
        title="档案与备案"
        subtitle="重大危险源档案、包保责任人与资料完整性"
        extra={
          <Space>
            <Select
              style={{ minWidth: 220 }}
              value={effectiveUnitId}
              onChange={(v) => {
                sp.set("unitId", v);
                setSp(sp, { replace: true });
              }}
              options={(units ?? []).map((u) => ({ value: u.id, label: u.name }))}
            />
            <Button onClick={() => navigate(`/enterprises/${id}/major-hazard`)}>返回台账</Button>
          </Space>
        }
      />

      {notFound && (
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 12 }}
          title="该单元尚未建立档案"
          description="填好下面的信息并保存即可建档。"
        />
      )}

      <Row gutter={16}>
        <Col span={14}>
          <Card
            title="备案信息与包保责任人"
            extra={
              <Button type="primary" loading={saving} onClick={save}>
                保存
              </Button>
            }
          >
            <Form form={form} layout="vertical" initialValues={initial} key={effectiveUnitId}>
              <Row gutter={12}>
                <Col span={8}>
                  <Form.Item name="hazard_code" label="重大危险源编码">
                    <Input placeholder="如 TYKJ001" />
                  </Form.Item>
                </Col>
                <Col span={8}>
                  <Form.Item name="filing_status" label="备案状态">
                    <Select
                      options={[
                        { value: "未备案", label: "未备案" },
                        { value: "已备案", label: "已备案" },
                        { value: "变更中", label: "变更中" },
                      ]}
                    />
                  </Form.Item>
                </Col>
                <Col span={8}>
                  <Form.Item name="filing_no" label="备案号">
                    <Input />
                  </Form.Item>
                </Col>
              </Row>
              <Form.Item name="filing_date" label="备案日期">
                <DatePicker style={{ width: 220 }} />
              </Form.Item>

              <Divider titlePlacement="start" plain>
                包保责任人
              </Divider>
              <Text type="secondary" style={{ fontSize: 12 }}>
                重大危险源需明确主要负责人、技术负责人、操作负责人三级包保责任。
              </Text>
              {RESPONSIBLE_GROUPS.map(([prefix, label]) => (
                <Row gutter={12} key={prefix} style={{ marginTop: 12 }}>
                  <Col span={6}>
                    <Form.Item name={`${prefix}_name`} label={`${label}·姓名`}>
                      <Input />
                    </Form.Item>
                  </Col>
                  <Col span={9}>
                    <Form.Item name={`${prefix}_post`} label="职务">
                      <Input />
                    </Form.Item>
                  </Col>
                  <Col span={9}>
                    <Form.Item name={`${prefix}_phone`} label="联系电话">
                      <Input />
                    </Form.Item>
                  </Col>
                </Row>
              ))}
            </Form>
          </Card>
        </Col>

        <Col span={10}>
          <Card title="资料完整性" style={{ marginBottom: 16 }}>
            <Checkbox.Group
              value={docs}
              onChange={(v) => setDocs(v as string[])}
              style={{ display: "block" }}
            >
              <Space orientation="vertical">
                {REQUIRED_DOCS.map((d) => (
                  <Checkbox key={d.key} value={d.key}>
                    {d.label}
                  </Checkbox>
                ))}
              </Space>
            </Checkbox.Group>
            <Text type="secondary" style={{ fontSize: 12, display: "block", marginTop: 8 }}>
              勾选状态随档案一起保存到 completeness 字段。
            </Text>
          </Card>

          <Card title="法规依据">
            <EvidencePanel
              ownerType="major_hazard_unit"
              ownerId={effectiveUnitId}
              listFn={listUnitEvidence}
              attachFn={attachUnitEvidence}
              presets={STANDARD_PRESETS}
            />
          </Card>
        </Col>
      </Row>
    </>
  );
}
