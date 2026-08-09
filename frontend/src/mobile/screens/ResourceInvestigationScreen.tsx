// @ts-nocheck
import React, { useState, useRef, useEffect, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Package, RefreshCw, Download, Loader2,
  Sparkles, X, FileText,
} from "lucide-react";
import NavBar from "@/mobile/components/ui/NavBar";
import SafeArea from "@/mobile/components/ui/SafeArea";
import Spinner from "@/mobile/components/ui/Spinner";
import EmptyState from "@/mobile/components/ui/EmptyState";
import ProgressBar from "@/mobile/components/ui/ProgressBar";
import Button from "@/mobile/components/ui/Button";
import Toast, { useToast } from "@/mobile/components/ui/Toast";
import {
  getResourceInvestigation,
  downloadResourceInvestigation,
  generateResourceInvestigationStream,
} from "@/services/resourceInvestigationService";
import type { SSEEvent } from "@/types/riskAssessment";

type GenerationStatus = "idle" | "generating" | "done" | "cancelled";

export default function ResourceInvestigationScreen() {
  const { id: enterpriseId } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { showToast } = useToast();

  const [genStatus, setGenStatus] = useState<GenerationStatus>("idle");
  const [streamContent, setStreamContent] = useState("");
  const [progressMessage, setProgressMessage] = useState("");
  const [progressPct, setProgressPct] = useState(0);
  const abortRef = useRef<AbortController | null>(null);
  const contentRef = useRef<HTMLDivElement>(null);

  // 读取已有报告
  const { data: report, isLoading, error } = useQuery({
    queryKey: ["resource-investigation", enterpriseId],
    queryFn: () => getResourceInvestigation(enterpriseId!),
    enabled: !!enterpriseId && genStatus === "idle",
  });

  const hasReport = report && typeof report === "object" && "content" in report;
  const reportContent = hasReport ? (report as Record<string, unknown>).content : null;

  // 清理 abort
  useEffect(() => {
    return () => { abortRef.current?.abort(); };
  }, []);

  // 滚动到底部
  useEffect(() => {
    if (streamContent && contentRef.current) {
      contentRef.current.scrollTop = contentRef.current.scrollHeight;
    }
  }, [streamContent]);

  // 开始生成
  const handleGenerate = useCallback(() => {
    if (!enterpriseId) return;
    setGenStatus("generating");
    setStreamContent("");
    setProgressMessage("正在连接 AI 生成引擎…");
    setProgressPct(0);

    const controller = generateResourceInvestigationStream(
      enterpriseId,
      undefined,
      (event: SSEEvent) => {
        if (event.type === "progress" || event.type === "chapter_start") {
          setProgressMessage(event.message ?? event.chapter ?? "正在生成…");
          setProgressPct(Math.min(95, (event.current ?? 0) / Math.max(1, event.total ?? 7) * 100));
        } else if (event.type === "chapter_end") {
          const chunk = event.content ?? "";
          if (chunk) {
            setStreamContent(prev => prev + chunk);
          }
        } else if (event.type === "token" || event.type === "chunk") {
          const chunk = event.content ?? event.token ?? event.chunk ?? "";
          if (chunk) {
            setStreamContent(prev => prev + chunk);
          }
        } else if (event.type === "done" || event.type === "complete") {
          if (event.content) setStreamContent(event.content);
          setGenStatus("done");
          setProgressPct(100);
          setProgressMessage("生成完成");
          queryClient.invalidateQueries({ queryKey: ["resource-investigation", enterpriseId] });
          queryClient.invalidateQueries({ queryKey: ["completion", enterpriseId] });
        } else if (event.type === "section_done") {
          const chunk = event.content ?? "";
          if (chunk) {
            setStreamContent(prev => prev + chunk);
          }
        } else if (event.type === "batch_done") {
          const batchChapters = event.chapters;
          if (batchChapters) {
            try {
              const parsed = typeof batchChapters === "string" ? JSON.parse(batchChapters) : batchChapters;
              const merged = parsed.map((c: { title: string; content: string }) => `## ${c.title}\n\n${c.content}`).join("\n\n");
              setStreamContent(merged);
            } catch { /* use streamContent */ }
          }
          setGenStatus("done");
          setProgressPct(100);
          setProgressMessage("生成完成");
          queryClient.invalidateQueries({ queryKey: ["resource-investigation", enterpriseId] });
          queryClient.invalidateQueries({ queryKey: ["completion", enterpriseId] });
        } else if (event.type === "error") {
          showToast?.({ type: "error", message: event.message ?? "生成失败" });
          setGenStatus("idle");
        }
      },
      (errorMsg: string) => {
        showToast?.({ type: "error", message: errorMsg });
        setGenStatus("idle");
      },
      () => {
        setGenStatus("done");
        setProgressPct(100);
        setProgressMessage("生成完成");
        queryClient.invalidateQueries({ queryKey: ["resource-investigation", enterpriseId] });
        queryClient.invalidateQueries({ queryKey: ["completion", enterpriseId] });
      }
    );
    abortRef.current = controller;
  }, [enterpriseId, showToast, queryClient]);

  // 取消生成
  const handleCancel = () => {
    abortRef.current?.abort();
    setGenStatus("cancelled");
    setProgressMessage("已取消生成");
    showToast?.({ type: "info", message: "已取消生成，已保留已生成内容" });
  };

  // 下载报告
  const handleDownload = async () => {
    if (!enterpriseId) return;
    try {
      await downloadResourceInvestigation(enterpriseId);
      showToast?.({ type: "success", message: "报告下载中…" });
    } catch {
      showToast?.({ type: "error", message: "下载失败" });
    }
  };

  const displayContent = streamContent || reportContent;

  return (
    <SafeArea className="bg-neutral-50 min-h-dvh">
      <NavBar
        title="应急资源调查报告"
        showBack
        onBack={() => navigate(-1)}
        rightActions={displayContent ? [{
          icon: <Download size={22} />,
          label: "下载",
          onPress: handleDownload,
        }] : undefined}
      />

      {/* 生成横幅 */}
      {genStatus === "generating" && (
        <div className="bg-primary-50 border-b border-primary-100 px-md py-3">
          <div className="flex items-center gap-sm mb-2">
            <Loader2 size={16} className="animate-spin text-primary-600" />
            <span className="flex-1 text-body-sm text-primary-600">{progressMessage}</span>
            <button className="text-red-500 text-caption font-medium" onClick={handleCancel}>
              取消
            </button>
          </div>
          <ProgressBar percent={progressPct} />
        </div>
      )}

      {/* 内容区 */}
      <div className="flex-1 overflow-y-auto" ref={contentRef}>
        {isLoading && (
          <div className="flex flex-col items-center justify-center py-20">
            <Spinner size="lg" />
            <p className="text-body text-neutral-500 mt-md">加载报告中…</p>
          </div>
        )}

        {error && genStatus === "idle" && (
          <EmptyState
            icon={<Package size={40} className="text-red-400" />}
            title="加载失败"
            description="无法加载应急资源调查报告"
            action="重试"
            onAction={() => queryClient.invalidateQueries({ queryKey: ["resource-investigation", enterpriseId] })}
          />
        )}

        {displayContent && (
          <div className="prose prose-sm max-w-none bg-white rounded-md shadow-card p-md m-md"
               dangerouslySetInnerHTML={{ __html: String(displayContent) }} />
        )}

        {!isLoading && !error && !displayContent && genStatus === "idle" && (
          <EmptyState
            icon={<FileText size={40} className="text-neutral-300" />}
            title="暂无应急资源调查报告"
            description="基于企业应急资源数据，AI 将自动生成资源调查报告"
          />
        )}

        {genStatus === "cancelled" && streamContent && (
          <div className="prose prose-sm max-w-none bg-white rounded-md shadow-card p-md m-md"
               dangerouslySetInnerHTML={{ __html: streamContent }} />
        )}
      </div>

      {/* 底部操作栏 */}
      <div className="p-md bg-white border-t border-neutral-100"
           style={{ paddingBottom: "calc(16px + var(--safe-bottom))" }}>
        {genStatus === "generating" ? (
          <Button variant="secondary" size="lg" fullWidth onClick={handleCancel}>
            <X size={18} className="mr-xs" /> 取消生成
          </Button>
        ) : genStatus === "done" || displayContent ? (
          <div className="flex gap-sm">
            <Button variant="secondary" size="lg" className="flex-1" onClick={handleGenerate}>
              <RefreshCw size={18} className="mr-xs" /> 重新生成
            </Button>
            <Button variant="primary" size="lg" className="flex-1" onClick={handleDownload}>
              <Download size={18} className="mr-xs" /> 导出 .docx
            </Button>
          </div>
        ) : (
          <Button variant="primary" size="lg" fullWidth icon={<Sparkles size={18} />} onClick={handleGenerate}>
            AI 生成应急资源调查报告
          </Button>
        )}
      </div>
    </SafeArea>
  );
}
