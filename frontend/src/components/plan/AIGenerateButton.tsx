import { useState, useCallback, useRef } from "react";
import { Button, Alert, Modal, Form, Input, Tag, Typography } from "antd";
import { RobotOutlined, LoadingOutlined, CheckCircleOutlined } from "@ant-design/icons";
import { generateSectionStream, stopGeneration, regenerateSelectionStream } from "@/services/generationService";
import { getAIConfig } from "@/services/aiConfigService";
import { getQuickPrompts } from "@/utils/quickPrompts";

const { Text } = Typography;

interface AIGenerateButtonProps {
  planId: string;
  sectionKey: string;
  sectionTitle?: string;
  onContentChunk: (chunk: string) => void;
  onGenerateComplete: (fullText: string) => void;
  disabled?: boolean;
  mode?: "full" | "selection";
  selectedText?: string;
  contextBefore?: string;
  contextAfter?: string;
}

type GenStatus = "idle" | "loading" | "done" | "error";

export default function AIGenerateButton({
  planId, sectionKey, sectionTitle, onContentChunk, onGenerateComplete, disabled,
  mode = "full", selectedText, contextBefore, contextAfter,
}: AIGenerateButtonProps) {
  const [status, setStatus] = useState<GenStatus>("idle");
  const [errorMsg, setErrorMsg] = useState("");
  const [modalOpen, setModalOpen] = useState(false);
  const controllerRef = useRef<AbortController | null>(null);
  const fullTextRef = useRef("");
  const [form] = Form.useForm();

  const checkConfig = useCallback(async (): Promise<boolean> => {
    try {
      const config = await getAIConfig();
      if (!config) {
        Modal.confirm({
          title: "未配置 AI 模型",
          content: "使用 AI 生成前需配置大语言模型。",
          okText: "去配置",
          cancelText: "取消",
          onOk: () => { window.location.href = "/settings/ai-config"; },
        });
        return false;
      }
      return true;
    } catch {
      return true;
    }
  }, []);

  const handleGenerate = useCallback(async () => {
    const hasConfig = await checkConfig();
    if (!hasConfig) return;
    setModalOpen(true);
    form.resetFields();
  }, [checkConfig, form]);

  const handleConfirm = useCallback(async () => {
    try {
      const values = await form.validateFields();
      const instruction = values.instruction || "";
      setModalOpen(false);
      setStatus("loading");
      setErrorMsg("");
      fullTextRef.current = "";

      if (mode === "selection" && selectedText !== undefined) {
        controllerRef.current = regenerateSelectionStream(
          planId, sectionKey, selectedText,
          contextBefore ?? null, contextAfter ?? null,
          instruction || null,
          (event) => {
            if (event.type === "chunk" && event.content) {
              fullTextRef.current += event.content;
              onContentChunk(event.content);
            } else if (event.type === "done") {
              setStatus("done");
              onGenerateComplete(event.content || fullTextRef.current);
              setTimeout(() => setStatus("idle"), 1500);
            } else if (event.type === "error") {
              setStatus("error");
              setErrorMsg(event.message || "AI 重写失败");
            }
          },
          (error) => { setStatus("error"); setErrorMsg(error); },
          () => {}
        );
      } else {
        controllerRef.current = generateSectionStream(
          planId, sectionKey, instruction || undefined,
          (event) => {
            if (event.type === "chunk" && event.content) {
              fullTextRef.current += event.content;
              onContentChunk(fullTextRef.current);
            } else if (event.type === "done") {
              setStatus("done");
              onGenerateComplete(event.content || fullTextRef.current);
              setTimeout(() => setStatus("idle"), 1500);
            } else if (event.type === "error") {
              setStatus("error");
              setErrorMsg(event.message || "AI 生成失败");
            }
          },
          (error) => { setStatus("error"); setErrorMsg(error); },
          () => {}
        );
      }
    } catch {
      // form validation failed, stay in modal
    }
  }, [planId, sectionKey, contextBefore, contextAfter, selectedText, mode, onContentChunk, onGenerateComplete, form]);

  const handleStop = useCallback(() => {
    controllerRef.current?.abort();
    stopGeneration(planId).catch(() => {});
    setStatus("idle");
  }, [planId]);

  const quickPrompts = getQuickPrompts();

  if (status === "loading") {
    return <Button icon={<LoadingOutlined />} onClick={handleStop} disabled={disabled}>生成中... 停止</Button>;
  }

  if (status === "done") {
    return <Button icon={<CheckCircleOutlined style={{ color: "#52c41a" }} />} disabled>生成完成</Button>;
  }

  const modalTitle = mode === "selection" ? "重写选中内容" : `生成「${sectionTitle || sectionKey}」`;

  return (
    <span>
      <Button icon={<RobotOutlined />} onClick={handleGenerate} disabled={disabled}>AI 生成</Button>
      {status === "error" && (
        <Alert type="error" message={errorMsg} closable onClose={() => setStatus("idle")} style={{ marginTop: 8 }}
          action={<Button size="small" onClick={handleConfirm}>重试</Button>}
        />
      )}
      <Modal
        title={modalTitle}
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        onOk={handleConfirm}
        okText="开始生成"
        cancelText="取消"
        width={560}
      >
        <div style={{ marginBottom: 12 }}>
          <Text type="secondary" style={{ fontSize: 12 }}>快捷指令（点击填入）：</Text>
          <div style={{ marginTop: 4, display: "flex", flexWrap: "wrap", gap: 4 }}>
            {quickPrompts.map((qp) => (
              <Tag
                key={qp.id}
                style={{ cursor: "pointer" }}
                onClick={() => {
                  const current = form.getFieldValue("instruction") || "";
                  form.setFieldsValue({ instruction: current ? `${current}\n${qp.text}` : qp.text });
                }}
              >
                {qp.label}
              </Tag>
            ))}
          </div>
        </div>
        <Form form={form} layout="vertical">
          <Form.Item name="instruction" label="自定义提示词（可选）">
            <Input.TextArea
              rows={4}
              placeholder="输入补充指令以优化生成结果，如：使用正式公文语体、补充操作步骤..."
            />
          </Form.Item>
        </Form>
      </Modal>
    </span>
  );
}
