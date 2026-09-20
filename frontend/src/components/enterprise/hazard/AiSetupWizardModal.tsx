/**
 * AI 智能引导（§3.8/#7）：一次把「组织架构 / 排查计划 / 检查表模板」建好。
 *
 * 设计契约（与后端一致，别改歪）：
 *  - `POST /hazard-inspection/ai/setup-wizard` **只出建议、不落库**；
 *  - 三块各自走既有写入端点：组织树 PUT /org/nodes、计划 POST /hazard-inspection/plans、
 *    检查表 POST /hazard-inspection/templates —— 所以某一块失败不影响另外两块；
 *  - AI 未配置时后端返回 `available:false`（200），界面必须降级提示而不是报错；
 *  - 名字→id 的映射与「AI 生成计划」共用 `utils/hazardSetupWizard`，避免两套规则漂移。
 */
import { useEffect, useMemo, useState } from "react";
import { Alert, App as AntApp, Button, Checkbox, Divider, Form, Input, Modal, Select, Space, Steps, Tag, Typography } from "antd";
import { RobotOutlined } from "@ant-design/icons";
import { useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import { aiSetupWizard, createHazardPlan, createHazardTemplate } from "@/services/hazardService";
import { getOrgNodes, saveOrgNodes } from "@/services/enterpriseOrgService";
import type { OrgNode } from "@/types/enterpriseOrg";
import { mergeOrgNodes } from "@/utils/orgMerge";
import {
  buildChecklistItems,
  buildOrgNodes,
  buildPlanPayloads,
  type WizardMember,
  type WizardZone,
} from "@/utils/hazardSetupWizard";
import type { HazardSetupWizardResult } from "@/types/hazard";

const { Text, Paragraph } = Typography;

const FREQUENCY_OPTIONS = [
  { value: "精简", label: "精简（少量高频）" },
  { value: "标准", label: "标准（覆盖主要区域）" },
  { value: "严格", label: "严格（全区域全覆盖）" },
];

const TEMPLATE_CATEGORY_OPTIONS = [
  { value: "daily", label: "日常排查" },
  { value: "comprehensive", label: "综合排查" },
  { value: "special", label: "专项排查" },
  { value: "holiday", label: "节假日排查" },
];

const ORG_TYPE_LABEL: Record<string, string> = { dept: "部门", team: "班组", position: "岗位" };
const ORG_TYPE_COLOR: Record<string, string> = { dept: "blue", team: "green", position: "purple" };

function extractDetail(err: unknown): string {
  if (axios.isAxiosError(err)) {
    const detail = (err.response?.data as { detail?: unknown } | undefined)?.detail;
    if (typeof detail === "string" && detail) return detail;
    return err.message;
  }
  return err instanceof Error ? err.message : "";
}

interface Props {
  open: boolean;
  onClose: () => void;
  enterpriseId: string;
  /** 预填行业（取当前企业的 industry） */
  industry?: string;
  zones: WizardZone[];
  members: WizardMember[];
  /** 任一区块写入成功后回调（页面刷新列表用） */
  onWrote?: () => void;
}

type BlockKey = "org" | "plans" | "checklist";

interface BlockResult {
  ok: boolean;
  text: string;
}

export default function AiSetupWizardModal({ open, onClose, enterpriseId, industry, zones, members, onWrote }: Props) {
  const { message } = AntApp.useApp();
  const queryClient = useQueryClient();
  const [form] = Form.useForm<{ industry: string; areas: string; employee_count?: string; frequency_preference?: string }>();
  const [step, setStep] = useState(0);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<HazardSetupWizardResult | null>(null);
  const [orgChecked, setOrgChecked] = useState<string[]>([]);
  const [planChecked, setPlanChecked] = useState<number[]>([]);
  const [itemChecked, setItemChecked] = useState<number[]>([]);
  const [templateName, setTemplateName] = useState("");
  const [templateCategory, setTemplateCategory] = useState("daily");
  const [busy, setBusy] = useState<BlockKey | "all" | null>(null);
  const [results, setResults] = useState<Partial<Record<BlockKey, BlockResult>>>({});

  const orgNodes: OrgNode[] = useMemo(() => buildOrgNodes(result?.org_suggestion), [result]);
  const planMappings = useMemo(
    () => buildPlanPayloads(result?.plans_suggestion?.plans, zones, members),
    [result, zones, members],
  );
  const checklistItems = useMemo(() => buildChecklistItems(result?.checklist_suggestion?.items), [result]);

  // 每次打开都回到初始态，避免上一次的建议/勾选残留
  useEffect(() => {
    if (!open) return;
    setStep(0);
    setResult(null);
    setResults({});
    setOrgChecked([]);
    setPlanChecked([]);
    setItemChecked([]);
    setTemplateCategory("daily");
    form.setFieldsValue({
      industry: industry ?? "",
      areas: zones.map((z) => z.name).join("、"),
      employee_count: "",
      frequency_preference: "标准",
    });
  }, [open, industry, zones, form]);

  const runGenerate = async () => {
    let values;
    try {
      values = await form.validateFields();
    } catch {
      return;
    }
    setLoading(true);
    try {
      const res = await aiSetupWizard(enterpriseId, {
        industry: values.industry.trim(),
        areas: values.areas.trim(),
        employee_count: values.employee_count?.trim() || null,
        frequency_preference: values.frequency_preference?.trim() || null,
      });
      setResult(res);
      setStepsAfterGenerate(res);
      if (!res.available) {
        message.warning(res.note || "AI 暂不可用，请手动维护组织架构 / 计划 / 检查表");
      }
    } catch (e) {
      message.error("生成建议失败：" + extractDetail(e));
    } finally {
      setLoading(false);
    }
  };

  const setStepsAfterGenerate = (res: HazardSetupWizardResult) => {
    // 真实模型实测：一家 120 人企业会给 89 个节点，其中 51 个是**岗位**。
    // 全量默认勾选会把一堆没有成员的岗位空节点灌进组织树，所以默认只勾部门/班组，
    // 岗位留给用户按需勾（上方另给 全选/只选部门班组/清空 三个快捷操作）。
    setOrgChecked(buildOrgNodes(res.org_suggestion).filter((n) => n.type !== "position").map((n) => n.id));
    setPlanChecked(buildPlanPayloads(res.plans_suggestion?.plans, zones, members).map((_, i) => i));
    setItemChecked(buildChecklistItems(res.checklist_suggestion?.items).map((_, i) => i));
    const firstArea = String(form.getFieldValue("areas") || "").split(/[、,，]/)[0]?.trim();
    setTemplateName(`${firstArea || "企业"}隐患排查检查表`);
    setStep(res.available ? 1 : 0);
  };

  const writeOrg = async (): Promise<string> => {
    const nodes = orgNodes.filter((n) => orgChecked.includes(n.id));
    if (!nodes.length) return "未勾选任何节点，已跳过";
    // 增量合并，绝不整树替换：PUT /org/nodes 是全量写入，直接提交 AI 建议会把
    // 企业已有的部门/班组/岗位（以及挂在节点上的成员）全部冲掉。
    // mergeOrgNodes 按 (type,name[,父组]) 复用已有节点，只补缺的。
    const existing = await getOrgNodes(enterpriseId);
    const merged = mergeOrgNodes(existing, nodes);
    await saveOrgNodes(enterpriseId, merged);
    queryClient.invalidateQueries({ queryKey: ["org-nodes", enterpriseId] });
    const added = merged.length - existing.length;
    return `组织架构已合并：新增 ${added} 个节点，复用 ${nodes.length - added} 个已有节点（原有节点全部保留）`;
  };

  const writePlans = async (): Promise<string> => {
    const picked = planMappings.filter((_, i) => planChecked.includes(i));
    if (!picked.length) return "未勾选任何计划，已跳过";
    // 后端要求 zone_ids 非空；企业还没建分区时，AI 建议的分区名必然映射不到 id。
    // 这种情况下不要拿 422 当结果抛给用户，而是**跳过并说清怎么办**。
    const ready = picked.filter((m) => m.payload.zone_ids.length > 0);
    const skipped = picked.filter((m) => m.payload.zone_ids.length === 0);
    let ok = 0;
    const unmatched: string[] = [];
    for (const m of ready) {
      await createHazardPlan(enterpriseId, m.payload);
      ok += 1;
      unmatched.push(...m.unmatchedZones);
    }
    if (ok) queryClient.invalidateQueries({ queryKey: ["hazard-plans", enterpriseId] });
    const parts = [`已创建 ${ok} 个排查计划`];
    if (unmatched.length) {
      parts.push(`${unmatched.length} 个分区名未匹配（${unmatched.join("、")}），已按匹配到的分区创建，请在计划里补选`);
    }
    if (skipped.length) {
      parts.push(`${skipped.length} 个计划因「企业还没有对应分区」被跳过（${skipped.map((m) => m.payload.name).join("、")}）：`
        + "请先到「四色图工作台」建好分区，再回来点一次");
    }
    return parts.join("；");
  };

  const writeChecklist = async (): Promise<string> => {
    const items = checklistItems.filter((_, i) => itemChecked.includes(i));
    if (!items.length) return "未勾选任何条目，已跳过";
    const name = templateName.trim() || "隐患排查检查表";
    await createHazardTemplate(enterpriseId, { name, category: templateCategory, items });
    queryClient.invalidateQueries({ queryKey: ["hazard-templates", enterpriseId] });
    return `已创建检查表模板「${name}」（${items.length} 条）`;
  };

  const runBlock = async (key: BlockKey) => {
    setBusy(key);
    try {
      const text = key === "org" ? await writeOrg() : key === "plans" ? await writePlans() : await writeChecklist();
      setResults((prev) => ({ ...prev, [key]: { ok: true, text } }));
      onWrote?.();
    } catch (e) {
      setResults((prev) => ({ ...prev, [key]: { ok: false, text: extractDetail(e) || "写入失败" } }));
    } finally {
      setBusy(null);
    }
  };

  const runAll = async () => {
    setBusy("all");
    try {
      for (const key of ["org", "plans", "checklist"] as BlockKey[]) {
        try {
          const text = key === "org" ? await writeOrg() : key === "plans" ? await writePlans() : await writeChecklist();
          setResults((prev) => ({ ...prev, [key]: { ok: true, text } }));
          onWrote?.();
        } catch (e) {
          // 单块失败不打断其余两块（后端三块本来就独立）
          setResults((prev) => ({ ...prev, [key]: { ok: false, text: extractDetail(e) || "写入失败" } }));
        }
      }
      setStep(2);
    } finally {
      setBusy(null);
    }
  };

  const allWritten = (["org", "plans", "checklist"] as BlockKey[]).every((k) => results[k]?.ok);
  const anyWritten = (["org", "plans", "checklist"] as BlockKey[]).some((k) => results[k]);

  const footer = () => {
    if (step === 0) {
      return [
        <Button key="cancel" onClick={onClose}>取消</Button>,
        <Button key="gen" type="primary" icon={<RobotOutlined />} loading={loading} onClick={() => void runGenerate()}>
          生成建议
        </Button>,
      ];
    }
    if (step === 1) {
      return [
        <Button key="back" onClick={() => setStep(0)}>上一步</Button>,
        <Button key="all" type="primary" loading={busy === "all"} onClick={() => void runAll()}>
          全部确认写入
        </Button>,
      ];
    }
    return [
      <Button key="close" type="primary" onClick={onClose}>
        {allWritten ? "完成" : "关闭"}
      </Button>,
    ];
  };

  return (
    <Modal
      open={open}
      onCancel={onClose}
      title={<Space><RobotOutlined style={{ color: "#1A56DB" }} />AI 智能引导</Space>}
      width={1080}
      footer={footer()}
      destroyOnHidden
    >
      <Steps
        size="small"
        current={step}
        items={[{ title: "填写基础信息" }, { title: "审阅三块建议" }, { title: "确认写入" }, { title: "完成" }]}
        style={{ margin: "8px 0 18px" }}
      />

      {step === 0 && (
        <>
          <Alert
            type="info"
            showIcon
            style={{ marginBottom: 14 }}
            title="一次生成三块建议，逐块确认后才写入"
            description="AI 只产出建议（不落库）；未配置 AI 时会提示手动维护，不会报错。"
          />
          <Form form={form} layout="vertical" style={{ maxWidth: 640 }}>
            <Form.Item name="industry" label="所属行业" rules={[{ required: true, message: "请填写所属行业" }]}>
              <Input placeholder="如：化工 / 危险化学品经营" />
            </Form.Item>
            <Form.Item name="areas" label="主要区域（逗号分隔）" rules={[{ required: true, message: "请填写主要区域" }]}>
              <Input.TextArea rows={3} placeholder="如：储罐区、装卸区、生产车间" />
            </Form.Item>
            <Form.Item name="employee_count" label="员工数量（可选）">
              <Input placeholder="如：120" />
            </Form.Item>
            <Form.Item name="frequency_preference" label="排查频次偏好（可选）">
              <Select options={FREQUENCY_OPTIONS} allowClear placeholder="选择偏好" />
            </Form.Item>
          </Form>
        </>
      )}

      {step >= 1 && result && (
        <>
          {!result.available && (
            <Alert
              type="warning"
              showIcon
              style={{ marginBottom: 14 }}
              title={result.note || "AI 暂不可用，请手动维护"}
              description="可以手动到「组织架构」「排查计划」「检查表模板」页维护，或稍后重试。"
            />
          )}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 16 }}>
            {/* ① 组织架构 */}
            <div>
              <Text strong>① 组织架构（{orgNodes.length} 个节点）</Text>
              {orgNodes.length > 0 && (
                <div style={{ marginTop: 6, marginBottom: 2 }}>
                  <Space size={6}>
                    <Text type="secondary" style={{ fontSize: 11 }}>
                      已选 {orgChecked.length}/{orgNodes.length}
                    </Text>
                    <Button size="small" type="link" style={{ padding: 0, fontSize: 12 }}
                            onClick={() => setOrgChecked(orgNodes.map((n) => n.id))}>全选</Button>
                    <Button size="small" type="link" style={{ padding: 0, fontSize: 12 }}
                            onClick={() => setOrgChecked(orgNodes.filter((n) => n.type !== "position").map((n) => n.id))}>
                      只选部门·班组
                    </Button>
                    <Button size="small" type="link" style={{ padding: 0, fontSize: 12 }}
                            onClick={() => setOrgChecked([])}>清空</Button>
                  </Space>
                </div>
              )}
              <div style={{ border: "1px solid #f0f0f0", borderRadius: 6, padding: 10, marginTop: 8, height: 240, overflow: "auto" }}>
                {orgNodes.length === 0 ? (
                  <Text type="secondary">无建议</Text>
                ) : orgNodes.map((n) => (
                  <div key={n.id} style={{ paddingLeft: n.parent_id ? 16 : 0, marginBottom: 6 }}>
                    <Checkbox
                      checked={orgChecked.includes(n.id)}
                      onChange={(e) => setOrgChecked((prev) => e.target.checked ? [...prev, n.id] : prev.filter((x) => x !== n.id))}
                    >
                      <Text style={{ fontSize: 13 }}>{n.name}</Text>
                      <Tag style={{ marginLeft: 6 }} color={ORG_TYPE_COLOR[n.type]}>{ORG_TYPE_LABEL[n.type]}</Tag>
                    </Checkbox>
                  </div>
                ))}
              </div>
              <Button size="small" type="primary" block style={{ marginTop: 8 }} disabled={step === 2}
                      loading={busy === "org"} onClick={() => void runBlock("org")}>
                合并写入组织架构
              </Button>
              <Text type="secondary" style={{ fontSize: 11, display: "block", marginTop: 4 }}>
                增量合并：同名部门/班组/岗位复用，只补缺的节点，不会覆盖现有组织架构与成员。
              </Text>
              {results.org && <Result r={results.org} />}
            </div>

            {/* ② 排查计划 */}
            <div>
              <Text strong>② 排查计划（{planMappings.length} 个）</Text>
              <div style={{ border: "1px solid #f0f0f0", borderRadius: 6, padding: 10, marginTop: 8, height: 240, overflow: "auto" }}>
                {planMappings.length === 0 ? (
                  <Text type="secondary">无建议</Text>
                ) : planMappings.map((m, i) => (
                  <div key={`${m.payload.name}-${i}`} style={{ marginBottom: 8 }}>
                    <Checkbox
                      checked={planChecked.includes(i)}
                      onChange={(e) => setPlanChecked((prev) => e.target.checked ? [...prev, i] : prev.filter((x) => x !== i))}
                    >
                      <Text style={{ fontSize: 13 }}>{m.payload.name}</Text>
                      <Tag color="orange" style={{ marginLeft: 6 }}>{m.payload.frequency}</Tag>
                    </Checkbox>
                    <div style={{ marginLeft: 24 }}>
                      {m.payload.zone_ids.length === 0 ? (
                        <Text type="warning" style={{ fontSize: 11 }}>
                          该企业还没有对应分区 → 会跳过（先去「四色图工作台」建分区）
                        </Text>
                      ) : (
                        <Text type="secondary" style={{ fontSize: 11 }}>
                          覆盖：{m.payload.zone_ids.length} 个分区
                          {m.payload.responsible_user_id ? " · 已匹配责任人" : ""}
                          {m.unmatchedZones.length ? ` · ${m.unmatchedZones.length} 个分区名待手动补选` : ""}
                        </Text>
                      )}
                    </div>
                  </div>
                ))}
              </div>
              <Button size="small" type="primary" block style={{ marginTop: 8 }} disabled={step === 2}
                      loading={busy === "plans"} onClick={() => void runBlock("plans")}>
                确认并创建计划
              </Button>
              {results.plans && <Result r={results.plans} />}
            </div>

            {/* ③ 检查表 */}
            <div>
              <Text strong>③ 检查表模板（{checklistItems.length} 条）</Text>
              <Space orientation="vertical" style={{ width: "100%", marginTop: 8 }} size={6}>
                <Input size="small" value={templateName} onChange={(e) => setTemplateName(e.target.value)} placeholder="模板名称" />
                <Select size="small" style={{ width: "100%" }} value={templateCategory} onChange={setTemplateCategory} options={TEMPLATE_CATEGORY_OPTIONS} />
              </Space>
              <div style={{ border: "1px solid #f0f0f0", borderRadius: 6, padding: 10, marginTop: 8, height: 168, overflow: "auto" }}>
                {checklistItems.length === 0 ? (
                  <Text type="secondary">无建议</Text>
                ) : checklistItems.map((it, i) => (
                  <div key={`${it.content}-${i}`} style={{ marginBottom: 6 }}>
                    <Checkbox
                      checked={itemChecked.includes(i)}
                      onChange={(e) => setItemChecked((prev) => e.target.checked ? [...prev, i] : prev.filter((x) => x !== i))}
                    >
                      <Text style={{ fontSize: 13 }}>{it.content}</Text>
                    </Checkbox>
                    {it.expected_note && (
                      <div style={{ marginLeft: 24 }}><Text type="secondary" style={{ fontSize: 11 }}>要求：{it.expected_note}</Text></div>
                    )}
                  </div>
                ))}
              </div>
              <Button size="small" type="primary" block style={{ marginTop: 8 }} disabled={step === 2}
                      loading={busy === "checklist"} onClick={() => void runBlock("checklist")}>
                确认并创建检查表
              </Button>
              {results.checklist && <Result r={results.checklist} />}
            </div>
          </div>

          <Divider style={{ margin: "14px 0" }} />
          <Paragraph type="secondary" style={{ marginBottom: 0, fontSize: 12 }}>
            三块走各自的既有接口，互不影响；同名同类别模板已存在时会提示冲突，改个名字再试即可。
            {anyWritten && !allWritten ? " 已完成的块可以留着，未完成的块可以单独重试。" : ""}
          </Paragraph>
        </>
      )}
    </Modal>
  );
}

function Result({ r }: { r: BlockResult }) {
  return (
    <div style={{ marginTop: 6 }}>
      <Text type={r.ok ? "success" : "danger"} style={{ fontSize: 12 }}>
        {r.ok ? "✓ " : "✕ "}{r.text}
      </Text>
    </div>
  );
}
