// @ts-nocheck
import React, { useState, useEffect, useRef, useCallback, useMemo } from "react";
import { useParams, useNavigate, useSearchParams } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  MoreHorizontal, Sparkles, Download,
  GitBranch, Loader2, ArrowLeft, Check,
  AlertTriangle, Save,
} from "lucide-react";
import NavBar from "@/mobile/components/ui/NavBar";
import SafeArea from "@/mobile/components/ui/SafeArea";
import Spinner from "@/mobile/components/ui/Spinner";
import BottomSheet from "@/mobile/components/ui/BottomSheet";
import ProgressBar from "@/mobile/components/ui/ProgressBar";
import Toast, { useToast } from "@/mobile/components/ui/Toast";
import ChapterTree from "@/mobile/components/plan/ChapterTree";
import MobileEditor from "@/mobile/components/plan/MobileEditor";
import EditorToolbar from "@/mobile/components/plan/EditorToolbar";
import AIGenerationSheet from "@/mobile/components/plan/AIGenerationSheet";
import type { ChapterNode } from "@/mobile/components/plan/ChapterTree";
import { getPlan, createVersion } from "@/services/planService";
import { listSections, updateSection, autofillSection } from "@/services/planService";
import { generateBatchBackground, getGenerationStatus } from "@/services/generationService";
import { useAppStore } from "@/mobile/store/appStore";
import { useDraftStore } from "@/mobile/store/draftStore";

type EditorMode = "navigate" | "edit";

