import { useState, useEffect } from "react";
import { Modal, Button, Input, Table, Checkbox, message, Alert, Spin, Space, Tag } from "antd";
import {
  getResourceAIQuestions,
  generateResourcesAI,
  batchCreateResources,
  type AIQuestion,
} from "@/services/emergencyResourceService";
import type { EmergencyResourceCreate } from "@/types/emergencyResource";

interface Props {
  enterpriseId: string;
  visible: boolean;
  onClose: () => void;
  onImported: () => void;
}

type Step = "loading-questions" | "answer" | "generating" | "preview";

interface EditableItem extends EmergencyResourceCreate {
  _key: number;
  _checked: boolean;
}

export default function ResourceAIGenerateModal({ enterpriseId, visible, onClose, onImported }: Props) {
  const [step, setStep] = useState<Step>("loading-questions");
  const [questions, setQuestions] = useState<AIQuestion[]>([]);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [generatedItems, setGeneratedItems] = useState<EditableItem[]>([]);
  const [importing, setImporting] = useState(false);
  const [editingKey, setEditingKey] = useState<number | null>(null);
  const [editForm, setEditForm] = useState<Partial<EmergencyResourceCreate>>({});
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
      const qs = await getResourceAIQuestions(enterpriseId);
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
      const items = await generateResourcesAI(enterpriseId, answerList);
      if (items.length === 0) {
        message.warning("AI 未能生成应急资源，请补充更多信息后重试");
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
      message.warning("请至少勾选一个资源");
      return;
    }
    setImporting(true);
    try {
      const toImport: EmergencyResourceCreate[] = checked.map((item) => ({
        category: item.category,
        name: item.name,
        specification: item.specification,
        quantity: item.quantity,
        unit: item.unit,
        location: item.location,
        responsible_person: item.responsible_person,
        contact_phone: item.contact_phone,
        is_external: item.is_external,
        external_address: item.external_address,
        external_distance_km: item.external_distance_km,
      }));
      console.log("[AI Generate] Sending batch create:", toImport.length, "items");
      const result = await batchCreateResources(enterpriseId, toImport);
      console.log("[AI Generate] Batch create result:", result.length, "created");
      message.success(`成功导入 ${toImport.length} 个应急资源`);
      onImported();
      resetAll();
    } catch (e: any) {
      console.error("[AI Generate] Batch create failed:", e);
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
    { title: "类别", dataIndex: "category" },
    { title: "名称", dataIndex: "name" },
    { title: "规格", dataIndex: "specification", render: (v: string) => v || "-" },
    { title: "数量", dataIndex: "quantity", width: 70 },
    { title: "类型", dataIndex: "is_external", width: 70, render: (v: boolean) => v ? <Tag color="blue">外部</Tag> : <Tag>内部</Tag> },
    { title: "位置", dataIndex: "location", render: (v: string) => v || "-" },
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
      title="AI 智能生成应急资源"
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
                  生成应急资源
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
            message="请回答以下问题，帮助 AI 更准确地识别该企业的应急资源需求"
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
              如果 AI 生成的问题未覆盖您想补充的信息，可在此输入补充描述，帮助 AI 生成更准确的应急资源清单。
            </div>
            <Input.TextArea
              value={customSupplement}
              onChange={(e) => setCustomSupplement(e.target.value)}
              placeholder="例如：厂区最近新增了一条危化品生产线，需要配套防护装备..."
              rows={3}
            />
          </div>
        </div>
      )}

      {step === "generating" && (
        <div style={{ textAlign: "center", padding: 40 }}>
          <Spin size="large" />
          <p style={{ marginTop: 16 }}>AI 正在根据您的回答生成应急资源列表...</p>
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
                placeholder="资源名称"
                value={editForm.name || ""}
                onChange={(e) => setEditForm((f) => ({ ...f, name: e.target.value }))}
              />
              <Input
                placeholder="规格型号"
                value={editForm.specification || ""}
                onChange={(e) => setEditForm((f) => ({ ...f, specification: e.target.value }))}
              />
              <Input
                placeholder="位置"
                value={editForm.location || ""}
                onChange={(e) => setEditForm((f) => ({ ...f, location: e.target.value }))}
              />
            </div>
          )}
          <Alert
            type="success"
            message={`AI 生成了 ${generatedItems.length} 个应急资源，可勾选、编辑或删除后确认导入`}
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
