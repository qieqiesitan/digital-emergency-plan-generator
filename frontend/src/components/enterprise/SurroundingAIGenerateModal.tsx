import { useState, useEffect } from "react";
import { Modal, Button, Input, Table, message, Alert, Spin, Space, Tag, Card, Select, InputNumber } from "antd";
import { DeleteOutlined } from "@ant-design/icons";
import {
  getSurroundingAIQuestions,
  generateSurroundingAI,
  updateSurrounding,
} from "@/services/enterpriseService";
import type { SurroundingInfo, NearbyUnit, SensitiveTarget } from "@/types/enterprise";

interface Props {
  enterpriseId: string;
  existingSurrounding: SurroundingInfo;
  visible: boolean;
  onClose: () => void;
  onImported: () => void;
}

type Step = "loading-questions" | "answer" | "generating" | "preview";

interface AIQuestion {
  id: string;
  question: string;
}

interface EditableNearby extends NearbyUnit {
  _key: string;
  _isNew: boolean;
}

interface EditableTarget extends SensitiveTarget {
  _key: string;
  _isNew: boolean;
}

const DIRECTIONS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"];

export default function SurroundingAIGenerateModal({
  enterpriseId,
  existingSurrounding,
  visible,
  onClose,
  onImported,
}: Props) {
  const [step, setStep] = useState<Step>("loading-questions");
  const [questions, setQuestions] = useState<AIQuestion[]>([]);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [customSupplement, setCustomSupplement] = useState("");
  const [saving, setSaving] = useState(false);

  // Preview state - merged existing + generated
  const [nearbyUnits, setNearbyUnits] = useState<EditableNearby[]>([]);
  const [sensitiveTargets, setSensitiveTargets] = useState<EditableTarget[]>([]);
  const [trafficInfo, setTrafficInfo] = useState("");

  useEffect(() => {
    if (visible) {
      loadQuestions();
    }
  }, [visible, enterpriseId]);

  const loadQuestions = async () => {
    setStep("loading-questions");
    try {
      const qs = await getSurroundingAIQuestions(enterpriseId);
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
      if (customSupplement.trim()) {
        answerList.push({
          question_id: "custom",
          question: "补充描述",
          answer: customSupplement.trim(),
        });
      }
      const generated = await generateSurroundingAI(enterpriseId, answerList);

      // Merge existing + generated with _key and _isNew markers
      const existingUnits: EditableNearby[] = (existingSurrounding.nearby_units || []).map(
        (u, i) => ({ ...u, _key: `existing-unit-${i}`, _isNew: false }),
      );
      const generatedUnits: EditableNearby[] = generated.nearby_units.map((u, i) => ({
        ...u,
        _key: `generated-unit-${i}`,
        _isNew: true,
      }));

      const existingTargets: EditableTarget[] = (existingSurrounding.sensitive_targets || []).map(
        (t, i) => ({ ...t, _key: `existing-target-${i}`, _isNew: false }),
      );
      const generatedTargets: EditableTarget[] = generated.sensitive_targets.map((t, i) => ({
        ...t,
        _key: `generated-target-${i}`,
        _isNew: true,
      }));

      setNearbyUnits([...existingUnits, ...generatedUnits]);
      setSensitiveTargets([...existingTargets, ...generatedTargets]);
      setTrafficInfo(generated.traffic_info || existingSurrounding.traffic_info || "");
      setStep("preview");
    } catch {
      message.error("AI 生成失败，请重试");
      setStep("answer");
    }
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const toSave: SurroundingInfo = {
        nearby_units: nearbyUnits.map(({ _key, _isNew, ...rest }) => rest),
        sensitive_targets: sensitiveTargets.map(({ _key, _isNew, ...rest }) => rest),
        traffic_info: trafficInfo,
      };
      await updateSurrounding(enterpriseId, toSave);
      message.success("周边环境已更新");
      onImported();
      resetAll();
    } catch {
      message.error("保存失败");
    } finally {
      setSaving(false);
    }
  };

  const resetAll = () => {
    setStep("loading-questions");
    setQuestions([]);
    setAnswers({});
    setCustomSupplement("");
    setNearbyUnits([]);
    setSensitiveTargets([]);
    setTrafficInfo("");
    onClose();
  };

  // --- Nearby units editing helpers ---
  const updateNearby = (key: string, field: string, value: unknown) => {
    setNearbyUnits((prev) =>
      prev.map((u) => (u._key === key ? { ...u, [field]: value } : u)),
    );
  };

  const deleteNearby = (key: string) => {
    setNearbyUnits((prev) => prev.filter((u) => u._key !== key));
  };

  // --- Sensitive targets editing helpers ---
  const updateTarget = (key: string, field: string, value: unknown) => {
    setSensitiveTargets((prev) =>
      prev.map((t) => (t._key === key ? { ...t, [field]: value } : t)),
    );
  };

  const deleteTarget = (key: string) => {
    setSensitiveTargets((prev) => prev.filter((t) => t._key !== key));
  };

  return (
    <Modal
      title="AI 智能生成周边环境"
      open={visible}
      onCancel={resetAll}
      width={960}
      footer={
        step === "preview"
          ? [
              <Button key="back" onClick={resetAll}>
                取消
              </Button>,
              <Button key="save" type="primary" loading={saving} onClick={handleSave}>
                确认保存（{nearbyUnits.length} 个周边单位，{sensitiveTargets.length} 个敏感目标）
              </Button>,
            ]
          : step === "answer"
            ? [
                <Button key="cancel" onClick={resetAll}>
                  取消
                </Button>,
                <Button key="generate" type="primary" onClick={handleGenerate}>
                  生成周边环境
                </Button>,
              ]
            : null
      }
    >
      {step === "loading-questions" && (
        <div style={{ textAlign: "center", padding: 40 }}>
          <Spin size="large" />
          <p style={{ marginTop: 16 }}>AI 正在分析企业档案，生成周边环境调查问题...</p>
        </div>
      )}

      {step === "answer" && (
        <div>
          <Alert
            type="info"
            message="请回答以下问题，帮助 AI 全面了解该企业的周边环境"
            style={{ marginBottom: 16 }}
            showIcon
          />
          <div style={{ display: "flex", flexDirection: "column", gap: 16, maxHeight: "50vh", overflow: "auto" }}>
            {questions.map((q) => (
              <div key={q.id}>
                <div style={{ fontWeight: 500, marginBottom: 4 }}>{q.question}</div>
                <Input.TextArea
                  value={answers[q.id] || ""}
                  onChange={(e) =>
                    setAnswers((prev) => ({ ...prev, [q.id]: e.target.value }))
                  }
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
              如果 AI 生成的问题未覆盖您想补充的信息，可在此输入补充描述。
            </div>
            <Input.TextArea
              value={customSupplement}
              onChange={(e) => setCustomSupplement(e.target.value)}
              placeholder="例如：厂区北侧有一条季节性河流，雨季需关注防汛..."
              rows={3}
            />
          </div>
        </div>
      )}

      {step === "generating" && (
        <div style={{ textAlign: "center", padding: 40 }}>
          <Spin size="large" />
          <p style={{ marginTop: 16 }}>AI 正在根据您的回答生成周边环境信息...</p>
        </div>
      )}

      {step === "preview" && (
        <div>
          <Alert
            type="success"
            message="AI 已生成周边环境信息，可编辑或删除后确认保存。蓝色标记项为新增数据。"
            style={{ marginBottom: 12 }}
            showIcon
          />

          {/* Nearby Units */}
          <Card title="周边单位" size="small" style={{ marginBottom: 12 }}>
            <Table
              dataSource={nearbyUnits}
              rowKey="_key"
              pagination={false}
              size="small"
              scroll={{ y: 240 }}
              columns={[
                {
                  title: "名称",
                  dataIndex: "name",
                  width: 180,
                  render: (v: string, record: EditableNearby) => (
                    <Input
                      size="small"
                      value={v}
                      onChange={(e) => updateNearby(record._key, "name", e.target.value)}
                      prefix={record._isNew ? <Tag color="blue" style={{ marginRight: 4 }}>新</Tag> : undefined}
                    />
                  ),
                },
                {
                  title: "方位",
                  dataIndex: "direction",
                  width: 100,
                  render: (v: string, record: EditableNearby) => (
                    <Select
                      size="small"
                      value={v}
                      onChange={(val) => updateNearby(record._key, "direction", val)}
                      options={DIRECTIONS.map((d) => ({ value: d, label: d }))}
                      style={{ width: "100%" }}
                    />
                  ),
                },
                {
                  title: "距离(m)",
                  dataIndex: "distance_m",
                  width: 100,
                  render: (v: number, record: EditableNearby) => (
                    <InputNumber
                      size="small"
                      value={v}
                      onChange={(val) => updateNearby(record._key, "distance_m", val || 0)}
                      style={{ width: "100%" }}
                    />
                  ),
                },
                {
                  title: "主要风险",
                  dataIndex: "main_risk",
                  render: (v: string, record: EditableNearby) => (
                    <Input
                      size="small"
                      value={v}
                      onChange={(e) => updateNearby(record._key, "main_risk", e.target.value)}
                    />
                  ),
                },
                {
                  title: "标记",
                  width: 70,
                  render: (_: unknown, record: EditableNearby) =>
                    record._isNew ? <Tag color="blue">新增</Tag> : <Tag>已有</Tag>,
                },
                {
                  title: "",
                  width: 40,
                  render: (_: unknown, record: EditableNearby) => (
                    <Button
                      type="text"
                      size="small"
                      danger
                      icon={<DeleteOutlined />}
                      onClick={() => deleteNearby(record._key)}
                    />
                  ),
                },
              ]}
            />
          </Card>

          {/* Sensitive Targets */}
          <Card title="敏感目标" size="small" style={{ marginBottom: 12 }}>
            <Table
              dataSource={sensitiveTargets}
              rowKey="_key"
              pagination={false}
              size="small"
              scroll={{ y: 240 }}
              columns={[
                {
                  title: "名称",
                  dataIndex: "name",
                  width: 180,
                  render: (v: string, record: EditableTarget) => (
                    <Input
                      size="small"
                      value={v}
                      onChange={(e) => updateTarget(record._key, "name", e.target.value)}
                      prefix={record._isNew ? <Tag color="blue" style={{ marginRight: 4 }}>新</Tag> : undefined}
                    />
                  ),
                },
                {
                  title: "方位",
                  dataIndex: "direction",
                  width: 100,
                  render: (v: string, record: EditableTarget) => (
                    <Select
                      size="small"
                      value={v}
                      onChange={(val) => updateTarget(record._key, "direction", val)}
                      options={DIRECTIONS.map((d) => ({ value: d, label: d }))}
                      style={{ width: "100%" }}
                    />
                  ),
                },
                {
                  title: "距离(m)",
                  dataIndex: "distance_m",
                  width: 100,
                  render: (v: number, record: EditableTarget) => (
                    <InputNumber
                      size="small"
                      value={v}
                      onChange={(val) => updateTarget(record._key, "distance_m", val || 0)}
                      style={{ width: "100%" }}
                    />
                  ),
                },
                {
                  title: "类型",
                  dataIndex: "type",
                  render: (v: string, record: EditableTarget) => (
                    <Input
                      size="small"
                      value={v}
                      onChange={(e) => updateTarget(record._key, "type", e.target.value)}
                    />
                  ),
                },
                {
                  title: "标记",
                  width: 70,
                  render: (_: unknown, record: EditableTarget) =>
                    record._isNew ? <Tag color="blue">新增</Tag> : <Tag>已有</Tag>,
                },
                {
                  title: "",
                  width: 40,
                  render: (_: unknown, record: EditableTarget) => (
                    <Button
                      type="text"
                      size="small"
                      danger
                      icon={<DeleteOutlined />}
                      onClick={() => deleteTarget(record._key)}
                    />
                  ),
                },
              ]}
            />
          </Card>

          {/* Traffic Info */}
          <Card title="交通状况" size="small">
            <Input.TextArea
              value={trafficInfo}
              onChange={(e) => setTrafficInfo(e.target.value)}
              rows={3}
            />
          </Card>
        </div>
      )}
    </Modal>
  );
}
