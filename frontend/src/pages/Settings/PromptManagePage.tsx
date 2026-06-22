import { useState } from "react";
import {
  Table, Modal, Form, Input, Select, Button, message, Tabs, Space, Tag,
} from "antd";
import { EditOutlined, ExperimentOutlined } from "@ant-design/icons";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  fetchPrompts,
  createPrompt,
  updatePrompt,
  testPrompt,
} from "@/services/promptService";
import type { PromptTemplate, PromptCreate, PromptUpdate } from "@/services/promptService";
import { PageHeader } from "@/components/common/PageHeader";

const { TextArea } = Input;

const PLAN_TYPES = [
  { key: "comprehensive", label: "综合应急预案" },
  { key: "special", label: "专项应急预案" },
  { key: "onsite", label: "现场处置方案" },
  { key: "risk_assessment", label: "风险评估报告" },
  { key: "resource_investigation", label: "应急资源调查报告" },
];

const CATEGORY_OPTIONS = [
  { value: "emergency_system", label: "系统提示词" },
  { value: "emergency_section", label: "章节提示词" },
  { value: "emergency_mermaid", label: "流程图提示词" },
  { value: "emergency_surrounding_system", label: "周边环境(系统)" },
  { value: "emergency_surrounding_user", label: "周边环境(用户)" },
  { value: "risk_assessment_system", label: "风险评估(系统)" },
  { value: "risk_assessment_section", label: "风险评估(章节)" },
  { value: "resource_investigation_system", label: "资源调查(系统)" },
  { value: "resource_investigation_section", label: "资源调查(章节)" },
];

