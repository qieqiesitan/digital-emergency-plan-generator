import { useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  Alert,
  App as AntApp,
  Button,
  Checkbox,
  DatePicker,
  Divider,
  Form,
  Input,
  Radio,
  Select,
  Space,
  Steps,
  Tag,
  Typography,
} from "antd";
import { useQuery } from "@tanstack/react-query";
import dayjs from "dayjs";
import GasTestTable from "@/components/enterprise/workTicket/GasTestTable";
import { PageHeader } from "@/components/common/PageHeader";
import { getEnterprise } from "@/services/enterpriseService";
import { addGasTest, errorDetail, listTemplates, openTicket, submitTicket } from "@/services/workTicketService";
import type {
  GasTestPayload,
  WorkTicketFieldDef,
  WorkTicketFlowNodeDef,
  WorkTicketTemplate,
  WorkTicketTypeCode,
} from "@/types/workTicket";
import { ALL_TICKET_TYPES, GAS_TEST_REQUIRED_TYPES } from "@/types/workTicket";

const { Text } = Typography;

const STEPS = [
  { title: "类型与级别" },
  { title: "票面内容" },
  { title: "气体检测" },
  { title: "安全措施" },
  { title: "JSA" },
  { title: "人员与提交" },
];

/** datetime/datetimerange 字段在表单里是 dayjs 对象，落库前统一转 ISO 字符串。 */
function normalizeValues(
  fields: WorkTicketFieldDef[],
  raw: Record<string, unknown>,
): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const f of fields) {
    const value = raw[f.field_key];
    if (value === undefined || value === null || value === "") continue;
    if (f.field_type === "datetime" && dayjs.isDayjs(value)) {
      out[f.field_key] = value.toISOString();
    } else if (f.field_type === "datetimerange" && Array.isArray(value) && value.length === 2) {
      const [start, end] = value as [dayjs.Dayjs, dayjs.Dayjs];
      out[f.field_key] = [start.toISOString(), end.toISOString()];
    } else {
      out[f.field_key] = value;
    }
  }
  return out;
}

function flowPreview(nodes: WorkTicketFlowNodeDef[]) {
  const chain = nodes.map((n) => n.name).filter(Boolean).join(" → ");
  const countersign = nodes
    .filter((n) => (n.countersign_units?.length ?? 0) > 0)
    .map((n) => `本票需${(n.countersign_units ?? []).join("、")}会签后审批`)
    .join("；");
  return { chain, countersign };
}

/**
 * 开票向导（6 步）。
 *
 * 顺序刻意是"先选级别、最后才提交"：级别决定法定审批人，用户在第 1 步就能看到
 * "这张票要经过谁"，而不是提交后才发现走错了级别。
 *
 * 提交前的本地检查只是提前把话说明白（问题清单逻辑与后端 `validate_before_submit`
 * 同一条规则）；真正的门禁在后端，前端绕过不影响阻断。
 */
