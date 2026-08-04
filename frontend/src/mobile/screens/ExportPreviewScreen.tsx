// @ts-nocheck
import React, { useState, useRef, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  Download, FileText, Loader2,
  ChevronDown, Check, X, List,
} from "lucide-react";
import NavBar from "@/mobile/components/ui/NavBar";
import SafeArea from "@/mobile/components/ui/SafeArea";
import Spinner from "@/mobile/components/ui/Spinner";
import ProgressBar from "@/mobile/components/ui/ProgressBar";
import BottomSheet from "@/mobile/components/ui/BottomSheet";
import Button from "@/mobile/components/ui/Button";
import Toast, { useToast } from "@/mobile/components/ui/Toast";
import { getPlan } from "@/services/planService";
import { listSections } from "@/services/planService";
import { getExportPreview, exportDocx, getExportTaskStatus } from "@/services/exportService";

type ExportPhase = "idle" | "validating" | "exporting" | "done" | "failed";

export default function ExportPreviewScreen() {
  const { id: planId } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { showToast } = useToast();

  const [tocOpen, setTocOpen] = useState(false);
  const [exportPhase, setExportPhase] = useState<ExportPhase>("idle");
  const [exportProgress, setExportProgress] = useState(0);
  const contentRef = useRef<HTMLDivElement>(null);

  // 获取预案基本信息
  const { data: plan } = useQuery({
    queryKey: ["plan", planId],
    queryFn: () => getPlan(planId!),
    enabled: !!planId,
  });

  // 获取章节（用于目录和自渲染）
  const { data: sections = [] } = useQuery({
    queryKey: ["plan-sections", planId],
    queryFn: () => listSections(planId!),
    enabled: !!planId,
  });

  // 获取预览 HTML
  const { data: preview, isLoading, error } = useQuery({
    queryKey: ["export-preview", planId],
    queryFn: () => getExportPreview(planId!),
    enabled: !!planId,
    retry: 1,
  });

  // 提取目录
  const tocItems = React.useMemo(() => {
    const items: { id: string; title: string; level: number }[] = [];
    for (const sec of sections) {
      if (sec.title && sec.content) {
        items.push({ id: sec.section_key, title: sec.title, level: sec.level });
      }
    }
    return items;
  }, [sections]);

  // 滚动到指定章节
  const scrollToSection = useCallback((key: string) => {
    const el = document.getElementById(`section-${key}`);
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "start" });
      setTocOpen(false);
    }
  }, []);

  // 导出处理
  const handleExport = useCallback(async () => {
    if (!planId) {
      showToast?.({ type: "error", message: "预案ID缺失，请返回重试" });
      return;
    }
    setExportPhase("exporting");
    setExportProgress(0);

    try {
      const result = await exportDocx(planId);
      if (result instanceof Blob) {
        setExportPhase("done");
        const url = URL.createObjectURL(result);
        const a = document.createElement("a");
        a.href = url;
        a.download = `${plan?.title ?? "应急预案"}.docx`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        showToast?.({ type: "success", message: "文档已开始下载" });
      } else if ((result as any).task_id) {
        const taskId = (result as any).task_id;
        const poll = setInterval(async () => {
          try {
            const status = await getExportTaskStatus(taskId);
            setExportProgress(status.progress ?? 0);
            if (status.status === "completed") {
              clearInterval(poll);
              setExportPhase("done");
              showToast?.({ type: "success", message: "文档已生成" });
              if (status.download_url) {
                window.open(status.download_url, "_blank");
              }
            } else if (status.status === "failed") {
              clearInterval(poll);
              setExportPhase("failed");
            }
          } catch {
            clearInterval(poll);
            setExportPhase("failed");
          }
        }, 2000);
      } else {
        setExportPhase("failed");
        showToast?.({ type: "error", message: "导出失败：服务器返回异常" });
      }
    } catch {
      setExportPhase("failed");
      showToast?.({ type: "error", message: "导出失败，请重试" });
    }
  }, [planId, plan, showToast]);

  const previewHtml = preview?.html;

  // 渲染章节内容为文档格式
  const renderDocument = () => {
    const sorted = [...sections].sort((a, b) => a.sort_order - b.sort_order);
    const rootSections = sorted.filter(s => s.level === 0);
    const childSections = sorted.filter(s => s.level > 0);

    // 为每个根章节匹配子章节
    const childMap = new Map<number, typeof childSections>();
    for (const child of childSections) {
      // 找到最近的根章节
      let parentIdx = 0;
      for (let i = sorted.indexOf(child) - 1; i >= 0; i--) {
        if (sorted[i].level === 0) {
          parentIdx = sorted[i].sort_order;
          break;
        }
      }
      if (!childMap.has(parentIdx)) childMap.set(parentIdx, []);
      childMap.get(parentIdx)!.push(child);
    }

    return (
      <div className="document-content">
        {/* 封面 */}
        <div className="cover-page text-center py-16 px-md border-b border-neutral-200 mb-8">
          <div className="w-16 h-16 mx-auto mb-6 rounded-full bg-primary-50 flex items-center justify-center">
            <FileText size={32} className="text-primary-600" />
          </div>
          <h1 className="text-h1 text-neutral-900 mb-3">{plan?.title ?? "应急预案"}</h1>
          {plan?.enterprise_name && (
            <p className="text-body text-neutral-500 mb-2">{plan.enterprise_name}</p>
          )}
          <div className="flex items-center justify-center gap-4 mt-6 text-caption text-neutral-400">
            <span>GB/T 29639-2020</span>
            <span>·</span>
            <span>{sections.length} 个章节</span>
          </div>
        </div>

        {/* 目录页 */}
        <div className="toc-page mb-8 px-md">
          <h2 className="text-h2 text-neutral-900 mb-4">目  录</h2>
          <div className="border-t border-neutral-200 pt-4">
            {tocItems.map((item, i) => (
              <div
                key={item.id}
                className="flex items-center py-2 border-b border-neutral-50 text-body-sm"
              >
                <span className="text-neutral-400 w-8 shrink-0">{i + 1}</span>
                <span className="text-neutral-700">{item.title}</span>
              </div>
            ))}
          </div>
        </div>

        {/* 正文 */}
        {rootSections.map((sec, idx) => (
          <div key={sec.section_key} id={`section-${sec.section_key}`} className="section-block mb-8 px-md">
            <h2 className="text-h2 text-neutral-900 mb-1">
              {idx + 1}. {sec.title}
            </h2>
            <div className="h-px bg-neutral-200 my-3" />
            {sec.content ? (
              <div
                className="prose prose-sm max-w-none text-body leading-relaxed text-neutral-700"
                dangerouslySetInnerHTML={{ __html: String(sec.content) }}
              />
            ) : (
              <p className="text-body-sm text-neutral-400 italic">此章节暂无内容</p>
            )}

            {/* 子章节 */}
            {childMap.get(sec.sort_order)?.map((child, ci) => (
              <div key={child.section_key} id={`section-${child.section_key}`} className="mt-6 ml-2">
                <h3 className="text-h3 text-neutral-800 mb-1">
                  {idx + 1}.{ci + 1} {child.title}
                </h3>
                <div className="h-px bg-neutral-100 my-2" />
                {child.content ? (
                  <div
                    className="prose prose-sm max-w-none text-body-sm leading-relaxed text-neutral-600"
                    dangerouslySetInnerHTML={{ __html: String(child.content) }}
                  />
                ) : (
                  <p className="text-caption text-neutral-400 italic">此章节暂无内容</p>
                )}
              </div>
            ))}
          </div>
        ))}

        {/* 文档末尾 */}
        {sections.filter(s => s.content).length > 0 && (
          <div className="text-center py-8 px-md border-t border-neutral-100 mt-8">
            <p className="text-caption text-neutral-400">— 文档结束 —</p>
            <p className="text-caption text-neutral-300 mt-1">
              生成时间：{new Date().toLocaleDateString("zh-CN")}
            </p>
          </div>
        )}
      </div>
    );
  };

  return (
    <SafeArea className="bg-white min-h-dvh flex flex-col">
      {/* NavBar */}
      <NavBar
        title="文档预览"
        showBack
        onBack={() => navigate(-1)}
        rightActions={[
          {
            icon: <List size={22} />,
            label: "目录",
            onPress: () => setTocOpen(true),
          },
        ]}
      />

      {/* 主内容区 */}
      <div className="flex-1 overflow-y-auto" ref={contentRef}>
        {isLoading && (
          <div className="flex flex-col items-center justify-center py-20">
            <Spinner size="lg" />
            <p className="text-body text-neutral-500 mt-md">加载预览中…</p>
          </div>
        )}

        {error && !previewHtml && sections.length === 0 && (
          <div className="flex flex-col items-center justify-center py-20 px-md text-center">
            <FileText size={48} className="text-neutral-300 mb-4" />
            <p className="text-h3 text-neutral-900 mb-2">暂无预览内容</p>
            <p className="text-body-sm text-neutral-500">
              请先在编辑器中为各章节添加内容，再回到此处预览
            </p>
          </div>
        )}

        {/* 优先使用 API 返回的 HTML，否则自渲染 */}
        {previewHtml ? (
          <div
            className="preview-html p-md"
            dangerouslySetInnerHTML={{ __html: previewHtml }}
          />
        ) : sections.length > 0 ? (
          renderDocument()
        ) : null}
      </div>

      {/* 底部操作栏 */}
      <div className="bg-white border-t border-neutral-100 px-md py-3"
           style={{ paddingBottom: "calc(12px + var(--safe-bottom))" }}>
        {/* 导出进度 */}
        {exportPhase === "exporting" && (
          <div className="mb-3">
            <ProgressBar percent={exportProgress > 0 ? exportProgress : undefined} />
            <p className="text-caption text-neutral-500 text-center mt-1">正在生成文档…</p>
          </div>
        )}

        {exportPhase === "failed" && (
          <div className="mb-2 flex items-center justify-center gap-2 text-danger text-caption">
            <X size={14} /> 导出失败
          </div>
        )}

        {exportPhase === "done" && (
          <div className="mb-2 flex items-center justify-center gap-2 text-success text-caption">
            <Check size={14} /> 导出完成
          </div>
        )}

        {/* 操作按钮组 */}
        <div className="flex gap-sm">
          <Button
            variant="secondary"
            size="lg"
            className="flex-1"
            onClick={() => navigate(`/m/plans/${planId}/edit`)}
          >
            <FileText size={18} className="mr-xs" /> 继续编辑
          </Button>
          <Button
            variant="primary"
            size="lg"
            className="flex-1"
            onClick={handleExport}
            disabled={exportPhase === "exporting"}
          >
            {exportPhase === "exporting" ? (
              <><Loader2 size={18} className="mr-xs animate-spin" /> 导出中…</>
            ) : (
              <><Download size={18} className="mr-xs" /> 导出 .docx</>
            )}
          </Button>
        </div>
      </div>

      {/* 目录抽屉 */}
      <BottomSheet
        open={tocOpen}
        onClose={() => setTocOpen(false)}
        height="70%"
      >
        <div className="p-md h-full flex flex-col">
          <div className="flex items-center justify-between mb-md">
            <p className="text-h2 font-semibold">目  录</p>
            <button onClick={() => setTocOpen(false)}>
              <X size={20} className="text-neutral-400" />
            </button>
          </div>

          {tocItems.length === 0 ? (
            <p className="text-body-sm text-neutral-400 text-center py-8">
              暂无章节内容
            </p>
          ) : (
            <div className="flex-1 overflow-y-auto">
              {tocItems.map((item, i) => (
                <button
                  key={item.id}
                  className="flex items-center w-full py-3 px-sm text-left border-b border-neutral-50 active:bg-neutral-50 rounded-sm"
                  onClick={() => scrollToSection(item.id)}
                >
                  <span className="w-8 h-7 rounded-full bg-primary-50 text-primary-600 text-caption font-semibold flex items-center justify-center shrink-0 mr-sm">
                    {i + 1}
                  </span>
                  <span className="flex-1 text-body text-neutral-800 truncate">{item.title}</span>
                  <ChevronDown size={14} className="text-neutral-400 shrink-0 rotate-[-90deg]" />
                </button>
              ))}
            </div>
          )}
        </div>
      </BottomSheet>
    </SafeArea>
  );
}
