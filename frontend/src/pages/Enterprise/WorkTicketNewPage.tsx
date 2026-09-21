import { useEffect, useMemo, useState } from "react";
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
import MeasureChecklist from "@/components/enterprise/workTicket/MeasureChecklist";
import { SOURCE_LABEL } from "@/components/enterprise/workTicket/fieldSources";
import { normalizeValues, toFormValues } from "@/components/enterprise/workTicket/formValues";
import { pruneScenario, scenarioFieldsFor } from "@/components/enterprise/workTicket/scenarioScope";
import PrefillBadge from "@/components/enterprise/workTicket/PrefillBadge";
import { PageHeader } from "@/components/common/PageHeader";
import { getEnterprise } from "@/services/enterpriseService";
import {
  addGasTest,
  aiPrefill,
  errorDetail,
  getPrefill,
  listLocations,
  listTemplates,
  openTicket,
  saveDraft,
  submitTicket,
} from "@/services/workTicketService";
import type {
  FieldMeta,
  FieldSource,
  GasTestPayload,
  MeasureMeta,
  MeasureSuggestion,
  PrefillMember,
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

/** 级别字段：第 0 步选完级别后自动联动回票面，避免二次输入。 */
const LEVEL_FIELD_BY_TYPE: Partial<Record<string, string>> = {
  DHZY: "fire_level",
  GCZY: "high_level",
  QZDZ: "lift_level",
};

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
 * 与原版的差别（2026-09-20 智能预填）：
 * - 第 0 步多了「作业地点」与「作业情景」，两者决定措施建议与风险辨识的输入
 * - 第 1 步进入即调确定性预填，每个自动带出的字段显示来源徽标
 * - 级别在第 0 步选完自动联动到票面，不再二次输入
 * - 第 3 步换成三态措施列表（确认涉及 / 本票不涉及（需理由） / 撤销），
 *   取消了无条件的「全部确认」
 * - 第 5 步给出「填写来源摘要」，AI 生成但未确认的字段会阻断提交
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
  const [measuresMeta, setMeasuresMeta] = useState<Record<string, MeasureMeta>>({});
  const [valuesMeta, setValuesMeta] = useState<Record<string, FieldMeta>>({});
  const [suggestions, setSuggestions] = useState<MeasureSuggestion[]>([]);
  const [members, setMembers] = useState<PrefillMember[]>([]);
  const [jsa, setJsa] = useState("");
  const [jsaMeta, setJsaMeta] = useState<FieldMeta | null>(null);
  const [scenario, setScenario] = useState<Record<string, boolean>>({});
  const [scenarioDeclared, setScenarioDeclared] = useState(false);
  const [locationId, setLocationId] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [problems, setProblems] = useState<string[]>([]);
  const [draftId, setDraftId] = useState<string | null>(null);
  const [prefillNote, setPrefillNote] = useState<string | null>(null);

  const { data: enterprise } = useQuery({
    queryKey: ["enterprise", id],
    queryFn: () => getEnterprise(id as string),
    enabled: Boolean(id),
  });

  const { data: templates } = useQuery({
    queryKey: ["work-ticket-templates"],
    queryFn: listTemplates,
  });

  const { data: locations } = useQuery({
    queryKey: ["work-ticket-locations", id],
    queryFn: () => listLocations(id as string),
    enabled: Boolean(id),
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
  const levelFieldKey = activeTicketType ? LEVEL_FIELD_BY_TYPE[activeTicketType] : undefined;
  // 情景区随票种变化：项来自后端（YAML 条件表），不再写死一组通用的动火情景
  const scenarioFields = useMemo(() => scenarioFieldsFor(template), [template]);

  /** 传给后端的作业情景：勾选=true；开了「已核实」开关时未勾选的项=false。 */
  const scenarioParam = useMemo(() => {
    const out: Record<string, boolean> = {};
    for (const field of scenarioFields) {
      if (scenario[field.key]) out[field.key] = true;
      else if (scenarioDeclared) out[field.key] = false;
    }
    return out;
  }, [scenario, scenarioDeclared, scenarioFields]);

  /** 确定性预填：模板或级别变化时重新取数（不触发 AI，无 token 成本）。 */
  useEffect(() => {
    if (!id || !template) return;
    let cancelled = false;
    getPrefill({
      enterprise_id: id,
      template_id: template.id,
      level: activeLevel || null,
      risk_object_id: locationId,
      fire_method: (form.getFieldValue("fire_method") as string) ?? null,
      scenario: JSON.stringify(scenarioParam),
    })
      .then((payload) => {
        if (cancelled) return;
        form.setFieldsValue(
          toFormValues(template.fields ?? [], payload.values ?? {}),
        );
        setValuesMeta(payload.values_meta ?? {});
        setSuggestions(payload.measures_suggestions ?? []);
        setMembers(payload.members ?? []);
        setPrefillNote(
          Object.keys(payload.values ?? {}).length > 0
            ? `已自动带出 ${Object.keys(payload.values).length} 项，其余请现场填写`
            : "没有可自动带出的内容，请手动填写",
        );
      })
      .catch(() => {
        if (cancelled) return;
        // 预填失败不阻断开票：表单保持空白可用
        setPrefillNote("未能自动带出，可手动填写");
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, template?.id, activeLevel, locationId, scenarioParam]);

  /**
   * 进入「安全措施」步骤时重取一次建议：此时票面已填，自动项（作业高度、动土深度、
   * 吊装级别）才有值可推断；只更新 measures_suggestions，不动表单值。
   */
  useEffect(() => {
    if (step !== 3 || !id || !template) return;
    let cancelled = false;
    getPrefill({
      enterprise_id: id,
      template_id: template.id,
      level: activeLevel || null,
      risk_object_id: locationId,
      fire_method: (form.getFieldValue("fire_method") as string) ?? null,
      scenario: JSON.stringify(scenarioParam),
    })
      .then((payload) => {
        if (!cancelled) setSuggestions(payload.measures_suggestions ?? []);
      })
      .catch(() => {
        // 建议取不到不阻断：保持上一次的建议（或全部留在主列表由人工逐条处理）
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [step]);

  /**
   * 级别联动：第 0 步定完级别，票面对应字段自动跟随。
   *
   * effect 里只同步"表单实例"这一外部系统，不写 React state
   * （派生值见 fieldSource()），避免 effect 内 setState 造成级联渲染。
   */
  useEffect(() => {
    if (!levelFieldKey || !activeLevel) return;
    form.setFieldValue(levelFieldKey, activeLevel);
  }, [form, levelFieldKey, activeLevel]);

  /** 字段来源的派生读取：级别字段永远算向导联动，其余读 valuesMeta。 */
  const fieldSource = (key: string): FieldSource | undefined =>
    levelFieldKey === key && activeLevel ? "template_link" : valuesMeta[key]?.source;

  /** 与后端 validate_before_submit 同一条规则，提前把问题说清楚。 */
  const localPrecheck = (): string[] => {
    const errs: string[] = [];
    const raw = (form.getFieldsValue() ?? {}) as Record<string, unknown>;
    for (const f of requiredFields) {
      const value = raw[f.field_key];
      if (value === undefined || value === null || value === "") {
        errs.push(`必填项「${f.label}」尚未填写`);
      }
      const meta = valuesMeta[f.field_key];
      if (meta?.source === "ai" && !meta.confirmed_at) {
        errs.push(`「${f.label}」为 AI 生成内容，尚未经人工确认`);
      }
    }
    const missing = mandatoryMeasures.filter((m) => {
      const state = measuresMeta[String(m.sort_order)]?.state;
      return state !== "confirmed" && state !== "not_applicable";
    });
    if (missing.length > 0) {
      errs.push(
        `还有 ${missing.length} 条安全措施未表态（如「${missing[0].measure_text.slice(0, 20)}…」）`,
      );
    }
    for (const [key, meta] of Object.entries(measuresMeta)) {
      if (meta.state === "not_applicable" && !meta.reason_text?.trim()) {
        errs.push(`第 ${key} 条措施标记为「本票不涉及」，但未填写理由`);
      }
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

  const collectPayload = () => ({
    values: {
      ...normalizeValues(template?.fields ?? [], form.getFieldsValue()),
      confirmed_measures: mandatoryMeasures
        .filter((m) => measuresMeta[String(m.sort_order)]?.state === "confirmed")
        .map((m) => m.sort_order),
      jsa: jsa || null,
    },
    values_meta: {
      ...valuesMeta,
      ...(levelFieldKey && activeLevel
        ? { [levelFieldKey]: { source: "template_link" as const, edited: false } }
        : {}),
      ...(jsaMeta ? { jsa: jsaMeta } : {}),
    },
    measures_meta: measuresMeta,
  });

  const handleSaveDraft = async () => {
    if (!id || !template) return;
    const payload = collectPayload();
    try {
      if (draftId) {
        await saveDraft(draftId, payload);
      } else {
        const instance = await openTicket({
          enterprise_id: id,
          enterprise_code: enterpriseCode,
          ticket_type: activeTicketType as WorkTicketTypeCode,
          template_id: template.id,
          level: levelsForType.length > 0 ? activeLevel : null,
          values: payload.values,
        });
        setDraftId(instance.id);
        await saveDraft(instance.id, payload);
      }
      message.success("草稿已保存，可稍后继续");
    } catch (err) {
      message.error(errorDetail(err, "草稿保存失败"));
    }
  };

  const handleSubmit = async () => {
    if (!id) return;
    if (!activeTicketType || !template) {
      message.error("未找到对应的作业票模板，请检查模板种子数据");
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
      const payload = collectPayload();
      const instance = draftId
        ? await saveDraft(draftId, payload).then(() => ({ id: draftId }))
        : await openTicket({
            enterprise_id: id,
            enterprise_code: enterpriseCode,
            ticket_type: activeTicketType,
            template_id: template.id,
            level: levelsForType.length > 0 ? activeLevel : null,
            values: payload.values,
          });
      if (!draftId) {
        await saveDraft(instance.id, payload);
      }
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

  /** AI 生成风险辨识结果：用户显式点击才调用，失败静默降级。 */
  const handleAiRisk = async () => {
    if (!id || !activeTicketType) return;
    const result = await aiPrefill({
      enterprise_id: id,
      ticket_type: activeTicketType,
      level: activeLevel || null,
      work_content: (form.getFieldValue("work_content") as string) ?? null,
    });
    if (!result.available || !result.risk_identification) {
      message.info(result.note || "AI 暂不可用，请手动填写");
      return;
    }
    form.setFieldValue("risk_identification", result.risk_identification.text);
    setValuesMeta((prev) => ({
      ...prev,
      risk_identification: {
        source: "ai",
        source_ref: { basis: result.risk_identification?.basis ?? [] },
        edited: false,
      },
    }));
    if (result.jsa?.text) {
      setJsa(result.jsa.text);
      setJsaMeta({ source: "ai", edited: false });
    }
    message.success("已生成，请核对后确认采用");
  };

  const renderField = (field: WorkTicketFieldDef) => {
    const memberOptions = members.map((m) => ({ value: m.name, label: m.name }));
    if (["work_leader", "guardian", "fire_person", "electrician", "lift_commander"].includes(field.field_key)) {
      return (
        <Select
          showSearch
          allowClear
          placeholder={memberOptions.length ? "从成员台账选择或手工输入" : field.label}
          options={memberOptions}
          dropdownRender={(menu) => (
            <>
              {menu}
              <Divider style={{ margin: "4px 0" }} />
              <div style={{ padding: "4px 8px" }}>
                <Text type="secondary">
                  也可直接输入：姓名 + 证书编号（动火人/电工需证书号）
                </Text>
              </div>
            </>
          )}
        />
      );
    }
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

  const sourceSummary = useMemo(() => {
    const counts: Partial<Record<FieldSource, number>> = {};
    let aiUnconfirmed: string[] = [];
    for (const [key, meta] of Object.entries(valuesMeta)) {
      counts[meta.source] = (counts[meta.source] ?? 0) + 1;
      if (meta.source === "ai" && !meta.confirmed_at) {
        const label = template?.fields.find((f) => f.field_key === key)?.label ?? key;
        aiUnconfirmed = [...aiUnconfirmed, label];
      }
    }
    return { counts, aiUnconfirmed };
  }, [valuesMeta, template]);

  /** 第 1 步的字段级「采用」动作：把来源标记进去（AI 值由此获得确认时间）。 */
  const confirmField = (key: string) => {
    setValuesMeta((prev) => ({
      ...prev,
      [key]: { ...prev[key], source: prev[key]?.source ?? "manual", confirmed_at: new Date().toISOString() },
    }));
  };

  return (
    <div>
      <PageHeader
        title="开票"
        subtitle="按 GB 30871-2022 附录A 票面填报；带来源徽标的字段为系统自动带出，请核对"
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
                  setMeasuresMeta({});
                  setProblems([]);
                  const nextLevels = Array.from(
                    new Set(
                      (templates ?? [])
                        .filter((t) => t.code === next && t.level)
                        .map((t) => t.level as string),
                    ),
                  );
                  setLevel(nextLevels[0] ?? "");
                  // 切票种时清掉不属于新票种的情景勾选（避免动火情景被带到受限空间/吊装等票）
                  const nextTemplate =
                    (templates ?? []).find(
                      (t) => t.code === next && (t.level ?? null) === (nextLevels[0] ?? null),
                    ) ?? (templates ?? []).find((t) => t.code === next);
                  setScenario((prev) => pruneScenario(prev, scenarioFieldsFor(nextTemplate)));
                  setScenarioDeclared(false);
                }}
                options={enabledTypes.map((t) => ({ value: t.code, label: t.label }))}
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
              <Text type="secondary">级别选定后会自动带入票面，无需二次输入。</Text>
            </div>
          )}
          <div>
            <Text strong>作业地点</Text>
            <div style={{ marginTop: 8 }}>
              <Select
                allowClear
                showSearch
                placeholder={
                  (locations?.objects?.length ?? 0) > 0 || (locations?.zones?.length ?? 0) > 0
                    ? "从风险区域/对象中选择（可留空手工填写）"
                    : "未维护风险区域，请在票面手工填写地点"
                }
                style={{ minWidth: 360 }}
                value={locationId}
                onChange={(value) => setLocationId(value ?? null)}
                options={[
                  ...(locations?.objects ?? []).map((o) => ({
                    value: o.id,
                    label: `对象：${o.name}${o.location ? `（${o.location}）` : ""}`,
                  })),
                  ...(locations?.zones ?? []).map((z) => ({
                    value: z.id,
                    label: `区域：${z.name}`,
                  })),
                ]}
                optionFilterProp="label"
              />
            </div>
          </div>
          <div>
            <Text strong>作业情景（{ALL_TICKET_TYPES.find((t) => t.code === activeTicketType)?.label}）</Text>
            <div style={{ marginTop: 8 }}>
              {scenarioFields.length > 0 ? (
                <Space orientation="vertical" size={4}>
                  {scenarioFields.map((field) => (
                    <Checkbox
                      key={field.key}
                      checked={Boolean(scenario[field.key])}
                      onChange={(e) =>
                        setScenario((prev) => ({ ...prev, [field.key]: e.target.checked }))
                      }
                    >
                      {field.label}
                    </Checkbox>
                  ))}
                  <Checkbox
                    checked={scenarioDeclared}
                    onChange={(e) => setScenarioDeclared(e.target.checked)}
                  >
                    以上未勾选的情景均已现场核实「不涉及」
                  </Checkbox>
                </Space>
              ) : (
                <Text type="secondary">
                  本票种无需额外情景（如夜间照明要求由作业时段自动判定）。
                </Text>
              )}
            </div>
            <Text type="secondary">
              勾选会用于生成措施建议；未勾选且未声明核实时，系统不会替你判定「不涉及」。
            </Text>
          </div>
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
          {prefillNote && (
            <Alert
              type="info"
              showIcon
              style={{ marginBottom: 12 }}
              title={prefillNote}
              description="带徽标的字段来自既有数据或 AI，请核对后再提交。"
            />
          )}
          {Object.entries(groupedFields).map(([group, fields]) => (
            <div key={group}>
              <Divider titlePlacement="left">{group}</Divider>
              {fields.map((field) => (
                <Form.Item
                  key={field.field_key}
                  name={field.field_key}
                  label={
                    <Space size={4}>
                      <span>{field.label}</span>
                      <PrefillBadge
                        source={fieldSource(field.field_key)}
                        detail={SOURCE_LABEL[fieldSource(field.field_key) ?? "manual"]}
                      />
                      {field.allow_ai_prefill && (
                        <Button size="small" type="link" onClick={handleAiRisk}>
                          AI 生成
                        </Button>
                      )}
                      {valuesMeta[field.field_key]?.source === "ai" &&
                        !valuesMeta[field.field_key]?.confirmed_at && (
                          <Button size="small" onClick={() => confirmField(field.field_key)}>
                            采用
                          </Button>
                        )}
                    </Space>
                  }
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
            title={requiresGasTest ? "本类型为法定强制气体检测" : "本类型不强制气体检测"}
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
        <MeasureChecklist
          measures={mandatoryMeasures}
          suggestions={suggestions}
          meta={measuresMeta}
          onChange={setMeasuresMeta}
        />
      )}

      {step === 4 && (
        <Space orientation="vertical" size={8} style={{ width: "100%" }}>
          <Space>
            <Text type="secondary">
              JSA（作业危害分析）可由 AI 生成草稿，是否采用由你决定。
            </Text>
            <Button size="small" onClick={handleAiRisk}>
              AI 生成
            </Button>
          </Space>
          <Input.TextArea
            rows={6}
            value={jsa}
            onChange={(e) => setJsa(e.target.value)}
            placeholder="可选：填写本次作业的危害分析与控制措施"
          />
          {jsaMeta?.source === "ai" && !jsaMeta.confirmed_at && (
            <Space>
              <PrefillBadge source="ai" />
              <Button
                size="small"
                onClick={() =>
                  setJsaMeta({ ...jsaMeta, confirmed_at: new Date().toISOString() })
                }
              >
                采用
              </Button>
            </Space>
          )}
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
          <div>
            <Text strong>填写来源摘要</Text>
            <div style={{ marginTop: 8 }}>
              <Space wrap>
                {Object.entries(sourceSummary.counts).map(([source, count]) => (
                  <Tag key={source} color={source === "ai" ? "purple" : "blue"}>
                    {SOURCE_LABEL[source as FieldSource]} {count} 项
                  </Tag>
                ))}
                {Object.keys(sourceSummary.counts).length === 0 && (
                  <Text type="secondary">全部为手工填写</Text>
                )}
              </Space>
            </div>
            {sourceSummary.aiUnconfirmed.length > 0 && (
              <Alert
                type="error"
                showIcon
                style={{ marginTop: 8 }}
                title="以下 AI 生成字段尚未确认，提交会被阻断"
                description={sourceSummary.aiUnconfirmed.join("、")}
              />
            )}
          </div>
          <Space size={24} wrap>
            <Text>票面字段：{(template?.fields ?? []).length} 项</Text>
            <Text>
              安全措施：已表态{" "}
              {
                mandatoryMeasures.filter((m) => {
                  const state = measuresMeta[String(m.sort_order)]?.state;
                  return state === "confirmed" || state === "not_applicable";
                }).length
              }{" "}
              / {mandatoryMeasures.length} 条
            </Text>
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
          <>
            <Button onClick={handleSaveDraft}>保存草稿</Button>
            <Button type="primary" loading={submitting} onClick={handleSubmit}>
              提交审批
            </Button>
          </>
        )}
      </Space>
    </div>
  );
}