export default function PromptManagePage() {
  const queryClient = useQueryClient();
  const [activePlanType, setActivePlanType] = useState("comprehensive");
  const [categoryFilter, setCategoryFilter] = useState<string | undefined>();
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [testModalOpen, setTestModalOpen] = useState(false);
  const [editingPrompt, setEditingPrompt] = useState<PromptTemplate | null>(null);
  const [testVariables, setTestVariables] = useState("{}");
  const [testResult, setTestResult] = useState<string>("");
  const [testing, setTesting] = useState(false);
  const [editForm] = Form.useForm();

  const { data: allPrompts = [], isLoading } = useQuery({
    queryKey: ["prompts", activePlanType, categoryFilter],
    queryFn: () => fetchPrompts(categoryFilter),
  });

  // 客户端按类型筛选
  const prompts = allPrompts.filter((p: PromptTemplate) => {
    const code = p.templateCode || "";
    // 预案类型: emergency_{category}_{planType}_...
    const parts = code.split("_");
    const planTypeInCode = parts.length >= 3 ? parts[2] : "";
    if (["comprehensive", "special", "onsite"].includes(planTypeInCode)) {
      return planTypeInCode === activePlanType;
    }
    // 报告类型: risk_assessment_ / resource_investigation_
    if (activePlanType === "risk_assessment" && code?.startsWith("risk_assessment_")) return true;
    if (activePlanType === "resource_investigation" && code?.startsWith("resource_investigation_")) return true;
    // 不包含特定类型的模板（如 mermaid, surrounding, default）在所有 tab 显示
    if (!["risk_assessment", "resource_investigation"].includes(activePlanType)) return true;
    return false;
  });

  const createMut = useMutation({
    mutationFn: (data: PromptCreate) => createPrompt(data),
    onSuccess: () => {
      message.success("创建成功");
      queryClient.invalidateQueries({ queryKey: ["prompts"] });
      setEditModalOpen(false);
    },
    onError: () => message.error("创建失败"),
  });

  const updateMut = useMutation({
    mutationFn: ({ id, data }: { id: number; data: PromptUpdate }) => updatePrompt(id, data),
    onSuccess: () => {
      message.success("更新成功");
      queryClient.invalidateQueries({ queryKey: ["prompts"] });
      setEditModalOpen(false);
    },
    onError: () => message.error("更新失败"),
  });

  const handleAdd = () => {
    setEditingPrompt(null);
    editForm.resetFields();
    editForm.setFieldsValue({ category: categoryFilter || "plan_content" });
    setEditModalOpen(true);
  };

  const handleEdit = (record: PromptTemplate) => {
    setEditingPrompt(record);
    editForm.setFieldsValue(record);
    setEditModalOpen(true);
  };

  const handleEditSubmit = async () => {
    const values = await editForm.validateFields();
    if (editingPrompt) {
      updateMut.mutate({ id: editingPrompt.id, data: values });
    } else {
      createMut.mutate(values as PromptCreate);
    }
  };

  const handleTest = (record: PromptTemplate) => {
    setEditingPrompt(record);
    setTestVariables("{}");
    setTestResult("");
    setTestModalOpen(true);
  };

  const handleTestSubmit = async () => {
    if (!editingPrompt) return;
    setTesting(true);
    try {
      let parsed: Record<string, string>;
      try {
        parsed = JSON.parse(testVariables);
      } catch {
        message.error("变量 JSON 格式不正确");
        setTesting(false);
        return;
      }
      const res = await testPrompt(editingPrompt.id, parsed);
      setTestResult(res.result);
    } catch {
      message.error("测试请求失败");
    } finally {
      setTesting(false);
    }
  };

  const columns = [
    { title: "模板编码", dataIndex: "templateCode", key: "template_code", width: 160 },
    { title: "模板名称", dataIndex: "templateName", key: "template_name", width: 180 },
    {
      title: "分类", dataIndex: "category", key: "category", width: 140,
      render: (c: string) => CATEGORY_OPTIONS.find((o) => o.value === c)?.label || c,
    },
    {
      title: "状态", dataIndex: "status", key: "status", width: 80,
      render: (s: string) => <Tag color={s === "0" ? "green" : "default"}>{s === "0" ? "启用" : "禁用"}</Tag>,
    },
    {
      title: "适用章节", dataIndex: "templateCode", key: "section", width: 160,
      render: (code: string) => {
        // 从 templateCode 解析 section_key 并映射中文名
        const parts = (code || "").split("_");
        const SK_MAP: Record<string, string> = {
          sec_1: "总则/风险分析/风险提示", sec_1_1: "编制目的/事故类型", sec_1_2: "编制依据/影响范围", sec_1_3: "适用范围", sec_1_4: "预案体系", sec_1_5: "工作原则",
          sec_2: "风险描述/指挥机构/组织联络", sec_2_1: "风险源识别", sec_2_2: "可能性及后果",
          sec_3: "组织机构/处置程序/处置卡", sec_3_1: "机构设置/启动流程/第一响应", sec_3_2: "职责分工/处置措施/紧急步骤", sec_3_3: "扩大应急/疏散路线", sec_3_4: "紧急联系电话",
          sec_4: "预警报告/应急保障", sec_4_1: "预警分级", sec_4_2: "信息报告",
          sec_5: "应急响应", sec_5_1: "响应分级", sec_5_2: "响应程序", sec_5_3: "处置措施",
          sec_6: "信息公开", sec_7: "后期处置", sec_8: "保障措施",
          sec_9: "应急预案管理", sec_9_1: "培训与演练", sec_9_2: "修订与更新",
          // 风险评估报告章节
          ch1_hazard_id: "危险有害因素辨识", ch2_summary: "辨识汇总", ch3_risk_eval: "风险等级评估", ch4_measures: "管控措施评价", ch5_conclusion: "评估结论与建议",
          // 应急资源调查报告章节
          ch1_purpose: "调查目的与依据", ch2_basic_info: "基本情况与风险", ch3_internal: "内部资源调查", ch4_external: "外部救援资源", ch5_gap_analysis: "需求与能力评估", ch6_conclusion: "调查结论与建议",
        };
        // 查找 section_key
        for (const part of parts) {
          if (part.startsWith("sec_")) {
            return SK_MAP[part] || part;
          }
        }
        if (code?.includes("_comprehensive_")) return "综合预案";
        if (code?.includes("_special_")) return "专项预案";
        if (code?.includes("_onsite_")) return "现场方案";
        if (code?.startsWith("risk_assessment_system")) return "全局";
        if (code?.startsWith("risk_assessment_section_")) return "风险评估";
        if (code?.startsWith("resource_investigation_system")) return "全局";
        if (code?.startsWith("resource_investigation_section_")) return "资源调查";
        if (code?.includes("_system")) return "全局";
        if (code?.includes("_mermaid")) return "流程图";
        if (code?.includes("_surrounding")) return "周边环境";
        return "-";
      },
    },
    {
      title: "操作", key: "actions", width: 160,
      render: (_: unknown, record: PromptTemplate) => (
        <Space>
          <Button type="link" icon={<EditOutlined />} onClick={() => handleEdit(record)}>编辑</Button>
          <Button type="link" icon={<ExperimentOutlined />} onClick={() => handleTest(record)}>测试</Button>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <PageHeader title="提示词管理" extra={<Button type="primary" onClick={handleAdd}>新增提示词</Button>} />

      <Tabs
        activeKey={activePlanType}
        onChange={setActivePlanType}
        items={PLAN_TYPES.map((t) => ({ key: t.key, label: t.label }))}
        style={{ marginBottom: 16 }}
      />

      <div style={{ marginBottom: 16 }}>
        <Select
          placeholder="按分类筛选"
          allowClear
          style={{ width: 200 }}
          value={categoryFilter}
          onChange={setCategoryFilter}
          options={CATEGORY_OPTIONS}
        />
      </div>

      <Table
        columns={columns}
        dataSource={prompts}
        rowKey="id"
        loading={isLoading}
        pagination={{ pageSize: 20 }}
      />

      {/* 编辑弹窗 */}
      <Modal
        title={editingPrompt ? "编辑提示词" : "新增提示词"}
        open={editModalOpen}
        onCancel={() => setEditModalOpen(false)}
        onOk={handleEditSubmit}
        confirmLoading={createMut.isPending || updateMut.isPending}
        width={700}
        destroyOnClose
      >
        <Form form={editForm} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item name="templateCode" label="模板编码" rules={[{ required: true, message: "请输入模板编码" }]}>
            <Input disabled={!!editingPrompt} />
          </Form.Item>
          <Form.Item name="templateName" label="模板名称" rules={[{ required: true, message: "请输入模板名称" }]}>
            <Input />
          </Form.Item>
          <Form.Item name="category" label="分类" rules={[{ required: true, message: "请选择分类" }]}>
            <Select options={CATEGORY_OPTIONS} />
          </Form.Item>
          <Form.Item name="systemPrompt" label="系统提示词">
            <TextArea rows={6} placeholder="系统级指令，定义 AI 角色与行为规则" />
          </Form.Item>
          <Form.Item name="userPromptTemplate" label="用户提示词模板">
            <TextArea rows={6} placeholder="用户消息模板，可使用 {{变量名}} 占位" />
          </Form.Item>
        </Form>
      </Modal>

      {/* 测试弹窗 */}
      <Modal
        title={`测试提示词: ${editingPrompt?.template_name || ""}`}
        open={testModalOpen}
        onCancel={() => setTestModalOpen(false)}
        footer={null}
        width={700}
        destroyOnClose
      >
        <div style={{ marginTop: 16 }}>
          <Form.Item label="输入变量 (JSON 格式)">
            <TextArea
              rows={5}
              value={testVariables}
              onChange={(e) => setTestVariables(e.target.value)}
              placeholder='{"enterprise_name": "XX化工", "hazard_type": "火灾"}'
            />
          </Form.Item>
          <Button type="primary" onClick={handleTestSubmit} loading={testing}>
            执行测试
          </Button>
          {testResult && (
            <div style={{ marginTop: 16 }}>
              <div style={{ fontWeight: 600, marginBottom: 8 }}>测试结果:</div>
              <div
                style={{
                  background: "#f5f5f5",
                  padding: 16,
                  borderRadius: 6,
                  maxHeight: 400,
                  overflow: "auto",
                  whiteSpace: "pre-wrap",
                }}
              >
                {testResult}
              </div>
            </div>
          )}
        </div>
      </Modal>
    </div>
  );
}
