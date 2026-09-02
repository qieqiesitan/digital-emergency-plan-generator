import { useState, useCallback, useRef, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Button, Alert, Modal, Form, Input, Tag, Typography } from "antd";
import { LoadingOutlined, CheckCircleOutlined } from "@ant-design/icons";
import AppIcon from "@/components/common/AppIcon";
import { generateSectionStream, stopGeneration, regenerateSelectionStream } from "@/services/generationService";
import { getAIConfig } from "@/services/aiConfigService";
import { getQuickPrompts } from "@/utils/quickPrompts";
import { AI_CONFIG_ROUTE, AI_NOT_CONFIGURED_HINT, aiErrorDisplay } from "@/utils/aiUnavailable";
import DiffPreviewModal from "./DiffPreviewModal";

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
  oldContent?: string;
  onReject?: (oldText?: string) => void;
}

type GenStatus = "idle" | "loading" | "done" | "error";

export default function AIGenerateButton({
  planId, sectionKey, sectionTitle, onContentChunk, onGenerateComplete, disabled,
  mode = "full", selectedText, contextBefore, contextAfter, oldContent, onReject,
}: AIGenerateButtonProps) {
  const [status, setStatus] = useState<GenStatus>("idle");
  const [errorMsg, setErrorMsg] = useState("");
  const [aiConfigError, setAiConfigError] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [diffOpen, setDiffOpen] = useState(false);
  const [diffOld, setDiffOld] = useState("");
  const [diffNew, setDiffNew] = useState("");
  const controllerRef = useRef<AbortController | null>(null);
  const fullTextRef = useRef("");
  const [form] = Form.useForm();
  const navigate = useNavigate();

  const checkConfig = useCallback(async (): Promise<boolean> => {
    try {
      const config = await getAIConfig();
      if (!config) {
        Modal.warning({
          title: "AI 未配置",
          content: (
            <div>
              <div>{AI_NOT_CONFIGURED_HINT}</div>
              <Button type="primary" size="small" style={{ marginTop: 12 }} onClick={() => navigate(AI_CONFIG_ROUTE)}>
                前往 AI 配置
              </Button>
            </div>
          ),
          okText: "知道了",
        });
        return false;
      }
      return true;
    } catch {
      return true;
    }
  }, [navigate]);

  /** 生成/重写失败统一落点：AI 未配置 → 引导文案 + 跳转；其余 → 通用错误（可重试） */
  const applyGenError = useCallback((raw: string | undefined, fallback: string) => {
    const disp = aiErrorDisplay(raw, fallback);
    setStatus("error");
    setErrorMsg(disp.text);
    setAiConfigError(disp.notConfigured);
  }, []);

  const handleGenerate = useCallback(async () => {
    const hasConfig = await checkConfig();
    if (!hasConfig) return;
    setModalOpen(true);
    form.resetFields();
  }, [checkConfig, form]);

  // ponytail: auto-open modal when mounted in selection mode (triggered by RichTextEditor toolbar click)
  useEffect(() => {
    if (mode === "selection") {
      handleGenerate();
    }
  }, [mode]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleConfirm = useCallback(async () => {
    try {
      const values = await form.validateFields();
      const instruction = values.instruction || "";
      setModalOpen(false);
      setStatus("loading");
      setErrorMsg("");
      setAiConfigError(false);
      fullTextRef.current = "";

      if (mode === "selection" && selectedText !== undefined) {
        controllerRef.current = regenerateSelectionStream(
          planId, sectionKey, selectedText,
          contextBefore ?? null, contextAfter ?? null,
          (event) => {
            if (event.type === "chunk" && event.content) {
              fullTextRef.current += event.content;
            } else if (event.type === "done") {
              setStatus("done");
              onGenerateComplete(fullTextRef.current || event.content || "");
              setTimeout(() => setStatus("idle"), 1500);
            } else if (event.type === "error") {
              applyGenError(event.message, "AI 重写失败");
            }
          },
          (error) => applyGenError(error, "AI 重写失败"),
          () => {},
          instruction || null
        );
      } else {
        controllerRef.current = generateSectionStream(
          planId, sectionKey,
          (event) => {
            if (event.type === "chunk" && event.content) {
              fullTextRef.current += event.content;
              onContentChunk(fullTextRef.current);
            } else if (event.type === "done") {
              const newText = event.content || fullTextRef.current;
              if (oldContent && newText !== oldContent) {
                setDiffOld(oldContent);
                setDiffNew(newText);
                setDiffOpen(true);
              } else {
                setDiffOpen(false);
              }
              onGenerateComplete(newText);
              setStatus("done");
              setTimeout(() => setStatus("idle"), 1500);
            } else if (event.type === "error") {
              applyGenError(event.message, "AI 生成失败");
            }
          },
          (error) => applyGenError(error, "AI 生成失败"),
          () => {},
          instruction || undefined
        );
      }
    } catch {
      // form validation failed, stay in modal
    }
  }, [planId, sectionKey, contextBefore, contextAfter, selectedText, oldContent, mode, onContentChunk, onGenerateComplete, form, applyGenError]);

  const handleStop = useCallback(() => {
    controllerRef.current?.abort();
    stopGeneration(planId).catch(() => {});
    setStatus("idle");
  }, [planId]);

  const quickPrompts = getQuickPrompts();

  const modalTitle = mode === "selection" ? "重写选中内容" : `生成「${sectionTitle || sectionKey}」`;

  return (
    <span>
      {status === "loading" ? (
        // ponytail: in selection mode, feedback is handled by RichTextEditor toolbar; render nothing here
        mode === "selection" ? null : (
          <Button icon={<LoadingOutlined />} onClick={handleStop} disabled={disabled}>生成中... 停止</Button>
        )
      ) : status === "done" ? (
        <Button icon={<CheckCircleOutlined style={{ color: "#52c41a" }} />} disabled>生成完成</Button>
      ) : (
        <>
          <Button icon={<AppIcon name="ai" size={14} />} onClick={handleGenerate} disabled={disabled}>AI 生成</Button>
          {status === "error" && (
            <Alert
              type={aiConfigError ? "warning" : "error"}
              message={errorMsg}
              closable
              onClose={() => { setStatus("idle"); setAiConfigError(false); }}
              style={{ marginTop: 8 }}
              action={
                aiConfigError ? (
                  <Button size="small" type="primary" onClick={() => navigate(AI_CONFIG_ROUTE)}>
                    前往 AI 配置
                  </Button>
                ) : (
                  <Button size="small" onClick={handleConfirm}>重试</Button>
                )
              }
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
        </>
      )}
      <DiffPreviewModal
        open={diffOpen}
        oldText={diffOld}
        newText={diffNew}
        onAccept={() => setDiffOpen(false)}
        onReject={() => {
          setDiffOpen(false);
          onReject?.(diffOld);
        }}
        onClose={() => setDiffOpen(false)}
      />
    </span>
  );
}
