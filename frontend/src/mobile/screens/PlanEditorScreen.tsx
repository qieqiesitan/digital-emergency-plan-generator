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
import type { ChapterNode } from "@/mobile/components/plan/ChapterTree";
import { getPlan, createVersion } from "@/services/planService";
import { listSections, updateSection } from "@/services/planService";
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

  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const abortRef = useRef<AbortController | null>(null);

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
        aiGeneratable: true,
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
          rightActions={[{
            icon: <Sparkles size={22} />,
            label: "AI生成",
            onPress: handleAIGenerate,
          }]}
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
                onClick={() => showToast?.("批量生成功能请在桌面端使用", "info")}
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
          </>
        ) : (
          <div className="flex-1 flex flex-col">
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
