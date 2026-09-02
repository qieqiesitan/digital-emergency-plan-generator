// @ts-nocheck
import React, { useState, useEffect, useRef, useCallback, useMemo } from "react";
import { useParams, useNavigate, useSearchParams } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  MoreHorizontal, Sparkles, Download,
  GitBranch, Loader2, ArrowLeft, Check,
  AlertTriangle, Save, ClipboardCheck,
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
import { getPlan, createVersion, fetchPlanReview, applyPlanReview } from "@/services/planService";
import { listSections, updateSection, autofillSection } from "@/services/planService";
import type { PlanReviewIssue, PlanReviewResult } from "@/services/planService";
import { generateBatchBackground, getGenerationStatus } from "@/services/generationService";
import { sseFetch } from "@/services/sseFetch";
import { useAppStore } from "@/mobile/store/appStore";
import { useDraftStore } from "@/mobile/store/draftStore";

type EditorMode = "navigate" | "edit";

// B15 修复：保存失败时按 planId 将章节草稿持久化到 localStorage，
// 进入章节时优先恢复（避免刷新/切回后丢失），保存成功后清除。
const DRAFT_STORAGE_PREFIX = "plan_editor_draft:";

interface StoredDraft {
  content: string;
  updatedAt: number;
}

function loadStoredDraft(planId: string, sectionKey: string): string | null {
  try {
    const raw = localStorage.getItem(`${DRAFT_STORAGE_PREFIX}${planId}`);
    if (!raw) return null;
    const map = JSON.parse(raw) as Record<string, StoredDraft>;
    return map[sectionKey]?.content ?? null;
  } catch {
    return null;
  }
}

function persistStoredDraft(planId: string, sectionKey: string, content: string): void {
  try {
    const raw = localStorage.getItem(`${DRAFT_STORAGE_PREFIX}${planId}`);
    const map: Record<string, StoredDraft> = raw ? JSON.parse(raw) : {};
    map[sectionKey] = { content, updatedAt: Date.now() };
    localStorage.setItem(`${DRAFT_STORAGE_PREFIX}${planId}`, JSON.stringify(map));
  } catch {
    // localStorage 不可用（隐私模式/配额满）时忽略，仍有 toast 明确提示保存失败
  }
}

function clearStoredDraft(planId: string, sectionKey: string): void {
  try {
    const raw = localStorage.getItem(`${DRAFT_STORAGE_PREFIX}${planId}`);
    if (!raw) return;
    const map = JSON.parse(raw) as Record<string, StoredDraft>;
    delete map[sectionKey];
    if (Object.keys(map).length === 0) {
      localStorage.removeItem(`${DRAFT_STORAGE_PREFIX}${planId}`);
    } else {
      localStorage.setItem(`${DRAFT_STORAGE_PREFIX}${planId}`, JSON.stringify(map));
    }
  } catch {
    // ignore
  }
}

