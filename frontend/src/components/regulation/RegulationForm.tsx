import { useState, useEffect } from "react";
import { Modal, Input, Button, Upload, Select, Form, message, Descriptions, Collapse, Spin, Space, Tag, Alert, AutoComplete } from "antd";
import { InboxOutlined, UploadOutlined } from "@ant-design/icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { parseRegulation, createRegulation, updateRegulation, checkDuplicate, fetchRegulations } from "@/services/regulationService";
import type { RegulationParseResult, DuplicateCheckResponse } from "@/types/regulation";

const { Dragger } = Upload;
const { TextArea } = Input;

interface Props {
  open: boolean;
  onClose: () => void;
  regulation?: RegulationNode | null;
  onSaved?: () => void;
}

const EMPTY_FIELD_STYLE: React.CSSProperties = { background: "#fffbe6", border: "1px solid #fadb14" };

function isBlank(v: string | string[] | undefined | null): boolean {
  if (v == null) return true;
  if (Array.isArray(v)) return v.length === 0;
  return String(v).trim() === "";
}

export function RegulationForm({ open, onClose, regulation, onSaved }: Props) {
  const isEdit = !!regulation;
  const queryClient = useQueryClient();
  const [step, setStep] = useState<"input" | "parsing" | "preview">("input");
  const [rawText, setRawText] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [parsed, setParsed] = useState<RegulationParseResult | null>(null);
  const [dupResult, setDupResult] = useState<DuplicateCheckResponse | null>(null);
  const [dupLoading, setDupLoading] = useState(false);
  const [editFile, setEditFile] = useState<File | null>(null);

  // Edit mode form fields
  const [editCode, setEditCode] = useState("");
  const [editFullName, setEditFullName] = useState("");
  const [editNodeType, setEditNodeType] = useState("standard");
  const [editStatus, setEditStatus] = useState("current");
  const [editVersion, setEditVersion] = useState("");
  const [editIssuingBody, setEditIssuingBody] = useState("");
  const [editEffectiveDate, setEditEffectiveDate] = useState("");
  const [editTopics, setEditTopics] = useState("");

  // Initialize edit fields from regulation prop
  useEffect(() => {
    if (regulation && open) {
      setEditCode(regulation.code || "");
      setEditFullName(regulation.full_name || "");
      setEditNodeType(regulation.node_type || "standard");
      setEditStatus(regulation.status || "current");
      setEditVersion(regulation.version || "");
      setEditIssuingBody(regulation.issuing_body || "");
      setEditEffectiveDate(regulation.effective_date || "");
      setEditTopics((regulation.topics || []).join(", "));
      setEditFile(null);
    }
  }, [regulation, open]);

  // Fetch all regulation codes for AutoComplete
  const { data: allRegs } = useQuery({
    queryKey: ["regulations", "", "all", "all", 1],
    queryFn: () => fetchRegulations({ page_size: 100 }),
    enabled: open,
  });
  const codeOptions = (allRegs?.items || [])
    .map(r => r.code)
    .filter((c, i, arr) => c && arr.indexOf(c) === i)
    .map(c => ({ value: c }));

  const parseMut = useMutation({
    mutationFn: () => parseRegulation(rawText || undefined, file || undefined),
    onSuccess: (data) => { setParsed(data); setStep("preview"); },
    onError: (err: any) => message.error(err?.response?.data?.detail || err?.message || "解析失败，请重试"),
  });

  const updateMut = useMutation({
    mutationFn: () => {
      if (!regulation) throw new Error("no regulation");
      return updateRegulation(regulation.id, {
        code: editCode,
        full_name: editFullName,
        status: editStatus,
        version: editVersion,
        issuing_body: editIssuingBody,
        effective_date: editEffectiveDate,
        topics: editTopics.split(",").map(t => t.trim()).filter(Boolean),
      }, editFile || undefined);
    },
    onSuccess: () => {
      message.success("法规已更新");
      queryClient.invalidateQueries({ queryKey: ["regulations"] });
      handleClose();
    },
    onError: (err: any) => message.error(err?.response?.data?.detail || err?.message || "更新失败"),
  });

  const createMut = useMutation({
    mutationFn: () => {
      if (!parsed) throw new Error("no data");
      return createRegulation({
        code: parsed.code,
        full_name: parsed.full_name,
        issuing_body: parsed.issuing_body,
        issue_date: parsed.issue_date,
        effective_date: parsed.effective_date,
        replaces: parsed.replaces,
        based_on: parsed.based_on,
        topics: parsed.topics,
        articles: parsed.articles,
        node_type: parsed.node_type || "standard",
        version: parsed.version || "",
      }, file || undefined, hasDuplicate);
    },
    onSuccess: (data) => {
      message.success(data.message || "入库成功");
      queryClient.invalidateQueries({ queryKey: ["regulations"] });
      reset();
      onClose();
    },
    onError: (err: any) => {
      const detail = err?.response?.data?.detail || err?.message || "入库失败";
      message.error(detail);
    },
  });

  // Auto check duplicate when entering preview
  useEffect(() => {
    if (step === "preview" && parsed) {
      setDupLoading(true);
      setDupResult(null);
      checkDuplicate(parsed.code, parsed.full_name, rawText)
        .then(setDupResult)
        .catch(() => setDupResult(null))
        .finally(() => setDupLoading(false));
    } else {
      setDupResult(null);
    }
  }, [step, parsed]);

  function reset() {
    setStep("input"); setRawText(""); setFile(null); setParsed(null); setDupResult(null);
  }

  function handleClose() {
    reset(); onClose();
    if (onSaved) onSaved();
  }

  function handleEditSave() {
    updateMut.mutate();
  }

  const hasDuplicate = dupResult?.duplicate && dupResult.matches.length > 0;

  if (isEdit) {
    return (
      <Modal title="编辑法规" open={open} onCancel={handleClose} width={700}
        footer={[
          <Button key="cancel" onClick={handleClose}>取消</Button>,
          <Button key="save" type="primary" loading={updateMut.isPending}
            disabled={!editCode.trim() && !editFullName.trim()}
            onClick={handleEditSave}>保存</Button>,
        ]}
      >
        <Descriptions column={2} size="small" bordered>
          <Descriptions.Item label="编号">
            <Input size="small" variant="borderless" value={editCode}
              onChange={e => setEditCode(e.target.value)} placeholder="如 GB/T 29639-2020" />
          </Descriptions.Item>
          <Descriptions.Item label="状态">
            <Select size="small" variant="borderless" value={editStatus} onChange={v => setEditStatus(v)}
              style={{ width: "100%" }}
              options={[{ label: "现行", value: "current" }, { label: "已废止", value: "abolished" }]} />
          </Descriptions.Item>
          <Descriptions.Item label="全称" span={2}>
            <Input size="small" variant="borderless" value={editFullName}
              onChange={e => setEditFullName(e.target.value)} placeholder="法规完整名称" />
          </Descriptions.Item>
          <Descriptions.Item label="类型">
            <Select size="small" variant="borderless" value={editNodeType} onChange={v => setEditNodeType(v)}
              style={{ width: "100%" }}
              options={[{ label: "法律", value: "law" }, { label: "标准", value: "standard" }, { label: "政策", value: "policy" }]} />
          </Descriptions.Item>
          <Descriptions.Item label="版本">
            <Input size="small" variant="borderless" value={editVersion}
              onChange={e => setEditVersion(e.target.value)} placeholder="如 2021年修正" />
          </Descriptions.Item>
          <Descriptions.Item label="发布机关">
            <Input size="small" variant="borderless" value={editIssuingBody}
              onChange={e => setEditIssuingBody(e.target.value)} placeholder="发布机关" />
          </Descriptions.Item>
          <Descriptions.Item label="施行日期">
            <Input size="small" variant="borderless" value={editEffectiveDate}
              onChange={e => setEditEffectiveDate(e.target.value)} placeholder="如 2021-09-01" />
          </Descriptions.Item>
          <Descriptions.Item label="主题标签" span={2}>
            <Input size="small" variant="borderless" value={editTopics}
              onChange={e => setEditTopics(e.target.value)} placeholder="逗号分隔，如 应急管理, 预案编制, 风险评估" />
          </Descriptions.Item>
        </Descriptions>

        <div style={{ marginTop: 16 }}>
          <Upload maxCount={1} accept=".md,.txt,.pdf,.docx,.doc"
            beforeUpload={f => { setEditFile(f); return false; }}
            onRemove={() => setEditFile(null)}
            fileList={editFile ? [{ uid: "-1", name: editFile.name, status: "done" } as any] : []}>
            <Button icon={<UploadOutlined />} size="small">更新法规文件（可选）</Button>
          </Upload>
        </div>
      </Modal>
    );
  }

  return (
    <Modal title={isEdit ? "编辑法规" : "新增法规"} open={open} onCancel={handleClose} width={700}
      footer={step === "preview" ? [
        <Button key="back" onClick={() => setStep("input")}>返回修改</Button>,
        <Button key="cancel" onClick={handleClose}>取消</Button>,
        <Button
          key="ok"
          type={hasDuplicate ? "default" : "primary"}
          danger={hasDuplicate}
          loading={createMut.isPending}
          onClick={() => createMut.mutate()}
        >
          {hasDuplicate ? "仍要入库（已存在相似法规）" : "确认入库"}
        </Button>,
      ] : step === "parsing" ? null : [
        <Button key="cancel" onClick={handleClose}>取消</Button>,
        <Button key="parse" type="primary" loading={parseMut.isPending}
          disabled={!rawText.trim() && !file}
          onClick={() => { setStep("parsing"); parseMut.mutate(); }}>自动解析结构 →</Button>,
      ]}
    >
      {step === "input" && (
        <div>
          <p style={{ marginBottom: 8, color: "#666" }}>方式一：粘贴全文</p>
          <TextArea rows={8} placeholder="将法规全文粘贴到这里..." value={rawText}
            onChange={e => setRawText(e.target.value)} />
          <p style={{ margin: "16px 0 8px", color: "#666" }}>方式二：上传文件</p>
          <Dragger maxCount={1} accept=".pdf,.docx,.doc" beforeUpload={f => { setFile(f); return false; }}
            onRemove={() => setFile(null)} fileList={file ? [{ uid: "-1", name: file.name, status: "done" }] : []}>
            <p className="ant-upload-drag-icon"><InboxOutlined /></p>
            <p>点击或拖拽 PDF / Word 文件到此区域</p>
            <p style={{ color: "#999", fontSize: 12 }}>支持 .pdf .docx .doc，限 10MB</p>
          </Dragger>
        </div>
      )}

      {step === "parsing" && (
        <div style={{ textAlign: "center", padding: 40 }}>
          <Spin size="large" />
          <p style={{ marginTop: 16 }}>AI 正在解析法规结构...</p>
        </div>
      )}

      {step === "preview" && parsed && (
        <div>
          {/* Duplicate check result */}
          {dupLoading && (
            <Alert type="info" title="正在检查重复法规..." style={{ marginBottom: 12 }} />
          )}
          {!dupLoading && dupResult && !hasDuplicate && (
            <Alert type="success" title="✓ 未发现重复法规" style={{ marginBottom: 12 }} />
          )}
          {!dupLoading && hasDuplicate && (
            <Alert
              type="error"
              title="存在疑似重复法规"
              description={
                <ul style={{ margin: 0, paddingLeft: 18 }}>
                  {dupResult.matches.map((d, i) => (
                    <li key={i}>
                      <strong>{d.code}</strong> — {d.full_name}
                      <Tag color="orange" style={{ marginLeft: 8 }}>相似度 {Math.round(d.similarity * 100)}%</Tag>
                    </li>
                  ))}
                </ul>
              }
              style={{ marginBottom: 12 }}
            />
          )}

          <Descriptions column={2} size="small" bordered>
            <Descriptions.Item label="编号">
              <span style={isBlank(parsed.code) ? EMPTY_FIELD_STYLE : undefined}>
                <AutoComplete
                  options={codeOptions}
                  value={parsed.code || ""}
                  style={{ width: "100%" }}
                  placeholder="请填写编号"
                  onChange={(v) => setParsed(p => p ? { ...p, code: v } : null)}
                  variant={isBlank(parsed.code) ? undefined : "borderless"}
                />
              </span>
              {isBlank(parsed.code) && <Tag color="gold" style={{ marginLeft: 4 }}>待填写</Tag>}
            </Descriptions.Item>
            <Descriptions.Item label="施行日期">
              <span style={isBlank(parsed.effective_date) ? EMPTY_FIELD_STYLE : undefined}>
                {parsed.effective_date || "未提供"}
              </span>
              {isBlank(parsed.effective_date) && <Tag color="gold" style={{ marginLeft: 4 }}>待填写</Tag>}
            </Descriptions.Item>
            <Descriptions.Item label="全称" span={2}>
              <span style={isBlank(parsed.full_name) ? EMPTY_FIELD_STYLE : undefined}>
                {parsed.full_name || "未提供"}
              </span>
              {isBlank(parsed.full_name) && <Tag color="gold" style={{ marginLeft: 4 }}>待填写</Tag>}
            </Descriptions.Item>
            <Descriptions.Item label="发布机关">
              <span style={isBlank(parsed.issuing_body) ? EMPTY_FIELD_STYLE : undefined}>
                {parsed.issuing_body || "未提供"}
              </span>
              {isBlank(parsed.issuing_body) && <Tag color="gold" style={{ marginLeft: 4 }}>待填写</Tag>}
            </Descriptions.Item>
            <Descriptions.Item label="替代">
              {parsed.replaces.length > 0 ? parsed.replaces.map(r => <Tag key={r}>{r}</Tag>) : "无"}
            </Descriptions.Item>
            <Descriptions.Item label="上位法依据" span={2}>
              <span style={isBlank(parsed.based_on) ? EMPTY_FIELD_STYLE : undefined}>
                {parsed.based_on.length > 0 ? parsed.based_on.join("、") : "未提供"}
              </span>
              {isBlank(parsed.based_on) && <Tag color="gold" style={{ marginLeft: 4 }}>待填写</Tag>}
            </Descriptions.Item>
            <Descriptions.Item label="主题标签" span={2}>
              {parsed.topics.length > 0 ? parsed.topics.map(t => <Tag key={t} color="blue">{t}</Tag>) : "无"}
            </Descriptions.Item>
          </Descriptions>
          <p style={{ marginTop: 16, fontWeight: 500 }}>条文清单（{parsed.article_count} 条）</p>
          <Collapse items={parsed.articles.slice(0, 20).map(a => ({
            key: a.number, label: a.number,
            children: <p style={{ whiteSpace: "pre-wrap" }}>{a.text}</p>,
          }))} />
          {parsed.articles.length > 20 && <p style={{ color: "#999", marginTop: 8 }}>...还有 {parsed.articles.length - 20} 条，入库后可在详情页查看</p>}
        </div>
      )}
    </Modal>
  );
}
