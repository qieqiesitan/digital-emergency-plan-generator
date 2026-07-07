import { useState } from "react";
import { Modal, Input, Button, Upload, message, Descriptions, Collapse, Spin, Space, Tag } from "antd";
import { InboxOutlined } from "@ant-design/icons";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { parseRegulation, createRegulation } from "@/services/regulationService";
import type { RegulationParseResult } from "@/types/regulation";

const { Dragger } = Upload;
const { TextArea } = Input;

interface Props {
  open: boolean;
  onClose: () => void;
}

export function RegulationForm({ open, onClose }: Props) {
  const queryClient = useQueryClient();
  const [step, setStep] = useState<"input" | "parsing" | "preview">("input");
  const [rawText, setRawText] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [parsed, setParsed] = useState<RegulationParseResult | null>(null);

  const parseMut = useMutation({
    mutationFn: () => parseRegulation(rawText || undefined, file || undefined),
    onSuccess: (data) => { setParsed(data); setStep("preview"); },
    onError: () => message.error("解析失败，请重试"),
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
      }, file || undefined);
    },
    onSuccess: (data) => {
      message.success(data.message || "入库成功");
      queryClient.invalidateQueries({ queryKey: ["regulations"] });
      reset();
      onClose();
    },
    onError: () => message.error("入库失败"),
  });

  function reset() {
    setStep("input"); setRawText(""); setFile(null); setParsed(null);
  }

  function handleClose() { reset(); onClose(); }

  return (
    <Modal title="新增法规" open={open} onCancel={handleClose} width={700}
      footer={step === "preview" ? [
        <Button key="back" onClick={() => setStep("input")}>返回修改</Button>,
        <Button key="cancel" onClick={handleClose}>取消</Button>,
        <Button key="ok" type="primary" loading={createMut.isPending} onClick={() => createMut.mutate()}>确认入库</Button>,
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
          <Descriptions column={2} size="small" bordered>
            <Descriptions.Item label="编号">{parsed.code}</Descriptions.Item>
            <Descriptions.Item label="施行日期">{parsed.effective_date || "未提供"}</Descriptions.Item>
            <Descriptions.Item label="全称" span={2}>{parsed.full_name}</Descriptions.Item>
            <Descriptions.Item label="发布机关">{parsed.issuing_body || "未提供"}</Descriptions.Item>
            <Descriptions.Item label="替代">
              {parsed.replaces.length > 0 ? parsed.replaces.map(r => <Tag key={r}>{r}</Tag>) : "无"}
            </Descriptions.Item>
            <Descriptions.Item label="上位法依据" span={2}>
              {parsed.based_on.length > 0 ? parsed.based_on.join("、") : "未提供"}
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