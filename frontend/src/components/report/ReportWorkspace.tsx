import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Alert,
  Badge,
  Button,
  Card,
  Empty,
  message,
  Modal,
  Progress,
  Space,
  Spin,
  Tag,
  Typography,
} from "antd";
import {
  AuditOutlined,
  CheckCircleFilled,
  CloseCircleFilled,
  ExportOutlined,
  EyeOutlined,
  FileSyncOutlined,
  LoadingOutlined,
  SaveOutlined,
  SettingOutlined,
  StopOutlined,
  ThunderboltOutlined,
} from "@ant-design/icons";
import type {
  ReportAdapter,
  ReportChapter,
  ReportDocument,
  ReportIssue,
} from "@/types/reportWorkspace";
import type { ChapterDef } from "@/services/riskAssessmentService";
import { createRiskAssessmentVersion } from "@/services/riskAssessmentService";
import { createResourceInvestigationVersion } from "@/services/resourceInvestigationService";
import TiptapEditor from "@/components/report/TiptapEditor";
import ReportChapterActions from "@/components/report/ReportChapterActions";
import ReviewDrawer from "@/components/report/ReviewDrawer";
import { StylePanel, DEFAULT_STYLE } from "@/components/plan/StylePanel";
import DiffPreviewModal from "@/components/plan/DiffPreviewModal";
import AiNotConfiguredHint from "@/components/common/AiNotConfiguredHint";
import { aiErrorDisplay } from "@/utils/aiUnavailable";
import { htmlToMarkdown, renderReportMarkdown } from "@/utils/reportMarkdown";

const { Text, Title } = Typography;

const RISK_FALLBACK_CHAPTERS: ChapterDef[] = [
  { key: "ch1_hazard_id", title: "一、危险有害因素辨识分析" },
  { key: "ch2_summary", title: "二、危险有害因素辨识汇总" },
  { key: "ch3_risk_eval", title: "三、风险等级评估" },
  { key: "ch4_measures", title: "四、现有管控措施评价" },
  { key: "ch5_conclusion", title: "五、风险评估结论与建议" },
];

const RESOURCE_FALLBACK_CHAPTERS: ChapterDef[] = [
  { key: "ch1_purpose", title: "一、调查目的与依据" },
  { key: "ch2_basic_info", title: "二、企业基本情况与风险概况" },
  { key: "ch3_internal", title: "三、内部应急资源调查" },
  { key: "ch4_external", title: "四、外部救援资源调查" },
  { key: "ch5_gap_analysis", title: "五、应急资源需求与能力评估" },
  { key: "ch6_conclusion", title: "六、调查结论与建议" },
];

interface ReportWorkspaceProps {
  adapter: ReportAdapter;
  enterpriseId: string;
  meta: { emptyTitle: string; emptyDesc: string; generateLabel: string };
  /** 报告类型：risk=风险评估，resource=应急资源调查；决定版本/预览路由与章节定义 */
  kind?: "risk" | "resource";
  /** 章节定义；缺省时按 kind 使用内置定义（与后端 CHAPTER_DEFINITIONS 对齐） */
  chapters?: ChapterDef[];
}

type SaveState = "idle" | "saving" | "saved" | "error";
type GenerationMode = "full" | "chapter" | null;

interface DiffItem {
  sectionKey: string;
  original: string;
  revised: string;
}

const SAVE_DEBOUNCE_MS = 1500;

/** 失败章节列表纯 reducer：按 key 去重追加 */
export function addFailedChapter(
  list: ReportChapter[],
  key: string,
  title?: string,
): ReportChapter[] {
  if (!key || list.some((f) => f.key === key)) return list;
  return [...list, { key, title: title || key, content: "" }];
}