export default function PlanEditorScreen() {
  const { id: planId } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { showToast } = useToast();
  const { setKeyboard } = useAppStore();
  const { addDraft } = useDraftStore();

  const [mode, setMode] = useState<EditorMode>("navigate");
  const [selectedChapter, setSelectedChapter] = useState<ChapterNode | null>(null);
  const [localContent, setLocalContent] = useState("");
  const [toolbarVisible, setToolbarVisible] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [genProgressPct, setGenProgressPct] = useState(0);
  const [genProgressMsg, setGenProgressMsg] = useState("");
  const [generationBanner, setGenerationBanner] = useState<{
    status: "generating" | "done" | "cancelled"; message: string;
  } | null>(null);
  const [batchSheetOpen, setBatchSheetOpen] = useState(false);
  const [failedSections, setFailedSections] = useState<Array<{ section_key: string; title: string }>>([]);

  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const statusTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // 获取预案信息
  const { data: plan, isLoading: planLoading } = useQuery({
    queryKey: ["plan", planId],
    queryFn: () => getPlan(planId!),
    enabled: !!planId,
  });

  // 获取全部章节
  const { data: sections = [], isLoading: sectionsLoading } = useQuery({
    queryKey: ["plan-sections", planId],
    queryFn: () => listSections(planId!),
    enabled: !!planId,
  });

  // 建立章节树
  const chapters: ChapterNode[] = useMemo(() => {
    const parentMap = new Map<number, ChapterNode>();
    const roots: ChapterNode[] = [];
    const sorted = [...sections].sort((a, b) => a.sort_order - b.sort_order);

    sorted.forEach((sec) => {
      const node: ChapterNode = {
        key: sec.section_key,
        title: `${sec.title}`,
        level: sec.level,
        aiGeneratable: sec.ai_generatable,
        autoFill: sec.auto_fill,
        required: sec.level === 0,
      };

      if (sec.level === 0) {
        roots.push(node);
        parentMap.set(sec.sort_order, node);
      } else {
        let parent: ChapterNode | undefined;
        for (let i = sorted.indexOf(sec) - 1; i >= 0; i--) {
          if (sorted[i].level === 0) {
            parent = parentMap.get(sorted[i].sort_order);
            break;
          }
        }
        if (parent) {
          parent.children = parent.children ?? [];
          parent.children.push(node);
        } else {
          roots.push(node);
        }
      }
    });

    return roots;
  }, [sections]);

  // 批量生成可选的章节（仅 aiGeneratable）
  const batchChapters: Array<{ key: string; name: string; aiGeneratable: boolean }> = useMemo(() => {
    return chapters
      .flatMap((c) => [c, ...(c.children || [])])
      .filter((c) => c.aiGeneratable)
      .map((c) => ({ key: c.key, name: c.title, aiGeneratable: true }));
  }, [chapters]);

  // 章节状态
  const sectionStates = useMemo(() => {
    const states: Record<string, { hasContent: boolean; aiGenerated: boolean }> = {};
    sections.forEach(sec => {
      states[sec.section_key] = {
        hasContent: (sec.content && sec.content.length > 10) || false,
        aiGenerated: sec.ai_generated,
      };
    });
    return states;
  }, [sections]);

  // 保存章节
  const saveMutation = useMutation({
    mutationFn: async (content: string) => {
      if (!planId || !selectedChapter) return;
      try {
        await updateSection(planId, selectedChapter.key, { content });
        addDraft(planId, selectedChapter.key, content);
      } catch {
        addDraft(planId, selectedChapter.key, content);
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["plan-sections", planId] });
    },
  });

  // 自动保存
  const autoSave = useCallback((content: string) => {
    if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    saveTimerRef.current = setTimeout(() => {
      saveMutation.mutate(content);
    }, 3000);
  }, [saveMutation]);

  const handleSelectChapter = useCallback((chapter: ChapterNode) => {
    setSelectedChapter(chapter);
    setMode("edit");
    const sec = sections.find(s => s.section_key === chapter.key);
    setLocalContent(sec?.content ?? "");
    setToolbarVisible(true);
    setTimeout(() => {
      textareaRef.current?.focus();
    }, 100);
  }, [sections]);

  const handleBackToNavigate = useCallback(() => {
    if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    if (localContent && selectedChapter) {
      saveMutation.mutate(localContent);
    }
    setMode("navigate");
    setSelectedChapter(null);
    setToolbarVisible(false);
  }, [localContent, selectedChapter, saveMutation]);

  // 键盘监听
  useEffect(() => {
    const handleResize = () => {
      if (window.visualViewport) {
        const keyboardOpen = window.visualViewport.height < window.innerHeight * 0.85;
        setToolbarVisible(keyboardOpen && mode === "edit");
        setKeyboard(keyboardOpen, window.innerHeight - window.visualViewport.height);
      }
    };
    if (window.visualViewport) {
      window.visualViewport.addEventListener("resize", handleResize);
    }
    return () => {
      window.visualViewport?.removeEventListener("resize", handleResize);
    };
  }, [mode, setKeyboard]);

  useEffect(() => {
    return () => {
      if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
      if (statusTimerRef.current) clearTimeout(statusTimerRef.current);
      abortRef.current?.abort();
    };
  }, []);

  // ========== AI 生成（真实 SSE 流式） ==========
  const handleAIGenerate = useCallback(async () => {
    if (!planId || !selectedChapter) return;
    abortRef.current?.abort();
    abortRef.current = new AbortController();

    setGenerating(true);
    setGenProgressPct(0);
    setGenProgressMsg(`AI 正在撰写"${selectedChapter.title}"…`);
    setGenerationBanner({ status: "generating", message: `AI 正在撰写"${selectedChapter.title}"…` });

    const token = localStorage.getItem("access_token");

    try {
      const response = await fetch(`/api/v1/plans/${planId}/generate/${selectedChapter.key}`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        signal: abortRef.current.signal,
      });

      if (!response.ok) {
        throw new Error("生成请求失败");
      }

      const reader = response.body?.getReader();
      if (!reader) throw new Error("无法读取响应流");

      const decoder = new TextDecoder();
      let buffer = "";
      let accumulated = localContent;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            try {
              const jsonStr = line.replace(/^(?:data: )+/, "");
              const event = JSON.parse(jsonStr);

              if (event.type === "progress" || event.type === "chapter_start") {
                setGenProgressMsg(event.message ?? event.chapter ?? "");
                setGenProgressPct(Math.min(95, (event.current ?? 0) / Math.max(1, event.total ?? 1) * 100));
              } else {
                const chunk = event.content ?? event.token ?? event.chunk ?? "";
                if (chunk) {
                  accumulated += chunk;
                  setLocalContent(accumulated);
                }
              }
            } catch { /* skip */ }
          }
        }
      }

      setGenerating(false);
      setGenProgressPct(100);
      setGenerationBanner({ status: "done", message: "✓ 生成完成" });
      autoSave(accumulated);
      setTimeout(() => setGenerationBanner(null), 2000);
    } catch (err: any) {
      if (err.name === "AbortError") {
        setGenerationBanner({ status: "cancelled", message: "已取消，已保留已生成内容" });
        setTimeout(() => setGenerationBanner(null), 2000);
        return;
      }
      setGenerating(false);
      setGenerationBanner(null);
      showToast?.({ type: "error", message: err.message ?? "生成失败" });
    }
  }, [planId, selectedChapter, localContent, autoSave, showToast]);

  const handleCancelGeneration = () => {
    abortRef.current?.abort();
    setGenerating(false);
    setGenerationBanner({ status: "cancelled", message: "已取消，已保留已生成内容" });
    setTimeout(() => setGenerationBanner(null), 2000);
  };

  // ========== AI 批量生成（后台 + 失败重试） ==========
  // 后台批量生成通常需要 1-3 分钟，单次 5 秒查询几乎总是查不到结果。
  // 改为多次轮询：每 15 秒查一次，最多 8 次（约 2 分钟），生成完成或出现失败即停止。
  const pollGenerationStatus = useCallback(
    async (planId: string, attempts = 8, intervalMs = 15000) => {
      for (let i = 0; i < attempts; i++) {
        await new Promise((r) => setTimeout(r, intervalMs));
        try {
          const status = await getGenerationStatus(planId);
          const failed = status?.data?.failed_sections ?? [];
          if (!status?.data?.generating || failed.length > 0) {
            setFailedSections(failed);
            return failed;
          }
        } catch {
          // 轮询失败继续尝试
        }
      }
      return [];
    },
    []
  );

  const runBatchGeneration = useCallback(async (keys: string[]) => {
    if (!planId) return;
    if (keys.length === 0) {
      showToast?.({ type: "info", message: "请至少选择一个章节" });
      return;
    }
    setFailedSections([]);
    try {
      const res = await generateBatchBackground(planId, keys);
      showToast?.({ type: "success", message: res.message || "已在后台开始生成" });
      if (statusTimerRef.current) clearTimeout(statusTimerRef.current);
      statusTimerRef.current = setTimeout(async () => {
        const failed = await pollGenerationStatus(planId);
        if (failed.length > 0) {
          showToast?.({ type: "error", message: `${failed.length} 个章节生成失败，可点击重试` });
        }
        // 轮询结束后刷新章节内容与失败提示条
        queryClient.invalidateQueries({ queryKey: ["plan-sections", planId] });
      }, 0);
    } catch (e: any) {
      showToast?.({ type: "error", message: e?.message || "批量生成失败" });
    }
  }, [planId, showToast, queryClient, pollGenerationStatus]);

  const handleBatchGenerate = useCallback((selectedKeys: string[]) => {
    setBatchSheetOpen(false);
    runBatchGeneration(selectedKeys);
  }, [runBatchGeneration]);

  const handleRetryFailed = useCallback(() => {
    const keys = failedSections.map((f) => f.section_key);
    runBatchGeneration(keys);
  }, [failedSections, runBatchGeneration]);

  // 文本格式化
  const wrapSelection = (wrapper: string, endWrapper?: string) => {
    const ta = textareaRef.current;
    if (!ta) return;
    const start = ta.selectionStart;
    const end = ta.selectionEnd;
    const selected = localContent.substring(start, end);
    const before = localContent.substring(0, start);
    const after = localContent.substring(end);
    const newContent = before + wrapper + selected + (endWrapper ?? wrapper) + after;
    setLocalContent(newContent);
    autoSave(newContent);
    setTimeout(() => {
      ta.focus();
      ta.setSelectionRange(start + wrapper.length, end + wrapper.length);
    }, 0);
  };

  const handleBold = () => wrapSelection("**");
  const handleItalic = () => wrapSelection("*");
  const handleHeading = () => {
    const ta = textareaRef.current;
    if (!ta) return;
    const lineStart = localContent.lastIndexOf("\n", ta.selectionStart) + 1;
    const after = localContent.substring(lineStart);
    if (after.startsWith("## ")) {
      setLocalContent(localContent.substring(0, lineStart) + after.substring(3));
    } else {
      setLocalContent(localContent.substring(0, lineStart) + "## " + after);
    }
  };
  const handleBulletList = () => {
    const ta = textareaRef.current;
    if (!ta) return;
    const lineStart = localContent.lastIndexOf("\n", ta.selectionStart) + 1;
    const after = localContent.substring(lineStart);
    if (after.startsWith("- ")) {
      setLocalContent(localContent.substring(0, lineStart) + after.substring(2));
    } else {
      setLocalContent(localContent.substring(0, lineStart) + "- " + after);
    }
  };

  if (planLoading || sectionsLoading) {
    return (
      <SafeArea className="bg-neutral-50 min-h-dvh flex items-center justify-center">
        <Spinner size="lg" />
      </SafeArea>
    );
  }

  if (!plan) return null;

  return (
    <SafeArea className="bg-neutral-50 min-h-dvh flex flex-col">
      {/* NavBar */}
      {mode === "navigate" ? (
        <NavBar
          title={plan.title}
          showBack
          onBack={() => navigate(-1)}
          rightActions={[{
            icon: <MoreHorizontal size={24} />,
            label: "更多",
            onPress: () => {},
          }]}
        />
      ) : (
        <NavBar
          title={selectedChapter?.title ?? ""}
          showBack
          onBack={handleBackToNavigate}
          rightActions={selectedChapter?.aiGeneratable ? [{
            icon: <Sparkles size={22} />,
            label: "AI生成",
            onPress: handleAIGenerate,
          }] : undefined}
        />
      )}

      {/* AI 生成横幅 + 进度条 */}
      {generationBanner && (
        <div className={`px-md py-3 border-b ${
          generationBanner.status === "generating" ? "bg-primary-50 border-primary-100" :
          generationBanner.status === "done" ? "bg-green-50 border-green-100" :
          "bg-amber-50 border-amber-100"
        }`}>
          <div className="flex items-center gap-sm mb-2">
            {generationBanner.status === "generating" && (
              <Loader2 size={16} className="animate-spin text-primary-600 shrink-0" />
            )}
            {generationBanner.status === "done" && (
              <Check size={16} className="text-green-600 shrink-0" />
            )}
            {generationBanner.status === "cancelled" && (
              <AlertTriangle size={16} className="text-amber-600 shrink-0" />
            )}
            <span className={`flex-1 text-body-sm ${
              generationBanner.status === "generating" ? "text-primary-600" :
              generationBanner.status === "done" ? "text-green-600" :
              "text-amber-600"
            }`}>
              {generationBanner.message}
            </span>
            {generationBanner.status === "generating" && (
              <button
                className="text-red-500 text-caption font-medium shrink-0"
                onClick={handleCancelGeneration}
              >
                取消
              </button>
            )}
          </div>
          {generationBanner.status === "generating" && (
            <ProgressBar percent={genProgressPct} />
          )}
        </div>
      )}

      {/* 内容区 */}
      <div className="flex-1 overflow-y-auto">
        {mode === "navigate" ? (
          <>
            {failedSections.length > 0 && (
              <div className="mx-md mt-sm p-sm rounded-md bg-amber-50 border border-amber-100 flex items-center gap-sm">
                <AlertTriangle size={16} className="text-amber-600 shrink-0" />
                <span className="flex-1 text-body-sm text-amber-700">
                  以下章节生成失败：{failedSections.map((f) => f.title).join("、")}
                </span>
                <button
                  className="text-body-sm font-medium text-amber-700 underline shrink-0"
                  onClick={handleRetryFailed}
                >
                  重试
                </button>
              </div>
            )}
            <ChapterTree
              chapters={chapters}
              sectionStates={sectionStates}
              selectedKey={null}
              onSelect={handleSelectChapter}
            />
            <div className="flex items-center h-14 bg-white border-t border-neutral-100 mt-sm"
                 style={{ paddingBottom: "var(--safe-bottom, 0px)" }}>
              <button
                className="flex-1 flex items-center justify-center gap-xs text-primary-600 font-medium"
                onClick={() => {
                  if (batchChapters.length === 0) {
                    showToast?.({ type: "info", message: "没有可生成的章节" });
                    return;
                  }
                  setBatchSheetOpen(true);
                }}
              >
                <Sparkles size={20} /> 批量生成
              </button>
              <div className="w-px h-6 bg-neutral-200" />
              <button
                className="w-14 h-14 flex items-center justify-center text-neutral-600"
                onClick={() => navigate(`/m/plans/${planId}/preview`)}
              >
                <Download size={22} />
              </button>
              <div className="w-px h-6 bg-neutral-200" />
              <button
                className="w-14 h-14 flex items-center justify-center text-primary-600"
                onClick={() => saveVersionMut.mutate()}
                disabled={saveVersionMut.isPending}
              >
                {saveVersionMut.isPending ? <Loader2 size={22} className="animate-spin" /> : <Save size={22} />}
              </button>
              <div className="w-px h-6 bg-neutral-200" />
              <button
                className="w-14 h-14 flex items-center justify-center text-neutral-600"
                onClick={() => navigate(`/m/plans/${planId}/versions`)}
              >
                <GitBranch size={22} />
              </button>
            </div>
            <AIGenerationSheet
              open={batchSheetOpen}
              onClose={() => setBatchSheetOpen(false)}
              mode="batch"
              planId={planId!}
              enterpriseName={plan.enterprise_name}
              contextSummary={{ riskCount: 0, resourceCount: 0 }}
              chapters={batchChapters}
              onGenerate={(selectedKeys) => handleBatchGenerate(selectedKeys)}
            />
          </>
        ) : (
          <div className="flex-1 flex flex-col">
            {selectedChapter?.autoFill && (
              <button
                className="w-full h-10 bg-indigo-600 text-white text-body-sm font-medium"
                onClick={async () => {
                  try {
                    const sec = await autofillSection(planId!, selectedChapter!.key);
                    setLocalContent(sec.content || "");
                    autoSave(sec.content || "");
                    showToast?.({ type: "success", message: "自动填充完成" });
                  } catch (e: any) {
                    showToast?.({ type: "error", message: e?.message || "自动填充失败" });
                  }
                }}
              >
                自动填充
              </button>
            )}
            <MobileEditor
              ref={textareaRef}
              value={localContent}
              onChange={(v) => {
                setLocalContent(v);
                autoSave(v);
              }}
              placeholder="点击下方工具栏编辑内容，或点击右上角 ✨ AI 生成"
              onFocus={() => setToolbarVisible(true)}
            />
            <div className="h-7 bg-neutral-50 border-t border-neutral-100 flex items-center justify-between px-md text-caption text-neutral-400">
              <span>字数：{localContent.length.toLocaleString()}</span>
              <span>{saveMutation.isPending ? "保存中…" : "已自动保存"}</span>
            </div>
          </div>
        )}
      </div>

      {/* 编辑工具栏 */}
      <EditorToolbar
        visible={toolbarVisible && mode === "edit" && !generating}
        onBold={handleBold}
        onItalic={handleItalic}
        onHeading={handleHeading}
        onBulletList={handleBulletList}
        onUndo={() => {}}
        onRedo={() => {}}
        activeStates={{ bold: false, italic: false, heading: false, list: false }}
      />
    </SafeArea>
  );
}
