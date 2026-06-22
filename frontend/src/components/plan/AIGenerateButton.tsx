import { useState, useCallback, useRef } from "react";
import { Button, Alert } from "antd";
import { RobotOutlined, LoadingOutlined, CheckCircleOutlined } from "@ant-design/icons";
import { generateSectionStream, stopGeneration } from "@/services/generationService";
import { getAIConfig } from "@/services/aiConfigService";
import { Modal } from "antd";

interface AIGenerateButtonProps {
  planId: string;
  sectionKey: string;
  onContentChunk: (chunk: string) => void;
  onGenerateComplete: (fullText: string) => void;
  disabled?: boolean;
}

type GenStatus = "idle" | "loading" | "done" | "error";

export default function AIGenerateButton({
  planId, sectionKey, onContentChunk, onGenerateComplete, disabled,
}: AIGenerateButtonProps) {
  const [status, setStatus] = useState<GenStatus>("idle");
  const [errorMsg, setErrorMsg] = useState("");
  const controllerRef = useRef<AbortController | null>(null);
  const fullTextRef = useRef("");

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
    setStatus("loading");
    setErrorMsg("");
    fullTextRef.current = "";

    controllerRef.current = generateSectionStream(
      planId, sectionKey, undefined,
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
  }, [planId, sectionKey, onContentChunk, onGenerateComplete, checkConfig]);

  const handleStop = useCallback(() => {
    controllerRef.current?.abort();
    stopGeneration(planId).catch(() => {});
    setStatus("idle");
  }, [planId]);

  if (status === "loading") {
    return <Button icon={<LoadingOutlined />} onClick={handleStop} disabled={disabled}>生成中... 停止</Button>;
  }

  if (status === "done") {
    return <Button icon={<CheckCircleOutlined style={{ color: "#52c41a" }} />} disabled>生成完成</Button>;
  }

  return (
    <span>
      <Button icon={<RobotOutlined />} onClick={handleGenerate} disabled={disabled}>AI 生成</Button>
      {status === "error" && (
        <Alert type="error" message={errorMsg} closable onClose={() => setStatus("idle")} style={{ marginTop: 8 }}
          action={<Button size="small" onClick={handleGenerate}>重试</Button>}
        />
      )}
    </span>
  );
}
