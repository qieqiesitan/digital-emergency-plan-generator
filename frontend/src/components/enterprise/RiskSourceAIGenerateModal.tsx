import { useState, useEffect } from "react";
import { Modal, Button, Input, Table, Checkbox, message, Alert, Spin, Space, Tag } from "antd";
import {
  getRiskSourceAIQuestions,
  generateRiskSourcesAI,
  batchCreateRiskSources,
  type AIQuestion,
} from "@/services/riskSourceService";
import type { RiskSourceCreate } from "@/types/riskSource";

interface Props {
  enterpriseId: string;
  visible: boolean;
  onClose: () => void;
  onImported: () => void;
}

type Step = "loading-questions" | "answer" | "generating" | "preview";

interface EditableItem extends RiskSourceCreate {
  _key: number;
  _checked: boolean;
}

export default function RiskSourceAIGenerateModal({ enterpriseId, visible, onClose, onImported }: Props) {
  const [step, setStep] = useState<Step>("loading-questions");
  const [questions, setQuestions] = useState<AIQuestion[]>([]);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [generatedItems, setGeneratedItems] = useState<EditableItem[]>([]);
  const [importing, setImporting] = useState(false);
  const [editingKey, setEditingKey] = useState<number | null>(null);
  const [editForm, setEditForm] = useState<Partial<RiskSourceCreate>>({});
  // 用户自行补充描述
  const [customSupplement, setCustomSupplement] = useState("");

  useEffect(() => {
    if (visible) {
      loadQuestions();
    }
  }, [visible, enterpriseId]);

  const loadQuestions = async () => {
    setStep("loading-questions");
    try {
      const qs = await getRiskSourceAIQuestions(enterpriseId);
      if (qs.length === 0) {
        message.error("未能生成调查问题，请重试");
        onClose();
        return;
      }
      setQuestions(qs);
      setAnswers({});
      setCustomSupplement("");
      setStep("answer");
    } catch {
      message.error("AI 服务暂不可用，请检查 AI 配置");
      onClose();
    }
  };

  const handleGenerate = async () => {
    setStep("generating");
    try {
      const answerList = questions.map((q) => ({
        question_id: q.id,
        question: q.question,
        answer: answers[q.id] || "",
      }));
      // 追加用户自行补充的描述
      if (customSupplement.trim()) {
        answerList.push({
          question_id: "custom",
          question: "补充描述",
          answer: customSupplement.trim(),
        });
      }
      const items = await generateRiskSourcesAI(enterpriseId, answerList);
      if (items.length === 0) {
        message.warning("AI 未能生成风险源，请补充更多信息后重试");
        setStep("answer");
        return;
      }
      setGeneratedItems(
        items.map((item, i) => ({ ...item, _key: i, _checked: true })),
      );
      setStep("preview");
    } catch {
      message.error("AI 生成失败，请重试");
      setStep("answer");
    }
  };

  const handleImport = async () => {
    const checked = generatedItems.filter((i) => i._checked);
    if (checked.length === 0) {
      message.warning("请至少勾选一个风险源");
      return;
    }
    setImporting(true);
    try {
      const toImport: RiskSourceCreate[] = checked.map((item) => ({
        categories: item.categories,
        name: item.name,
        location: item.location,
        location_x: item.location_x,
        location_y: item.location_y,
        description: item.description,
        likelihood: item.likelihood,
        severity: item.severity,
        control_measures: item.control_measures,
      }));
      console.log("[AI Generate Risk] Sending batch create:", toImport.length, "items");
      const result = await batchCreateRiskSources(enterpriseId, toImport);
      console.log("[AI Generate Risk] Batch create result:", result.length, "created");
      message.success(`成功导入 ${toImport.length} 个风险源`);
      onImported();
      resetAll();
    } catch (e: any) {
      console.error("[AI Generate Risk] Batch create failed:", e);
      const detail = e?.response?.data?.detail || e?.message || String(e);
      message.error(`导入失败: ${detail}`);
    } finally {
      setImporting(false);
    }
  };

  const toggleCheck = (key: number) => {
    setGeneratedItems((prev) =>
      prev.map((i) => (i._key === key ? { ...i, _checked: !i._checked } : i)),
    );
  };

  const startEdit = (record: EditableItem) => {
    setEditingKey(record._key);
    setEditForm({ ...record });
  };

  const saveEdit = () => {
    if (editingKey == null) return;
    setGeneratedItems((prev) =>
      prev.map((i) => (i._key === editingKey ? { ...i, ...editForm } : i)),
    );
    setEditingKey(null);
    setEditForm({});
  };

  const deleteItem = (key: number) => {
    setGeneratedItems((prev) => prev.filter((i) => i._key !== key));
  };

  const resetAll = () => {
    setStep("loading-questions");
    setQuestions([]);
    setAnswers({});
    setGeneratedItems([]);
    setEditingKey(null);
    setCustomSupplement("");
    onClose();
  };

  const previewColumns = [
    {
      title: "",
      dataIndex: "_checked",
      width: 40,
      render: (v: boolean, record: EditableItem) => (
        <Checkbox checked={v} onChange={() => toggleCheck(record._key)} />
      ),
    },
    {
      title: "风险类别",
      dataIndex: "categories",
      render: (cats: string[]) => (
        <Space size={4} wrap>
          {cats?.map((c) => (
            <Tag key={c} color="orange">{c}</Tag>
          ))}
        </Space>
      ),
    },
    { title: "风险名称", dataIndex: "name" },
    { title: "位置", dataIndex: "location", render: (v: string) => v || "-" },
    { title: "可能性", dataIndex: "likelihood", width: 80, render: (v: string) => v || "中" },
    { title: "严重性", dataIndex: "severity", width: 80, render: (v: string) => v || "中" },
    { title: "描述", dataIndex: "description", ellipsis: true, render: (v: string) => v || "-" },
    {
      title: "操作",
      width: 140,
      render: (_: unknown, record: EditableItem) =>
        editingKey === record._key ? (
          <Space>
            <Button size="small" type="link" onClick={saveEdit}>保存</Button>
            <Button size="small" type="link" onClick={() => setEditingKey(null)}>取消</Button>
          </Space>
        ) : (
          <Space>
            <Button size="small" type="link" onClick={() => startEdit(record)}>编辑</Button>
            <Button size="small" type="link" danger onClick={() => deleteItem(record._key)}>删除</Button>
          </Space>
        ),
    },
  ];

  return (
    <Modal
      title="AI 智能生成风险源"
      open={visible}
      onCancel={resetAll}
      width={950}
      footer={
        step === "preview"
          ? [
              <Button key="back" onClick={resetAll}>取消</Button>,
              <Button key="import" type="primary" loading={importing} onClick={handleImport}>
                确认导入 ({generatedItems.filter((i) => i._checked).length} 条)
              </Button>,
            ]
          : step === "answer"
            ? [
                <Button key="cancel" onClick={resetAll}>取消</Button>,
                <Button key="generate" type="primary" onClick={handleGenerate}>
                  生成风险源
                </Button>,
              ]
            : null
      }
    >
      {step === "loading-questions" && (
        <div style={{ textAlign: "center", padding: 40 }}>
          <Spin size="large" />
          <p style={{ marginTop: 16 }}>AI 正在分析企业档案，生成针对性调查问题...</p>
        </div>
      )}

      {step === "answer" && (
        <div>
          <Alert
            type="info"
            message="请回答以下问题，帮助 AI 更准确地识别该企业的风险源"
            style={{ marginBottom: 16 }}
            showIcon
          />
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            {questions.map((q) => (
              <div key={q.id}>
                <div style={{ fontWeight: 500, marginBottom: 4 }}>{q.question}</div>
                <Input.TextArea
                  value={answers[q.id] || ""}
                  onChange={(e) => setAnswers((prev) => ({ ...prev, [q.id]: e.target.value }))}
                  placeholder="请输入您的回答..."
                  rows={2}
                />
              </div>
            ))}
          </div>

          <div style={{ marginTop: 20 }}>
            <div style={{ fontWeight: 500, marginBottom: 6, color: "#595959" }}>
              自行补充描述（选填）
            </div>
            <div style={{ fontSize: 12, color: "#999", marginBottom: 8 }}>
              如果 AI 生成的问题未覆盖您想补充的信息，可在此输入补充描述，帮助 AI 生成更准确的风险源清单。
            </div>
            <Input.TextArea
              value={customSupplement}
              onChange={(e) => setCustomSupplement(e.target.value)}
              placeholder="例如：我司还有一个地下仓库，存放有大量化工原料..."
              rows={3}
            />
          </div>
        </div>
      )}

      {step === "generating" && (
        <div style={{ textAlign: "center", padding: 40 }}>
          <Spin size="large" />
          <p style={{ marginTop: 16 }}>AI 正在根据您的回答生成风险源列表...</p>
        </div>
      )}

      {step === "preview" && (
        <div>
          {editingKey != null && (
            <div
              style={{
                marginBottom: 12,
                padding: 12,
                border: "1px solid #d9d9d9",
                borderRadius: 6,
                display: "flex",
                flexDirection: "column",
                gap: 8,
              }}
            >
              <Input
                placeholder="风险名称"
                value={editForm.name || ""}
                onChange={(e) => setEditForm((f) => ({ ...f, name: e.target.value }))}
              />
              <Input
                placeholder="位置"
                value={editForm.location || ""}
                onChange={(e) => setEditForm((f) => ({ ...f, location: e.target.value }))}
              />
              <Input.TextArea
                placeholder="风险描述"
                value={editForm.description || ""}
                rows={2}
                onChange={(e) => setEditForm((f) => ({ ...f, description: e.target.value }))}
              />
            </div>
          )}
          <Alert
            type="success"
            message={`AI 生成了 ${generatedItems.length} 个风险源，可勾选、编辑或删除后确认导入`}
            style={{ marginBottom: 12 }}
            showIcon
          />
          <Table
            dataSource={generatedItems}
            rowKey="_key"
            columns={previewColumns}
            pagination={false}
            size="small"
            scroll={{ y: 400 }}
          />
        </div>
      )}
    </Modal>
  );
}