export default function ReportWorkspace({
  adapter,
  enterpriseId,
  meta,
  kind = "risk",
  chapters: chapterDefsProp,
}: ReportWorkspaceProps) {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [doc, setDoc] = useState<ReportDocument | null>(null);
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [contentByKey, setContentByKey] = useState<Record<string, string>>({});
  const [saveState, setSaveState] = useState<Record<string, SaveState>>({});
  const [generating, setGenerating] = useState<GenerationMode>(null);
  const [generatingKeys, setGeneratingKeys] = useState<Set<string>>(new Set());
  const [failedChapters, setFailedChapters] = useState<ReportChapter[]>([]);
  const [batchProgress, setBatchProgress] = useState({ current: 0, total: 0, message: "" });
  const [thinkingText, setThinkingText] = useState("");
  const [aiUnavailable, setAiUnavailable] = useState(false);

  const [styleOpen, setStyleOpen] = useState(false);
  const [styleValue, setStyleValue] = useState<typeof DEFAULT_STYLE>(DEFAULT_STYLE);
  const [savingStyle, setSavingStyle] = useState(false);

  const [reviewOpen, setReviewOpen] = useState(false);
  const [reviewIssues, setReviewIssues] = useState<ReportIssue[]>([]);
  const [reviewing, setReviewing] = useState(false);
  const [applyingReview, setApplyingReview] = useState(false);
  const [diffQueue, setDiffQueue] = useState<DiffItem[]>([]);
  const [diffIndex, setDiffIndex] = useState(-1);

  const [genModalKey, setGenModalKey] = useState<string | null>(null);
  const [savingVersion, setSavingVersion] = useState(false);
  const [merging, setMerging] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [collapsed, setCollapsed] = useState(false);

  const allControllersRef = useRef<AbortController[]>([]);
  const genBufferRef = useRef<Record<string, string>>({});
  const pendingSavesRef = useRef<Record<string, string>>({});
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const saveChainRef = useRef<Promise<void>>(Promise.resolve());
  const dirtyRef = useRef<Set<string>>(new Set());

  const fallbackChapters = useMemo(
    () => (kind === "resource" ? RESOURCE_FALLBACK_CHAPTERS : RISK_FALLBACK_CHAPTERS),
    [kind],
  );

  const chapterDefs = useMemo(() => {
    const base = chapterDefsProp && chapterDefsProp.length > 0 ? chapterDefsProp : fallbackChapters;
    // 若已加载草稿章节（key/title），优先用草稿顺序展示，补上缺失定义
    const loaded = doc?.chapters || [];
    const known = new Set<string>();
    const merged: ChapterDef[] = [];
    loaded.forEach((ch) => {
      known.add(ch.key);
      merged.push({ key: ch.key, title: ch.title });
    });
    base.forEach((c) => {
      if (!known.has(c.key)) merged.push({ key: c.key, title: c.title });
    });
    return merged;
  }, [chapterDefsProp, fallbackChapters, doc]);

  const selectedDef = chapterDefs.find((c) => c.key === selectedKey) || null;
  const editorHtml = selectedKey ? renderReportMarkdown(contentByKey[selectedKey] || "") : "";
  const chapterTitleMap = useMemo(() => {
    const map: Record<string, string> = {};
    chapterDefs.forEach((c) => { map[c.key] = c.title; });
    return map;
  }, [chapterDefs]);

  /** 更新某个章节的内容（markdown 规范），供 SSE / 编辑 / diff 应用共用 */
  const setChapterContent = useCallback((key: string, md: string) => {
    setContentByKey((prev) => ({ ...prev, [key]: md }));
  }, []);

  const saveOne = useCallback(
    async (key: string, md: string) => {
      setSaveState((prev) => ({ ...prev, [key]: "saving" }));
      try {
        await adapter.saveChapter(enterpriseId, key, md);
        setSaveState((prev) => ({ ...prev, [key]: "saved" }));
        dirtyRef.current.delete(key);
      } catch (err) {
        setSaveState((prev) => ({ ...prev, [key]: "error" }));
        const disp = aiErrorDisplay(
          err instanceof Error ? err.message : undefined,
          "章节保存失败，点击重试",
        );
        if (disp.notConfigured) setAiUnavailable(true);
        else message.error(disp.text);
      }
    },
    [adapter, enterpriseId],
  );

  const flushPendingSaves = useCallback(() => {
    if (saveTimerRef.current) {
      clearTimeout(saveTimerRef.current);
      saveTimerRef.current = null;
    }
    const keys = Object.keys(pendingSavesRef.current);
    if (keys.length === 0) return;
    const snapshots = { ...pendingSavesRef.current };
    pendingSavesRef.current = {};
    keys.forEach((key) => {
      if (dirtyRef.current.has(key) || snapshots[key] !== undefined) {
        const content = snapshots[key];
        if (content !== undefined) {
          saveChainRef.current = saveChainRef.current
            .then(() => saveOne(key, content))
            .catch(() => {});
        }
      }
    });
  }, [saveOne]);

  /** 编辑内容进入防抖保存队列（1.5s） */
  const scheduleSave = useCallback(
    (key: string, md: string) => {
      pendingSavesRef.current[key] = md;
      dirtyRef.current.add(key);
      setSaveState((prev) => ({ ...prev, [key]: "idle" }));
      if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
      saveTimerRef.current = setTimeout(() => {
        saveTimerRef.current = null;
        flushPendingSaves();
      }, SAVE_DEBOUNCE_MS);
    },
    [flushPendingSaves],
  );

  const loadDocument = useCallback(async () => {
    try {
      const next = await adapter.load(enterpriseId);
      setDoc(next);
      setContentByKey((prev) => {
        const merged = { ...prev };
        (next.chapters || []).forEach((ch) => {
          // 保留用户在编辑器中的未保存改动；其余以服务端为准
          if (!dirtyRef.current.has(ch.key)) merged[ch.key] = ch.content || "";
        });
        return merged;
      });
      setSaveState({});
      setSelectedKey((prev) => prev ?? next.chapters?.[0]?.key ?? null);
    } catch {
      // 无报告行 → 空态（在生成前 report 不存在，load 404 属预期，不打断首次生成引导）
      setDoc(null);
    } finally {
      setLoading(false);
    }
  }, [adapter, enterpriseId]);

  useEffect(() => {
    setLoading(true);
    void loadDocument();
  }, [loadDocument]);

  // 卸载/离开前提示未保存内容
  useEffect(() => {
    const onBeforeUnload = (e: BeforeUnloadEvent) => {
      if (dirtyRef.current.size > 0) {
        e.preventDefault();
        e.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", onBeforeUnload);
    return () => {
      window.removeEventListener("beforeunload", onBeforeUnload);
      // 离开页面即停止进行中的生成：后端会把已完成章节落为草稿，
      // 避免“生成到一半退出”后整份作废或残留 generating 空行
      allControllersRef.current.forEach((c) => c.abort());
      allControllersRef.current = [];
      flushPendingSaves();
    };
  }, [flushPendingSaves]);

  // 章节切换前立即落盘待保存内容
  const selectChapter = useCallback(
    (key: string) => {
      flushPendingSaves();
      setSelectedKey(key);
    },
    [flushPendingSaves],
  );

  const showGenError = useCallback(
    (raw: string | null | undefined, fallback: string) => {
      const disp = aiErrorDisplay(raw, fallback);
      if (disp.notConfigured) setAiUnavailable(true);
      else message.error(disp.text);
    },
    [],
  );

  const stopGeneration = useCallback(() => {
    allControllersRef.current.forEach((c) => c.abort());
    allControllersRef.current = [];
    setGenerating(null);
    setGeneratingKeys(new Set());
    setBatchProgress({ current: 0, total: 0, message: "" });
  }, []);

  /** 全量生成：adapter.generateAll（SSE） */
  const startFullGenerate = useCallback(async () => {
    if (doc?.status === "completed") {
      const confirmed = await new Promise<boolean>((resolve) => {
        Modal.confirm({
          title: "重新生成将覆盖当前报告，确定继续？",
          okText: "重新生成",
          okButtonProps: { danger: true },
          cancelText: "取消",
          onOk: () => resolve(true),
          onCancel: () => resolve(false),
        });
      });
      if (!confirmed) return;
    }
    if (generating) return;
    flushPendingSaves();
    allControllersRef.current.forEach((c) => c.abort());
    allControllersRef.current = [];
    genBufferRef.current = {};
    setGenerating("full");
    setGeneratingKeys(new Set());
    setFailedChapters([]);
    setBatchProgress({ current: 0, total: 0, message: "准备开始..." });
    setAiUnavailable(false);

    const controller = adapter.generateAll(
      enterpriseId,
      {
        onEvent: (event) => {
          switch (event.type) {
            case "thinking": {
              setThinkingText(event.message || "");
              break;
            }
            case "progress": {
              setThinkingText("");
              const sk = event.section_key as string | undefined;
              if (sk) setGeneratingKeys((prev) => new Set(prev).add(sk));
              setBatchProgress((prev) => ({
                current: event.current ?? prev.current,
                total: event.total ?? prev.total,
                message: event.message || prev.message,
              }));
              break;
            }
            case "chunk": {
              setThinkingText("");
              const sk = event.section_key as string | undefined;
              if (sk && event.content) {
                genBufferRef.current[sk] = (genBufferRef.current[sk] || "") + String(event.content);
                setChapterContent(sk, genBufferRef.current[sk]);
              }
              break;
            }
            case "section_done": {
              setThinkingText("");
              const sk = event.section_key as string | undefined;
              if (sk) {
                setGeneratingKeys((prev) => {
                  const n = new Set(prev);
                  n.delete(sk);
                  return n;
                });
                setSaveState((prev) => ({ ...prev, [sk]: "saved" }));
              }
              break;
            }
            case "batch_done": {
              setThinkingText("");
              const rawChapters = (event.chapters as unknown) || event.content || "";
              if (typeof rawChapters === "string" && rawChapters.trim()) {
                try {
                  const parsed = JSON.parse(rawChapters);
                  if (Array.isArray(parsed)) {
                    const merged: Record<string, string> = {};
                    parsed.forEach((c) => {
                      if (c && c.key) merged[c.key] = c.content || "";
                    });
                    genBufferRef.current = { ...genBufferRef.current, ...merged };
                  }
                } catch {
                  // 后端 chapters 可能不是 JSON 字符串；忽略，内容已按 chunk 累积
                }
              }
              setGenerating(null);
              setGeneratingKeys(new Set());
              setBatchProgress({ current: 0, total: 0, message: "" });
              const failed = event.failed_sections as Array<{ key: string; title?: string }> | undefined;
              if (failed && failed.length > 0) {
                setFailedChapters(
                  failed.map((f) => ({ key: f.key, title: f.title || f.key, content: "" })),
                );
                message.warning(`${failed.length} 个章节生成失败，可单独重试`);
              } else {
                message.success("报告草稿生成完成");
              }
              void loadDocument();
              break;
            }
            case "error": {
              setThinkingText("");
              const sk = event.section_key as string | undefined;
              if (sk) {
                setFailedChapters((prev) => addFailedChapter(prev, sk, sk));
              }
              showGenError(event.message, "生成失败，请重试");
              setGenerating(null);
              setGeneratingKeys(new Set());
              break;
            }
          }
        },
        onError: (error) => {
          setThinkingText("");
          showGenError(error, "生成失败，请重试");
          setGenerating(null);
          setGeneratingKeys(new Set());
        },
        onComplete: () => {},
      },
    );
    allControllersRef.current.push(controller);
  }, [
    adapter, enterpriseId, doc, generating, flushPendingSaves,
    setChapterContent, showGenError, loadDocument,
  ]);

  /** 单章生成/重生成：adapter.generateChapter / regenerateChapter（SSE） */
  const runChapterGeneration = useCallback(
    (key: string, mode: "generate" | "regenerate") => {
      const def = fallbackChapters.find((c) => c.key === key) || chapterDefs.find((c) => c.key === key);
      const title = def?.title || key;
      const previous = contentByKey[key] || "";
      flushPendingSaves();
      allControllersRef.current.forEach((c) => c.abort());
      allControllersRef.current = [];
      genBufferRef.current = {};
      setGenerating("chapter");
      setGeneratingKeys(new Set([key]));
      setAiUnavailable(false);

      const cb = {
        onEvent: (event: any) => {
          switch (event.type) {
            case "thinking": {
              setThinkingText(event.message || "");
              break;
            }
            case "chunk": {
              setThinkingText("");
              if (event.content) {
                genBufferRef.current[key] = (genBufferRef.current[key] || "") + String(event.content);
                setChapterContent(key, genBufferRef.current[key]);
              }
              break;
            }
            case "section_done": {
              setThinkingText("");
              setGenerating(null);
              setGeneratingKeys(new Set());
              const finalMd = genBufferRef.current[key] || "";
              setChapterContent(key, finalMd);
              setSaveState((prev) => ({ ...prev, [key]: "saved" }));
              if (mode === "regenerate" && previous && finalMd && previous !== finalMd) {
                setDiffQueue([{ sectionKey: key, original: previous, revised: finalMd }]);
                setDiffIndex(0);
              } else if (previous && finalMd) {
                message.success(`「${title}」已重新生成`);
              }
              break;
            }
            case "error": {
              setThinkingText("");
              setGenerating(null);
              setGeneratingKeys(new Set());
              showGenError(event.message, "单章生成失败");
              break;
            }
          }
        },
        onError: (error: string) => {
          setThinkingText("");
          setGenerating(null);
          setGeneratingKeys(new Set());
          showGenError(error, "单章生成失败");
        },
        onComplete: () => {},
      };
      const controller =
        mode === "regenerate"
          ? adapter.regenerateChapter(enterpriseId, key, cb)
          : adapter.generateChapter(enterpriseId, key, cb);
      allControllersRef.current.push(controller);
    },
    [
      adapter, enterpriseId, contentByKey, fallbackChapters, chapterDefs,
      flushPendingSaves, setChapterContent, showGenError,
    ],
  );

  /** 保存版本：按 kind 调对应 service 的 createVersion */
  const handleSaveVersion = useCallback(async () => {
    if (savingVersion) return;
    setSavingVersion(true);
    try {
      if (kind === "resource") {
        await createResourceInvestigationVersion(enterpriseId);
      } else {
        await createRiskAssessmentVersion(enterpriseId);
      }
      message.success("版本已保存");
    } catch (err) {
      showGenError(err instanceof Error ? err.message : undefined, "保存版本失败");
    } finally {
      setSavingVersion(false);
    }
  }, [kind, enterpriseId, savingVersion, showGenError]);

  /** 合并定稿：adapter.merge */
  const handleMerge = useCallback(async () => {
    if (merging) return;
    const chapters: ReportChapter[] = chapterDefs
      .map((c) => ({
        key: c.key,
        title: c.title,
        content: contentByKey[c.key] || "",
      }))
      .filter((c) => c.content && c.content.trim());
    if (chapters.length === 0) {
      message.warning("请先生成章节内容再合并");
      return;
    }
    setMerging(true);
    try {
      await adapter.merge(enterpriseId, chapters);
      message.success("报告合并完成");
      await loadDocument();
    } catch (err) {
      showGenError(err instanceof Error ? err.message : undefined, "合并失败，请重试");
    } finally {
      setMerging(false);
    }
  }, [merging, chapterDefs, contentByKey, adapter, enterpriseId, loadDocument, showGenError]);

  /** AI 审查（确定性规则） */
  const handleReview = useCallback(async () => {
    if (reviewing) return;
    setReviewing(true);
    try {
      const issues = await adapter.review(enterpriseId, null);
      setReviewIssues(issues);
      setReviewOpen(true);
      if (issues.length === 0) {
        // Drawer 内 Empty 提示，不额外打扰
      }
    } catch (err) {
      showGenError(err instanceof Error ? err.message : undefined, "审查失败，请重试");
    } finally {
      setReviewing(false);
    }
  }, [adapter, enterpriseId, reviewing, showGenError]);

  const applyReview = useCallback(
    async (sectionKeys: string[]) => {
      if (applyingReview || sectionKeys.length === 0) return;
      setApplyingReview(true);
      try {
        const applied = await adapter.applyReview(enterpriseId, sectionKeys);
        const diffs: DiffItem[] = applied.map((r) => ({
          sectionKey: r.section_key,
          original: r.original || "",
          revised: r.revised || "",
        }));
        if (diffs.length === 0) {
          message.info("所选章节没有需要修订的内容");
          return;
        }
        setDiffQueue(diffs);
        setDiffIndex(0);
      } catch (err) {
        showGenError(err instanceof Error ? err.message : undefined, "生成修订失败");
      } finally {
        setApplyingReview(false);
      }
    },
    [adapter, enterpriseId, applyingReview, showGenError],
  );

  /** Diff 逐条确认：接受 → 更新内存章节并保存；拒绝 → 保持原文 */
  const closeDiff = useCallback(
    (accepted: boolean) => {
      const item = diffQueue[diffIndex];
      if (item) {
        if (accepted) {
          setChapterContent(item.sectionKey, item.revised);
          // 立即保存修订结果（修订内容较大，不再等防抖窗口）
          setSaveState((prev) => ({ ...prev, [item.sectionKey]: "saving" }));
          void saveOne(item.sectionKey, item.revised);
        }
      }
      if (diffIndex + 1 < diffQueue.length) {
        setDiffIndex((i) => i + 1);
      } else {
        setDiffQueue([]);
        setDiffIndex(-1);
        setReviewOpen(false);
        setReviewIssues([]);
      }
    },
    [diffQueue, diffIndex, saveOne, setChapterContent],
  );

  const openStyleModal = useCallback(async () => {
    setStyleOpen(true);
    try {
      const saved = await adapter.getStyle(enterpriseId);
      setStyleValue({ ...DEFAULT_STYLE, ...saved } as typeof DEFAULT_STYLE);
    } catch {
      // 默认风格兜底
    }
  }, [adapter, enterpriseId]);

  const saveStyle = useCallback(async () => {
    setSavingStyle(true);
    try {
      const stylePayload: Record<string, string> = {
        formality: styleValue.formality,
        detail_level: styleValue.detail_level,
        table_preference: styleValue.table_preference,
        diagram_preference: styleValue.diagram_preference,
        mode: styleValue.mode,
      };
      await adapter.saveStyle(enterpriseId, stylePayload);
      message.success("创作风格已保存");
      setStyleOpen(false);
    } catch (err) {
      showGenError(err instanceof Error ? err.message : undefined, "保存风格失败");
    } finally {
      setSavingStyle(false);
    }
  }, [adapter, enterpriseId, styleValue, showGenError]);

  const currentStatus = generating ? "generating" : doc?.status || "empty";
  /** 上次会话中断残留的 generating 行（当前页面没有正在运行的生成） */
  const interruptedGenerating = doc?.status === "generating" && !generating;
  const partialChapterCount = interruptedGenerating
    ? (doc?.chapters ?? []).filter((c) => c.content && c.content.trim()).length
    : 0;
  const currentChapter = selectedDef;
  const hasDraftContent = Object.values(contentByKey).some((c) => c && c.trim());
  const saveStatus = currentChapter ? saveState[currentChapter.key] || "saved" : "saved";

  if (loading) {
    return (
      <div style={{ display: "flex", justifyContent: "center", padding: 80 }}>
        <Spin size="large" tip="正在加载报告..." />
      </div>
    );
  }

  const toolbar = (
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, marginBottom: 12, flexWrap: "wrap" }}>
      <Space wrap>
        <Text strong style={{ fontSize: 15 }}>
          {doc?.title || meta.emptyTitle}
        </Text>
        {currentStatus === "completed" && <Tag color="green">已完成</Tag>}
        {currentStatus === "draft" && <Tag color="blue">草稿</Tag>}
        {currentStatus === "generating" && <Tag color="processing">生成中</Tag>}
      </Space>
      <Space wrap>
        {currentStatus === "completed" && (
          <Button
            danger
            icon={<ThunderboltOutlined />}
            onClick={() => { setGenerating(null); void startFullGenerate(); }}
          >
            重新生成
          </Button>
        )}
        {!generating && (
          <Button
            icon={<ThunderboltOutlined />}
            onClick={() => void startFullGenerate()}
            disabled={!!generating}
          >
            一键生成全部
          </Button>
        )}
        {generating === "full" && (
          <Button danger icon={<StopOutlined />} onClick={stopGeneration}>
            停止生成
          </Button>
        )}
        {(currentStatus === "draft" || currentStatus === "generating") && (
          <>
            <Button
              icon={<AuditOutlined />}
              loading={reviewing}
              disabled={!!generating}
              onClick={() => void handleReview()}
            >
              AI 审查
            </Button>
            <Button icon={<SettingOutlined />} disabled={!!generating} onClick={() => void openStyleModal()}>
              创作风格
            </Button>
            <Button
              icon={<SaveOutlined />}
              loading={savingVersion}
              disabled={!!generating}
              onClick={() => void handleSaveVersion()}
            >
              保存版本
            </Button>
            <Button
              type="primary"
              icon={<FileSyncOutlined />}
              loading={merging}
              disabled={!hasDraftContent || !!generating}
              onClick={() => void handleMerge()}
            >
              合并定稿
            </Button>
          </>
        )}
        <Button
          icon={<EyeOutlined />}
          disabled={!!generating}
          onClick={() => navigate(`/enterprises/${enterpriseId}/${kind === "resource" ? "resource-investigation" : "risk-assessment"}/preview`)}
        >
          预览
        </Button>
        <Button
          type="primary"
          icon={<ExportOutlined />}
          loading={exporting}
          onClick={() => {
            setExporting(true);
            adapter
              .download(enterpriseId)
              .catch((err: unknown) =>
                message.error(
                  (err as Error)?.message || "导出失败，请重试",
                ),
              )
              .finally(() => setExporting(false));
          }}
        >
          导出
        </Button>
      </Space>
    </div>
  );

  if (!doc && !generating && !hasDraftContent) {
    return (
      <div>
        {aiUnavailable && <AiNotConfiguredHint onClose={() => setAiUnavailable(false)} />}
        <div style={{ textAlign: "center", padding: "48px 0" }}>
          <Empty
            image={<ThunderboltOutlined style={{ fontSize: 56, color: "#1677ff" }} />}
            description={
              <>
                <Title level={4} style={{ marginBottom: 4 }}>{meta.emptyTitle}</Title>
                <Text type="secondary">{meta.emptyDesc}</Text>
              </>
            }
          >
            <Button
              type="primary"
              size="large"
              icon={<ThunderboltOutlined />}
              loading={generating === "full"}
              onClick={() => void startFullGenerate()}
            >
              {meta.generateLabel}
            </Button>
          </Empty>
        </div>
      </div>
    );
  }

  if (currentStatus === "completed" && doc && !generating) {
    return (
      <div>
        {aiUnavailable && <AiNotConfiguredHint onClose={() => setAiUnavailable(false)} />}
        {toolbar}
        <div style={{ color: "#999", marginBottom: 12 }}>
          生成时间：
          {doc.generatedAt
            ? new Date(doc.generatedAt).toLocaleString("zh-CN")
            : "-"}
        </div>
        <div
          style={{
            background: "#fff",
            padding: 24,
            border: "1px solid #f0f0f0",
            borderRadius: 8,
            maxHeight: "calc(100vh - 320px)",
            overflow: "auto",
            fontFamily: "SimSun, serif",
            fontSize: 15,
            lineHeight: 2,
          }}
        >
          <style>{REPORT_TABLE_STYLE}</style>
          <div
            className="risk-report-content"
            dangerouslySetInnerHTML={{ __html: renderReportMarkdown(doc.content || "") }}
          />
        </div>
      </div>
    );
  }

  // 草稿/生成中：侧栏 + 编辑器
  const visibleChapters = chapterDefs.length > 0 ? chapterDefs : fallbackChapters;
  return (
    <div>
      {aiUnavailable && <AiNotConfiguredHint onClose={() => setAiUnavailable(false)} />}
      {toolbar}
      {thinkingText && (
        <div style={{ marginBottom: 8, fontSize: 13, color: "#374151", lineHeight: 1.6 }}>
          {thinkingText}<span style={{ color: "#1a56db" }}>▌</span>
        </div>
      )}
      {interruptedGenerating && (
        <Alert
          type="warning"
          showIcon
          style={{ marginBottom: 12 }}
          message="上次生成未完成"
          description={`已保留 ${partialChapterCount}/${chapterDefs.length} 章。可对左侧空章节单独生成，或一键重新生成全部；若仍在其他页面生成中请稍候再试。`}
          action={
            <Button size="small" onClick={() => void startFullGenerate()}>
              重新生成全部
            </Button>
          }
        />
      )}
      {generating === "full" && (
        <div style={{ marginBottom: 12 }}>
          <Progress
            percent={batchProgress.total > 0 ? Math.round((batchProgress.current / batchProgress.total) * 100) : 0}
            format={() => `${batchProgress.current}/${batchProgress.total}`}
            status="active"
          />
          <div style={{ textAlign: "center", fontSize: 13, color: "#666", marginTop: 4 }}>
            {batchProgress.message}
          </div>
        </div>
      )}
      {failedChapters.length > 0 && !generating && (
        <Alert
          type="warning"
          showIcon
          style={{ marginBottom: 12 }}
          message={`${failedChapters.length} 个章节生成失败`}
          description={failedChapters.map((f) => f.title).join("、")}
          action={
            <Button
              size="small"
              onClick={() => {
                const first = failedChapters[0];
                setFailedChapters([]);
                if (first) {
                  message.info("正在重试第一个失败章节；其余章节可在左侧单独重新生成");
                  runChapterGeneration(first.key, "generate");
                }
              }}
            >
              重试失败章节
            </Button>
          }
        />
      )}
      <div style={{ display: "flex", gap: 16, height: "calc(100vh - 320px)", minHeight: 460 }}>
        {!collapsed && (
          <div style={{ width: 280, flexShrink: 0, border: "1px solid #f0f0f0", borderRadius: 8, overflow: "auto", background: "#fff" }}>
            <div style={{ padding: "10px 12px", fontWeight: 600, fontSize: 13, borderBottom: "1px solid #f0f0f0", background: "#fafafa", color: "#666", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span>报告章节</span>
              <Button type="text" size="small" onClick={() => setCollapsed(true)}>收起</Button>
            </div>
            {visibleChapters.map((c) => {
              const content = contentByKey[c.key] || "";
              const isGen = generatingKeys.has(c.key);
              const failed = failedChapters.some((f) => f.key === c.key);
              const isSelected = selectedKey === c.key;
              return (
                <div
                  key={c.key}
                  onClick={() => selectChapter(c.key)}
                  style={{
                    padding: "10px 12px",
                    cursor: generating && !isGen ? "default" : "pointer",
                    background: isSelected ? "#e6f4ff" : "transparent",
                    borderLeft: isSelected ? "3px solid #1677ff" : "3px solid transparent",
                    borderBottom: "1px solid #f0f0f0",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    {isGen ? (
                      <LoadingOutlined style={{ color: "#1677ff" }} />
                    ) : content ? (
                      <CheckCircleFilled style={{ color: "#52c41a" }} />
                    ) : failed ? (
                      <CloseCircleFilled style={{ color: "#ff4d4f" }} />
                    ) : (
                      <span style={{ width: 14, color: "#d9d9d9" }}>○</span>
                    )}
                    <Text
                      ellipsis={{ tooltip: c.title }}
                      style={{ fontWeight: isSelected ? 600 : 400, color: content || isGen ? "#333" : "#999" }}
                    >
                      {c.title}
                    </Text>
                  </div>
                  <div style={{ marginLeft: 22, fontSize: 12, color: "#999" }}>
                    {isGen ? "AI 生成中..." : content ? `${content.length} 字` : failed ? "生成失败，可重试" : "未生成"}
                  </div>
                </div>
              );
            })}
          </div>
        )}
        {collapsed && (
          <Button type="text" onClick={() => setCollapsed(false)} style={{ flexShrink: 0 }}>
            展开章节
          </Button>
        )}
        <div style={{ flex: 1, display: "flex", flexDirection: "column", background: "#fff", border: "1px solid #f0f0f0", borderRadius: 8, overflow: "hidden", minWidth: 0 }}>
          {currentChapter ? (
            <>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "10px 14px", borderBottom: "1px solid #f0f0f0" }}>
                <Space>
                  <Text strong>{currentChapter.title}</Text>
                  <Badge
                    count={currentChapter ? (contentByKey[currentChapter.key] || "").length : 0}
                    overflowCount={99999}
                    style={{ backgroundColor: "#999" }}
                  />
                </Space>
                <Space size="middle">
                  <ReportChapterActions
                    hasContent={!!(currentChapter && contentByKey[currentChapter.key])}
                    loading={generatingKeys.has(currentChapter.key)}
                    disabled={generating === "full"}
                    generate={() => setGenModalKey(currentChapter.key)}
                    regenerate={() => {
                      Modal.confirm({
                        title: `重新生成「${currentChapter.title}」？`,
                        content: "重新生成将覆盖当前章节内容，完成后可在对比预览中选择接受或拒绝。",
                        okText: "开始生成",
                        onOk: () => runChapterGeneration(currentChapter.key, "regenerate"),
                      });
                    }}
                    stop={stopGeneration}
                  />
                  <span style={{ fontSize: 12, color: saveStatus === "error" ? "#cf1322" : saveStatus === "saving" ? "#1677ff" : "#999" }}>
                    {saveStatus === "saving"
                      ? "保存中..."
                      : saveStatus === "error"
                        ? "保存失败"
                        : saveStatus === "idle"
                          ? "未保存"
                          : "已保存"}
                  </span>
                  {saveStatus === "error" && currentChapter && (
                    <Button
                      type="link"
                      size="small"
                      onClick={() => {
                        // 直接读取当前 state 中的最新内容重试，避免闭包陈旧值
                        setSaveState((prev) => ({ ...prev, [currentChapter.key]: "saving" }));
                        const md = contentByKey[currentChapter.key] || "";
                        void saveOne(currentChapter.key, md);
                      }}
                    >
                      重试保存
                    </Button>
                  )}
                </Space>
              </div>
              <div style={{ flex: 1, overflow: "auto", padding: 14 }}>
                <TiptapEditor
                  content={editorHtml}
                  onChange={(html) => {
                    if (!currentChapter) return;
                    const md = htmlToMarkdown(html);
                    setChapterContent(currentChapter.key, md);
                    // 被生成的章节由生成流程落库，避免编辑回调与 SSE 竞争
                    if (!generatingKeys.has(currentChapter.key)) scheduleSave(currentChapter.key, md);
                  }}
                  readOnly={generating === "full" || generatingKeys.has(currentChapter.key)}
                  placeholder={`编辑「${currentChapter.title}」内容...`}
                />
                {kind === "risk" && currentChapter?.key === "ch2_summary" && (doc?.fourColorImages?.length ?? 0) > 0 && (
                  <div style={{ marginTop: 16 }}>
                    <div style={{ fontWeight: 600, marginBottom: 8 }}>四色分布图</div>
                    {doc?.fourColorImages?.map((im) => (
                      <Card
                        key={im.floor_id}
                        size="small"
                        style={{ marginBottom: 12 }}
                        title={`${im.floor_name} 四色分布图`}
                      >
                        <img src={im.url} alt={im.floor_name} style={{ maxWidth: "100%" }} />
                      </Card>
                    ))}
                  </div>
                )}
              </div>
            </>
          ) : (
            <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", flexDirection: "column", gap: 16, color: "#999" }}>
              {generating ? (
                <>
                  <Spin size="large" />
                  <div>正在生成报告章节...</div>
                </>
              ) : (
                <>
                  <ThunderboltOutlined style={{ fontSize: 48, color: "#d9d9d9" }} />
                  <div>从左侧选择一个章节开始编辑，或一键生成全部</div>
                  <Button type="primary" icon={<ThunderboltOutlined />} onClick={() => void startFullGenerate()}>
                    {meta.generateLabel}
                  </Button>
                </>
              )}
            </div>
          )}
        </div>
      </div>

      {/* 创作风格 */}
      <Modal
        title="创作风格"
        open={styleOpen}
        onCancel={() => setStyleOpen(false)}
        width={560}
        onOk={() => void saveStyle()}
        okText="保存风格"
        confirmLoading={savingStyle}
      >
        <StylePanel value={styleValue} onChange={setStyleValue} />
      </Modal>

      {/* 审查 */}
      <ReviewDrawer
        open={reviewOpen}
        issues={reviewIssues}
        onClose={() => {
          setReviewOpen(false);
          setReviewIssues([]);
        }}
        onApply={(keys) => void applyReview(keys)}
        applying={applyingReview}
        chapterTitleMap={chapterTitleMap}
      />

      {/* 修订 diff（逐条确认） */}
      {diffIndex >= 0 && diffQueue[diffIndex] && (
        <DiffPreviewModal
          open={diffIndex >= 0}
          oldText={renderReportMarkdown(diffQueue[diffIndex].original)}
          newText={renderReportMarkdown(diffQueue[diffIndex].revised)}
          onAccept={() => closeDiff(true)}
          onReject={() => closeDiff(false)}
          onClose={() => closeDiff(false)}
        />
      )}

      {/* 单章生成自定义指令 */}
      <Modal
        title="生成本章"
        open={!!genModalKey}
        onCancel={() => setGenModalKey(null)}
        onOk={() => {
          if (!genModalKey) return;
          runChapterGeneration(genModalKey, "generate");
          setGenModalKey(null);
        }}
        okText="开始生成"
        width={560}
      >
        <Text type="secondary">
          AI 将按当前章节定义与创作风格生成内容，生成期间可随时停止。
        </Text>
      </Modal>
    </div>
  );
}

const REPORT_TABLE_STYLE = `
  .risk-report-content table {
    border-collapse: collapse;
    width: 100%;
    margin: 12px 0;
    font-size: 13px;
  }
  .risk-report-content table th,
  .risk-report-content table td {
    border: 1px solid #333;
    padding: 6px 10px;
    text-align: left;
    vertical-align: top;
  }
  .risk-report-content table th {
    background-color: #f0f0f0;
    font-weight: bold;
  }
`;