export default function PlanEditorScreen() {
  const { id: planId } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { showToast } = useToast();
  const { setKeyboard } = useAppStore();
  const { addDraft, removeDraft } = useDraftStore();

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
  const [reviewSheetOpen, setReviewSheetOpen] = useState(false);
  const [reviewLoading, setReviewLoading] = useState(false);
  const [reviewResult, setReviewResult] = useState<PlanReviewResult | null>(null);
  const [applyReviewLoading, setApplyReviewLoading] = useState(false);
  const [saveStatus, setSaveStatus] = useState<"saved" | "dirty" | "saving" | "error">("saved");

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

  // 保存章节（B15：不再静默吞错——失败时状态栏报错 + toast 提示，并把内容暂存为本地草稿）
  const saveMutation = useMutation({
    mutationFn: async (content: string) => {
      if (!planId || !selectedChapter) return;
      await updateSection(planId, selectedChapter.key, { content });
    },
    onMutate: () => setSaveStatus("saving"),
    onSuccess: () => {
      setSaveStatus("saved");
      if (planId && selectedChapter) {
        clearStoredDraft(planId, selectedChapter.key);
        removeDraft(planId, selectedChapter.key);
      }
      // B12：这里只刷新章节树状态，不把服务器值写回 localContent，
      // 避免自动保存/生成期间的 refetch 覆盖正在编辑的内容。
      queryClient.invalidateQueries({ queryKey: ["plan-sections", planId] });
    },
    onError: (_error, content) => {
      setSaveStatus("error");
      if (planId && selectedChapter) {
        persistStoredDraft(planId, selectedChapter.key, content);
        addDraft(planId, selectedChapter.key, content);
      }
      showToast?.({ type: "error", message: "保存失败，内容已暂存为本地草稿" });
    },
  });

  // 保存版本快照（B2：此前引用了从未定义的 saveVersionMut，点击必崩）
  const saveVersionMut = useMutation({
    mutationFn: () => createVersion(planId!, "手动保存版本"),
    onSuccess: () => {
      showToast?.({ type: "success", message: "版本已保存" });
      queryClient.invalidateQueries({ queryKey: ["versions", planId] });
    },
    onError: () => {
      showToast?.({ type: "error", message: "保存版本失败" });
    },
  });

  // 自动保存
  const autoSave = useCallback((content: string) => {
    setSaveStatus("dirty");
    if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    saveTimerRef.current = setTimeout(() => {
      saveMutation.mutate(content);
    }, 3000);
  }, [saveMutation]);

  const handleSelectChapter = useCallback((chapter: ChapterNode) => {
    setSelectedChapter(chapter);
    setMode("edit");
    const sec = sections.find(s => s.section_key === chapter.key);
    const serverContent = sec?.content ?? "";
    // B15/B12：有本地未保存草稿时优先恢复，避免服务器旧值覆盖正在编辑的内容
    const draft = loadStoredDraft(planId!, chapter.key);
    if (draft !== null && draft !== serverContent) {
      setLocalContent(draft);
      setSaveStatus("dirty");
      showToast?.({ type: "info", message: "已恢复未保存的草稿" });
    } else {
      setLocalContent(serverContent);
      setSaveStatus("saved");
    }
    setToolbarVisible(true);
    setTimeout(() => {
      textareaRef.current?.focus();
    }, 100);
  }, [sections, planId, showToast]);

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
  const handleAIGenerate = useCallback(() => {
    if (!planId || !selectedChapter) return;
    abortRef.current?.abort();
    abortRef.current = new AbortController();

    setGenerating(true);
    setGenProgressPct(0);
    setGenProgressMsg(`AI 正在撰写"${selectedChapter.title}"…`);
    setGenerationBanner({ status: "generating", message: `AI 正在撰写"${selectedChapter.title}"…` });

    const targetPlanId = planId;
    const targetChapterKey = selectedChapter.key;
    const startContent = localContent;
    let accumulated = startContent;

    void sseFetch({
      path: `/plans/${targetPlanId}/generate/${targetChapterKey}`,
      method: "POST",
      body: { custom_instruction: null },
      signal: abortRef.current.signal,
      errorMessage: "生成请求失败",
      onData: (data) => {
        try {
          const event = JSON.parse(data);
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
        } catch { /* skip malformed events */ }
      },
      onComplete: () => {
        setGenerating(false);
        setGenProgressPct(100);
        setGenerationBanner({ status: "done", message: "✓ 生成完成" });
        autoSave(accumulated);
        setTimeout(() => setGenerationBanner(null), 2000);
      },
      onError: (message) => {
        setGenerating(false);
        setGenerationBanner(null);
        showToast?.({ type: "error", message: message || "生成失败" });
      },
    }).catch((err: any) => {
      setGenerating(false);
      setGenerationBanner(null);
      showToast?.({ type: "error", message: err?.message ?? "生成失败" });
    });
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

  // ========== AI 审查（结果展示 + 应用修订） ==========
  const handleOpenReview = useCallback(async () => {
    if (!planId) return;
    setReviewLoading(true);
    try {
      const data = await fetchPlanReview(planId);
      setReviewResult(data);
      setReviewSheetOpen(true);
    } catch (e: any) {
      showToast?.({ type: "error", message: e?.message || "获取审查结果失败" });
    } finally {
      setReviewLoading(false);
    }
  }, [planId, showToast]);

  const handleApplyReview = useCallback(async () => {
    if (!planId) return;
    setApplyReviewLoading(true);
    try {
      const r = await applyPlanReview(planId, "llm");
      showToast?.({ type: "success", message: `已应用 ${r.applied.length} 个章节的修订` });
      setReviewSheetOpen(false);
      setReviewResult(null);
      queryClient.invalidateQueries({ queryKey: ["plan-sections", planId] });
      queryClient.invalidateQueries({ queryKey: ["plan", planId] });
    } catch (e: any) {
      showToast?.({ type: "error", message: e?.message || "应用修订失败" });
    } finally {
      setApplyReviewLoading(false);
    }
  }, [planId, showToast, queryClient]);

  const reviewGroups = useMemo(() => {
    if (!reviewResult) return [];
    const map = new Map<string, {
      section_key: string;
      section_title: string;
      issues: PlanReviewIssue[];
      warnings: PlanReviewIssue[];
    }>();
    reviewResult.issues.forEach((it) => {
      const g = map.get(it.section_key) || {
        section_key: it.section_key,
        section_title: it.section_title || it.section_key,
        issues: [],
        warnings: [],
      };
      g.issues.push(it);
      map.set(it.section_key, g);
    });
    reviewResult.warnings.forEach((it) => {
      const g = map.get(it.section_key) || {
        section_key: it.section_key,
        section_title: it.section_title || it.section_key,
        issues: [],
        warnings: [],
      };
      g.warnings.push(it);
      map.set(it.section_key, g);
    });
    return Array.from(map.values());
  }, [reviewResult]);

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
                className="w-14 h-14 flex items-center justify-center text-primary-600"
                onClick={handleOpenReview}
                disabled={reviewLoading}
              >
                {reviewLoading ? <Loader2 size={22} className="animate-spin" /> : <ClipboardCheck size={22} />}
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
            <BottomSheet open={reviewSheetOpen} onClose={() => setReviewSheetOpen(false)} height="70%">
              <div className="px-md py-sm">
                <div className="flex items-center justify-between mb-sm">
                  <span className="text-h3 font-semibold text-neutral-900">AI 审查结果</span>
                  <button className="text-caption text-neutral-500" onClick={() => setReviewSheetOpen(false)}>
                    关闭
                  </button>
                </div>
                {!reviewResult ? (
                  <div className="py-lg text-center text-neutral-400">暂无审查结果</div>
                ) : reviewResult.issues.length === 0 && reviewResult.warnings.length === 0 ? (
                  <div className="py-lg text-center text-green-600">✓ 未发现问题，预案质量良好</div>
                ) : (
                  <div className="flex flex-col gap-sm">
                    {reviewGroups.map((g) => (
                      <div key={g.section_key} className="rounded-md border border-neutral-100 p-sm">
                        <div className="text-body-sm font-semibold text-neutral-800 mb-xs">{g.section_title}</div>
                        {g.issues.map((it, i) => (
                          <div key={`issue-${i}`} className="text-body-sm text-red-600 flex gap-xs">
                            <span>•</span>
                            <span className="flex-1">{it.issue}</span>
                          </div>
                        ))}
                        {g.warnings.map((it, i) => (
                          <div key={`warning-${i}`} className="text-body-sm text-amber-600 flex gap-xs">
                            <span>•</span>
                            <span className="flex-1">
                              {it.warning}
                              {it.evidence ? `（${it.evidence}）` : ""}
                            </span>
                          </div>
                        ))}
                      </div>
                    ))}
                  </div>
                )}
                {reviewResult && reviewResult.issues.length > 0 && (
                  <button
                    className="mt-md w-full h-11 rounded-md bg-primary-600 text-white text-body-sm font-medium disabled:opacity-50"
                    disabled={applyReviewLoading}
                    onClick={handleApplyReview}
                  >
                    {applyReviewLoading ? "修订中…" : "应用修订（LLM）"}
                  </button>
                )}
                <button
                  className="mt-sm w-full h-11 rounded-md border border-neutral-200 text-neutral-600 text-body-sm font-medium"
                  onClick={() => { setReviewSheetOpen(false); navigate(`/m/plans/${planId}/versions`); }}
                >
                  回退（版本历史）
                </button>
                <div className="mt-xs text-caption text-neutral-400 text-center">
                  应用修订前会自动保存版本快照，可在版本历史中回退。
                </div>
              </div>
            </BottomSheet>
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
              <span className={saveStatus === "error" ? "text-red-500" : undefined}>
                {saveStatus === "saving"
                  ? "保存中…"
                  : saveStatus === "dirty"
                  ? "未保存"
                  : saveStatus === "error"
                  ? "保存失败"
                  : "已自动保存"}
              </span>
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