export default function WorkTicketNewPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { message } = AntApp.useApp();

  const [step, setStep] = useState(0);
  const [ticketType, setTicketType] = useState<WorkTicketTypeCode>("DHZY");
  const [level, setLevel] = useState<string>("");
  const [form] = Form.useForm();
  const [gasTests, setGasTests] = useState<GasTestPayload[]>([]);
  const [confirmed, setConfirmed] = useState<number[]>([]);
  const [jsa, setJsa] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [problems, setProblems] = useState<string[]>([]);

  const { data: enterprise } = useQuery({
    queryKey: ["enterprise", id],
    queryFn: () => getEnterprise(id as string),
    enabled: Boolean(id),
  });

  const { data: templates } = useQuery({
    queryKey: ["work-ticket-templates"],
    queryFn: listTemplates,
  });

  const enabledTypes = useMemo(() => {
    const codes = new Set((templates ?? []).map((t) => t.code));
    return ALL_TICKET_TYPES.filter((t) => codes.has(t.code));
  }, [templates]);

  const activeTicketType = enabledTypes.some((t) => t.code === ticketType)
    ? ticketType
    : enabledTypes[0]?.code;

  const levelsForType = useMemo(() => {
    if (!activeTicketType) return [];
    return Array.from(
      new Set(
        (templates ?? [])
          .filter((t) => t.code === activeTicketType && t.level)
          .map((t) => t.level as string),
      ),
    );
  }, [templates, activeTicketType]);

  const activeLevel = levelsForType.includes(level) ? level : levelsForType[0] ?? "";

  const template: WorkTicketTemplate | undefined = useMemo(() => {
    if (!templates || !activeTicketType) return undefined;
    const candidates = templates.filter((t) => t.code === activeTicketType);
    if (levelsForType.length > 0) {
      return candidates.find((t) => (t.level ?? null) === activeLevel);
    }
    return candidates.find((t) => !t.level) ?? candidates[0];
  }, [templates, activeTicketType, activeLevel, levelsForType]);

  const enterpriseCode = (enterprise?.credit_code || id || "").slice(0, 20);
  const { chain: flowChain, countersign: countersignHint } = flowPreview(
    template?.flow_nodes ?? [],
  );
  const requiresGasTest = activeTicketType
    ? GAS_TEST_REQUIRED_TYPES.includes(activeTicketType)
    : false;

  const requiredFields = (template?.fields ?? []).filter((f) => f.is_required);
  const mandatoryMeasures = template?.measures ?? [];

  /** 与后端 validate_before_submit 同一条规则，提前把问题说清楚。 */
  const localPrecheck = (): string[] => {
    const errs: string[] = [];
    const raw = (form.getFieldsValue() ?? {}) as Record<string, unknown>;
    for (const f of requiredFields) {
      const value = raw[f.field_key];
      if (value === undefined || value === null || value === "") {
        errs.push(`必填项「${f.label}」尚未填写`);
      }
    }
    const missing = mandatoryMeasures.filter((m) => !confirmed.includes(m.sort_order));
    if (missing.length > 0) {
      errs.push(`还有 ${missing.length} 条安全措施未确认（如「${missing[0].measure_text.slice(0, 20)}…」）`);
    }
    if (requiresGasTest) {
      if (gasTests.length === 0) {
        errs.push("动火/受限空间作业必须至少录入一次气体检测记录");
      } else {
        const latest = gasTests
          .map((g) => dayjs(g.sampled_at))
          .sort((a, b) => b.valueOf() - a.valueOf())[0];
        if (dayjs().diff(latest, "minute") > 30) {
          errs.push("气体检测取样时间已超过 30 分钟，请重新检测后再提交");
        }
      }
    }
    return errs;
  };

  const handleSubmit = async () => {
    if (!id) return;
    if (!activeTicketType) {
      message.error("未找到已启用的作业票模板，请检查模板种子数据");
      return;
    }
    if (!template) {
      message.error("未找到对应模板，请检查种子数据是否已导入");
      return;
    }
    const errs = localPrecheck();
    setProblems(errs);
    if (errs.length > 0) {
      message.warning("提交前校验未通过，请按清单逐条处理");
      return;
    }
    setSubmitting(true);
    try {
      const values = {
        ...normalizeValues(template.fields, form.getFieldsValue()),
        confirmed_measures: confirmed,
        jsa: jsa || null,
      };
      const instance = await openTicket({
        enterprise_id: id,
        enterprise_code: enterpriseCode,
        ticket_type: activeTicketType,
        template_id: template.id,
        level: levelsForType.length > 0 ? activeLevel : null,
        values,
      });
      for (const gas of gasTests) {
        await addGasTest(instance.id, gas);
      }
      try {
        const result = await submitTicket(instance.id);
        message.success(`已提交，当前节点：${result.node ?? "已批准"}`);
      } catch (err) {
        setProblems(errorDetail(err, "提交失败").split("；").filter(Boolean));
        message.error("提交未通过后端校验，已生成草稿票");
      }
      navigate(`/enterprises/${id}/work-ticket/${instance.id}`);
    } catch (err) {
      message.error(errorDetail(err, "开票失败"));
    } finally {
      setSubmitting(false);
    }
  };

  const renderField = (field: WorkTicketFieldDef) => {
    if (field.field_type === "textarea") {
      return <Input.TextArea rows={3} placeholder={field.label} />;
    }
    if (field.field_type === "select") {
      return (
        <Select
          placeholder={field.label}
          options={(field.options?.choices ?? []).map((c) => ({ value: c, label: c }))}
        />
      );
    }
    if (field.field_type === "datetime") {
      return <DatePicker showTime format="YYYY-MM-DD HH:mm" style={{ width: "100%" }} />;
    }
    if (field.field_type === "datetimerange") {
      return <DatePicker.RangePicker showTime format="YYYY-MM-DD HH:mm" />;
    }
    return <Input placeholder={field.label} />;
  };

  const groupedFields = (template?.fields ?? []).reduce<Record<string, WorkTicketFieldDef[]>>(
    (acc, f) => {
      const key = f.group_name || "其他";
      acc[key] = acc[key] ? [...acc[key], f] : [f];
      return acc;
    },
    {},
  );

  return (
    <div>
      <PageHeader
        title="开票"
        subtitle="按 GB 30871-2022 附录A 票面填报；级别决定法定审批人"
        onBack={() => navigate(`/enterprises/${id}/work-ticket`)}
      />

      <Steps current={step} size="small" items={STEPS} style={{ marginBottom: 24 }} />

      {step === 0 && (
        <Space orientation="vertical" size={16} style={{ width: "100%" }}>
          <div>
            <Text strong>作业类型</Text>
            <div style={{ marginTop: 8 }}>
              <Radio.Group
                value={activeTicketType}
                onChange={(e) => {
                  const next = e.target.value as WorkTicketTypeCode;
                  setTicketType(next);
                  setConfirmed([]);
                  setProblems([]);
                  const nextLevels = Array.from(
                    new Set(
                      (templates ?? [])
                        .filter((t) => t.code === next && t.level)
                        .map((t) => t.level as string),
                    ),
                  );
                  setLevel(nextLevels[0] ?? "");
                }}
                options={enabledTypes.map((t) => ({
                  value: t.code,
                  label: t.label,
                }))}
                optionType="button"
              />
            </div>
          </div>
          {levelsForType.length > 0 && (
            <div>
              <Text strong>作业级别</Text>
              <div style={{ marginTop: 8 }}>
                <Radio.Group
                  value={activeLevel}
                  onChange={(e) => setLevel(e.target.value as string)}
                  options={levelsForType.map((l) => ({ value: l, label: l }))}
                  optionType="button"
                />
              </div>
            </div>
          )}
          <Alert
            type={flowChain ? "info" : "warning"}
            showIcon
            title={
              flowChain
                ? `审批流程：${flowChain}`
                : "未找到该类型的审批流程配置，请检查模板种子数据"
            }
            description={
              countersignHint
                ? `${countersignHint}。审批人依据 GB 30871-2022 附录B 表B.1；法定环节不提供跳过入口。`
                : "审批人依据 GB 30871-2022 附录B 表B.1；法定环节不提供跳过入口。"
            }
          />
        </Space>
      )}

      {step === 1 && (
        <Form form={form} layout="vertical">
          {Object.entries(groupedFields).map(([group, fields]) => (
            <div key={group}>
              <Divider titlePlacement="left">{group}</Divider>
              {fields.map((field) => (
                <Form.Item
                  key={field.field_key}
                  name={field.field_key}
                  label={field.label}
                  rules={
                    field.is_required
                      ? [{ required: true, message: `请填写${field.label}` }]
                      : undefined
                  }
                >
                  {renderField(field)}
                </Form.Item>
              ))}
            </div>
          ))}
        </Form>
      )}

      {step === 2 && (
        <Space orientation="vertical" size={12} style={{ width: "100%" }}>
          <Alert
            type={requiresGasTest ? "info" : "success"}
            showIcon
            title={
              requiresGasTest
                ? "本类型为法定强制气体检测"
                : "本类型不强制气体检测"
            }
            description={
              requiresGasTest
                ? "动火与受限空间作业提交前至少需要一条 30 分钟内的有效检测记录。"
                : "可选填；若现场需要检测，仍可在这里记录。"
            }
          />
          <GasTestTable records={gasTests} onChange={setGasTests} />
        </Space>
      )}

      {step === 3 && (
        <Space orientation="vertical" size={8} style={{ width: "100%" }}>
          <Space>
            <Button
              size="small"
              onClick={() => setConfirmed(mandatoryMeasures.map((m) => m.sort_order))}
            >
              全部确认
            </Button>
            <Text type="secondary">
              已确认 {confirmed.length} / {mandatoryMeasures.length} 条
            </Text>
          </Space>
          {mandatoryMeasures.map((m) => (
            <Checkbox
              key={m.sort_order}
              checked={confirmed.includes(m.sort_order)}
              onChange={(e) =>
                setConfirmed((prev) =>
                  e.target.checked
                    ? [...prev, m.sort_order]
                    : prev.filter((o) => o !== m.sort_order),
                )
              }
            >
              <Text>{m.measure_text}</Text>{" "}
              <Tag color="blue">{m.article_anchor}</Tag>
            </Checkbox>
          ))}
        </Space>
      )}

      {step === 4 && (
        <Space orientation="vertical" size={8} style={{ width: "100%" }}>
          <Text type="secondary">
            JSA（作业危害分析）由 AI 能力生成，本计划未接入；留空可以直接跳过，不影响开票。
          </Text>
          <Input.TextArea
            rows={6}
            value={jsa}
            onChange={(e) => setJsa(e.target.value)}
            placeholder="可选：填写本次作业的危害分析与控制措施"
          />
        </Space>
      )}

      {step === 5 && (
        <Space orientation="vertical" size={12} style={{ width: "100%" }}>
          <Alert
            type={flowChain ? "info" : "warning"}
            showIcon
            title={`审批链：${flowChain || "未配置"}`}
            description={
              countersignHint
                ? `${countersignHint}。提交后进入审批中，审批人在「审批工作台」办理。`
                : "提交后进入审批中，审批人在「审批工作台」办理。"
            }
          />
          <Space size={24} wrap>
            <Text>票面字段：{(template?.fields ?? []).length} 项</Text>
            <Text>安全措施：已确认 {confirmed.length} 条</Text>
            <Text>气体检测：{gasTests.length} 次</Text>
          </Space>
          {problems.length > 0 && (
            <Alert
              type="error"
              showIcon
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
        </Space>
      )}

      <Space style={{ marginTop: 24 }}>
        <Button disabled={step === 0} onClick={() => setStep((s) => s - 1)}>
          上一步
        </Button>
        {step < STEPS.length - 1 ? (
          <Button type="primary" onClick={() => setStep((s) => s + 1)}>
            下一步
          </Button>
        ) : (
          <Button type="primary" loading={submitting} onClick={handleSubmit}>
            提交审批
          </Button>
        )}
      </Space>
    </div>
  );
}
