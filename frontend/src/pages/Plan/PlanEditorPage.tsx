// @ts-nocheck
import { useState, useEffect, useCallback, useRef, useMemo } from "react";
import { useParams, useNavigate, useSearchParams } from "react-router-dom";
import { Spin, Input, Button, Space, Badge, message, Progress, Alert } from "antd";
import Modal from "antd/es/modal";
import { ExportOutlined, HistoryOutlined, ThunderboltOutlined, LoadingOutlined, SaveOutlined, SettingOutlined, FileSyncOutlined } from "@ant-design/icons";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getPlan, updatePlan, createVersion, regenerateMissingDiagrams } from "@/services/planService";
import { listSections, updateSection, autofillSection } from "@/services/planService";
import { generateBatchStream } from "@/services/generationService";
import { validateExport } from "@/services/exportService";
import { PageHeader } from "@/components/common/PageHeader";
import { PlanStatusTag } from "@/components/plan/PlanStatusTag";
import SectionTree from "@/components/plan/SectionTree";
import RichTextEditor from "@/components/plan/RichTextEditor";
import AIGenerateButton from "@/components/plan/AIGenerateButton";
import { StylePanel, DEFAULT_STYLE } from "@/components/plan/StylePanel";
import { AdvancedStylePanel } from "@/components/plan/AdvancedStylePanel";
import type { StylePreference } from "@/components/plan/StylePanel";
import type { PlanSection, SectionTemplate } from "@/types/plan";
import type { SSEEvent } from "@/types/plan";

function findTemplate(key: string, templates: SectionTemplate[]): SectionTemplate | null {
  for (const t of templates) {
    if (t.key === key) return t;
    if (t.subsections.length > 0) {
      const f = findTemplate(key, t.subsections);
      if (f) return f;
    }
  }
  return null;
}

export default function PlanEditorPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [searchParams] = useSearchParams();
  const autoGenerate = searchParams.get("auto_generate"); // "1" 全量（旧）| "sample" 样章

  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [editingContent, setEditingContent] = useState("");
  const [saveStatus, setSaveStatus] = useState<string>("saved");
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [batchProgress, setBatchProgress] = useState({ current: 0, total: 0, message: "" });
  const [generatingSections, setGeneratingSections] = useState<Set<string>>(new Set());
  const [failedSections, setFailedSections] = useState<Array<{ section_key: string; title: string }>>([]);
  const [stylePreference, setStylePreference] = useState<StylePreference>(DEFAULT_STYLE);
  const [advancedOverrides, setAdvancedOverrides] = useState<Record<string, unknown> | null>(null);
  const [styleMode, setStyleMode] = useState<"panel" | "advanced">("panel");
  const [styleModalOpen, setStyleModalOpen] = useState(false);
  const [sampleMode, setSampleMode] = useState(autoGenerate === "sample");
  const [sampleDone, setSampleDone] = useState(false);

  const { data: plan, isLoading: planLoading } = useQuery({
    queryKey: ["plan", id],
    queryFn: () => getPlan(id!),
    enabled: !!id,
  });

  const { data: sections } = useQuery({
    queryKey: ["planSections", id],
    queryFn: () => listSections(id!),
    enabled: !!id,
  });

  const { data: validation } = useQuery({
    queryKey: ["exportValidate", id],
    queryFn: () => validateExport(id!),
    enabled: !!id && !isGenerating,
  });

  const missingDiagrams = useMemo(() => {
    const items: string[] = [];
    (sections || []).forEach((s) => {
      Object.entries(s.diagram_svgs || {}).forEach(([k, meta]) => {
        if (meta?.placeholder) items.push(`${s.title}：${k}`);
      });
    });
    return items;
  }, [sections]);

  const regenerateDiagramsMut = useMutation({
    mutationFn: () => regenerateMissingDiagrams(id!),
    onSuccess: (r) => {
      message.success(`已重新生成 ${r.regenerated} 张附图`);
      queryClient.invalidateQueries({ queryKey: ["planSections", id] });
    },
    onError: () => message.error("重新生成附图失败"),
  });

  const saveMutation = useMutation({
    mutationFn: ({ key, content }: { key: string; content: string }) =>
      updateSection(id!, key, { content }),
    onSuccess: () => {
      setSaveStatus("saved");
      queryClient.invalidateQueries({ queryKey: ["planSections", id] });
      queryClient.invalidateQueries({ queryKey: ["plan", id] });
    },
    onError: () => { setSaveStatus("error"); message.error("保存失败"); },
  });
  const saveVersionMut = useMutation({
    mutationFn: () => createVersion(id!, "手动保存版本"),
    onSuccess: () => { message.success("版本已保存"); queryClient.invalidateQueries({ queryKey: ["versions", id] }); },
    onError: () => message.error("保存版本失败"),
  });
  const autofillMut = useMutation({
    mutationFn: (key: string) => autofillSection(id!, key),
    onSuccess: () => {
      message.success("自动填充完成");
      queryClient.invalidateQueries({ queryKey: ["planSections", id] });
      queryClient.invalidateQueries({ queryKey: ["plan", id] });
    },
    onError: (e: unknown) => message.error((e as Error)?.message || "自动填充失败"),
  });


  useEffect(() => {
    if (selectedKey && sections) {
      // During generation, prefer live-streamed content from genContentRef
      if (isGenerating && genContentRef.current[selectedKey] !== undefined) {
        setEditingContent(genContentRef.current[selectedKey]);
      } else {
        const section = sections.find((s: PlanSection) => s.section_key === selectedKey);
        if (section) setEditingContent(section.content || "");
      }
    }
  }, [selectedKey, sections, isGenerating]);

  // Auto-save with 3s debounce
  useEffect(() => {
    if (!selectedKey || isGenerating) return;
    const current = sections?.find((s: PlanSection) => s.section_key === selectedKey);
    if (!current || editingContent === current.content) return;
    setSaveStatus("unsaved");
    const timer = setTimeout(() => {
      setSaveStatus("saving");
      saveMutation.mutate({ key: selectedKey, content: editingContent });
    }, 3000);
    return () => clearTimeout(timer);
  }, [editingContent]);

  // If plan is in generating state on mount, show progress bar (no auto-reset)
  useEffect(() => {
    if (plan?.status === "generating" && !isGenerating) {
      setIsGenerating(true);
    } else if (plan && plan.status !== "generating" && isGenerating) {
      // 后端状态已恢复（生成完成/失败/取消），前端同步复位
      setIsGenerating(false);
      setGeneratingSections(new Set());
      setBatchProgress({ current: 0, total: 0, message: "" });
    }
  }, [plan?.status]);

  // Auto-trigger batch generation only on explicit ?auto_generate=1 (one-shot, session-guarded)
  useEffect(() => {
    if ((autoGenerate !== "1" && autoGenerate !== "sample") || !sections || sections.length === 0) return;
    const storageKey = `plan_auto_gen_${id}`;
    if (sessionStorage.getItem(storageKey) === "1") return;
    sessionStorage.setItem(storageKey, "1");
    // Clear the URL param so it does not re-trigger on page revisit
    navigate(`/plans/${id}/edit`, { replace: true });
    if (plan?.status === "generating") {
      // Already marked generating — do not double-trigger
      return;
    }
    if (autoGenerate === "sample") {
      // 样章模式：只生成第一章，完成后进入样章确认状态
      startRealtimeGeneration([sections[0].section_key], () => setSampleDone(true));
    } else {
      startRealtimeGeneration();
    }
  }, [autoGenerate, sections, plan?.status]);

  const genContentRef = useRef<Record<string, string>>({});
  const selectedKeyRef = useRef<string | null>(null);
  // Keep selectedKeyRef in sync with selectedKey state
  useEffect(() => {
    selectedKeyRef.current = selectedKey;
  }, [selectedKey]);




  const startRealtimeGeneration = useCallback((keys?: string[], onBatchDone?: () => void) => {
    if (!id || !sections || sections.length === 0) return;
    // Guard against accidental direct binding (e.g. onClick passes MouseEvent as keys)
    if (keys && !Array.isArray(keys)) {
      keys = undefined;
    }

    setIsGenerating(true);
    setBatchProgress({ current: 0, total: keys ? keys.length : sections.length, message: "准备开始..." });
    genContentRef.current = {};
    selectedKeyRef.current = null;
    setGeneratingSections(new Set());

    const allKeys = sections.map((s: PlanSection) => s.section_key);
    let completedCount = 0;

    const controller = generateBatchStream(
      id,
      keys ?? allKeys,
      (event: SSEEvent) => {
        switch (event.type) {
          case "progress":
            if (event.section_key) {
              genContentRef.current[event.section_key] = genContentRef.current[event.section_key] || "";
              setGeneratingSections(prev => new Set(prev).add(event.section_key!));
              // Auto-select the section being generated (first time only per section)
              if (genContentRef.current[event.section_key] === "") {
                setSelectedKey(event.section_key);
                selectedKeyRef.current = event.section_key;
              }
            }
            setBatchProgress({
              current: event.current || 0,
              total: event.total || 0,
              message: event.message || "",
            });
            break;

          case "chunk":
            if (event.content && event.section_key) {
              // Accumulate content in ref
              genContentRef.current[event.section_key] = (genContentRef.current[event.section_key] || "") + event.content;
              // Update editor if this section is currently viewed (using ref for StrictMode safety)
              if (selectedKeyRef.current === event.section_key) {
                setEditingContent(genContentRef.current[event.section_key]);
              }
            }
            break;

          case "section_done":
            if (event.section_key) {
              completedCount++;
              setGeneratingSections(prev => { const next = new Set(prev); next.delete(event.section_key!); return next; });
              // Refresh sidebar to show updated section status
              queryClient.invalidateQueries({ queryKey: ["planSections", id] });
            }
            break;

          case "batch_done":
            setIsGenerating(false);
            setGeneratingSections(new Set());
            setBatchProgress({ current: 0, total: 0, message: "" });
            if (event.failed_sections && event.failed_sections.length > 0) {
              setFailedSections(event.failed_sections);
              message.warning(`${event.failed_sections.length} 个章节生成失败`);
            } else {
              setFailedSections([]);
              message.success(`全部生成完成，共 ${completedCount} 个章节`);
              onBatchDone?.(); // 样章：仅无失败时进入确认态
            }
            queryClient.invalidateQueries({ queryKey: ["planSections", id] });
            queryClient.invalidateQueries({ queryKey: ["plan", id] });
            break;

          case "error":
            setIsGenerating(false);
            setGeneratingSections(new Set());
            setFailedSections([]);
            message.error(event.message || "生成出错");
            break;
        }
      },
      (error: string) => {
        setIsGenerating(false);
        setGeneratingSections(new Set());
        setBatchProgress({ current: 0, total: 0, message: "" });
        setFailedSections([]);
        message.error(error);
      },
      () => {
        // Stream completed (final fallback)
      }
    );

    // Store controller for potential cancel
    (window as any).__genController = controller;
  }, [id, sections, queryClient, saveMutation]);



  const handleAIContentChunk = useCallback((fullText: string) => {
    setEditingContent(fullText);
  }, []);

  const handleAIGenerateComplete = useCallback(
    (_fullText: string) => {
      setIsGenerating(false);
      // Backend already saved HTML via _md_to_html; reload from server
      queryClient.invalidateQueries({ queryKey: ["planSections", id] });
      queryClient.invalidateQueries({ queryKey: ["plan", id] });
    },
    [selectedKey, saveMutation]
  );

  const currentSection = sections?.find((s: PlanSection) => s.section_key === selectedKey);

  const templateSections: SectionTemplate[] = (sections || []).map((s) => ({
    key: s.section_key,
    title: s.title,
    level: s.level,
    sort_order: s.sort_order,
    ai_generatable: s.ai_generatable,
    user_editable: true,
    required: s.level <= 1,
    auto_fill: s.auto_fill,
    auto_fill_source: s.auto_fill_source,
    gb_requirement: "",
    prompt_template: null,
    data_dependencies: s.data_dependencies,
    subsections: [],
  }));

  if (planLoading) return <Spin size="large" />;
  if (!plan) return <div>预案不存在</div>;

  return (
    <div style={{ height: "calc(100vh - 140px)", display: "flex", flexDirection: "column" }}>
      <PageHeader
        onBack={() => navigate("/plans")}
        title={
          <Space>
            <Input
              defaultValue={plan.title}
              onBlur={(e) => updatePlan(id!, { title: e.target.value })}
              bordered={false}
              style={{ fontWeight: 600, fontSize: 16, width: 300 }}
            />
            <PlanStatusTag status={plan.status} />
          </Space>
        }
        extra={
          <Space>
<Button onClick={() => setStyleModalOpen(true)} icon={<SettingOutlined />}>创作风格</Button>
                        <Button
                icon={isGenerating ? <LoadingOutlined /> : <ThunderboltOutlined />}
                type="primary"
                ghost
                onClick={() => startRealtimeGeneration()}
                loading={isGenerating}
                disabled={isGenerating}
              >
                {isGenerating ? "后台生成中..." : "一键生成全部"}
              </Button>
            <Button icon={<HistoryOutlined />} onClick={() => navigate(`/plans/${id}/versions`)}>
              版本历史
            </Button>
            <Button icon={<SaveOutlined />} onClick={() => saveVersionMut.mutate()} loading={saveVersionMut.isPending}>
              保存版本
            </Button>
            <Button icon={<ExportOutlined />} type="primary" onClick={() => navigate(`/plans/${id}/preview`)}>
              导出
            </Button>
          </Space>
        }
      />

      {sampleDone && sampleMode && (
        <div style={{ border: "1px solid #1677ff", borderRadius: 8, padding: 12, marginBottom: 12, background: "#f0f7ff" }}>
          <div style={{ fontWeight: 600, marginBottom: 4 }}>样章已生成（第一章）——先看风格和内容</div>
          <div style={{ fontSize: 13, color: "#555", marginBottom: 8 }}>满意后生成全部章节；不满意可换风格重新生成样章</div>
          <Space>
            <Button type="primary" onClick={() => { setSampleMode(false); startRealtimeGeneration(); }}>满意，生成全部章节</Button>
            <Button
              onClick={() => {
                setSampleDone(false);
                startRealtimeGeneration([sections![0].section_key]);
              }}
            >
              换风格重新生成样章
            </Button>
          </Space>
        </div>
      )}

      {missingDiagrams.length > 0 && (
        <Alert
          type="warning"
          showIcon
          message={`该企业缺部分数据，${missingDiagrams.length} 张图未生成`}
          description={missingDiagrams.join("、")}
          action={
            <Space>
              <Button size="small" onClick={() => navigate("/enterprises")}>
                去补数据
              </Button>
              <Button size="small" type="primary" onClick={() => regenerateDiagramsMut.mutate()}>
                重新生成缺失附图
              </Button>
            </Space>
          }
        />
      )}

      {validation && !validation.valid && (
        <Alert
          type="warning"
          showIcon
          style={{ marginBottom: 12 }}
          message="⚠ 部分章节可能未覆盖完整要点"
          description={validation.issues.slice(0, 3).map((i) => `「${i.section_title}」${i.issue}`).join("；")}
          action={<Button size="small" onClick={() => message.info("可在导出预览页查看全部校验结果")}>查看要点清单</Button>}
        />
      )}

      {isGenerating && batchProgress.total > 0 &&  (
        <div style={{ padding: "8px 0" }}>
          <Progress
            percent={Math.round((batchProgress.current / batchProgress.total) * 100)}
            format={() => `${batchProgress.current}/${batchProgress.total}`}
            status="active"
          />
          <div style={{ textAlign: "center", fontSize: 13, color: "#666", marginTop: 4 }}>
            {batchProgress.message}
          </div>
        </div>
      )}

      {failedSections.length > 0 && !isGenerating && (
        <Alert
          type="warning"
          showIcon
          message={`${failedSections.length} 个章节生成失败`}
          description={failedSections.map((f) => f.title).join("、")}
          action={
            <Button
              size="small"
              onClick={() => {
                startRealtimeGeneration(failedSections.map((f) => f.section_key));
                setFailedSections([]);
              }}
            >
              重试失败章节
            </Button>
          }
        />
      )}

      <div style={{ flex: 1, display: "flex", gap: 16, overflow: "hidden" }}>
        {!sidebarCollapsed && (
          <div style={{ width: 260, flexShrink: 0, overflow: "auto", border: "1px solid #f0f0f0", borderRadius: 8, padding: 8 }}>
            <Button type="text" size="small" onClick={() => setSidebarCollapsed(true)} style={{ marginBottom: 8 }}>
              收起侧栏
            </Button>
            <SectionTree
              sections={sections || []}
              templateSections={templateSections}
              selectedKey={selectedKey}
              onSelect={setSelectedKey}
              generatingKeys={generatingSections}
            />
          </div>
        )}
        {sidebarCollapsed && (
          <Button type="text" onClick={() => setSidebarCollapsed(false)} style={{ flexShrink: 0 }}>
            展开侧栏
          </Button>
        )}

        <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
          {selectedKey && currentSection ? (
            <>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
                <span style={{ fontWeight: 500 }}>{currentSection.title}</span>
                <Space>
                  <Badge count={editingContent.length} overflowCount={99999} style={{ backgroundColor: "#999" }} />
                  {currentSection.auto_fill && (
                    <Button
                      icon={<FileSyncOutlined />}
                      loading={autofillMut.isPending}
                      onClick={() => autofillMut.mutate(currentSection.section_key)}
                    >
                      自动填充
                    </Button>
                  )}
                  {currentSection.ai_generatable && (
                    <AIGenerateButton
                    planId={id!}
                    sectionKey={selectedKey}
                    sectionTitle={currentSection.title}
                    onContentChunk={handleAIContentChunk}
                    onGenerateComplete={handleAIGenerateComplete}
                    oldContent={currentSection.content || ""}
                    onReject={(oldText?: string) => {
                      if (!id || !selectedKey) return;
                      const old = oldText ?? (currentSection.content || "");
                      saveMutation.mutate({ key: selectedKey, content: old });
                    }}
                    />
                  )}
                </Space>
              </div>
              <RichTextEditor
                planId={id!}
                sectionKey={selectedKey}
                sectionTitle={currentSection.title}
                aiGenerated={currentSection.ai_generated}
                content={editingContent}
                onChange={setEditingContent}
                readOnly={isGenerating}
                diagramSvgs={currentSection?.diagram_svgs}
              />
              <div style={{ marginTop: 4, fontSize: 12, textAlign: "right" }}>
                {saveStatus === "saving" ? "保存中..." : saveStatus === "saved" ? "已保存" : saveStatus === "error" ? "保存失败" : "未保存"}
              </div>
            </>
          ) : (
            <div style={{ flex: 1, display: "flex", justifyContent: "center", alignItems: "center", color: "#999", flexDirection: "column", gap: 12 }}>
              {isGenerating ? (
                <div style={{ textAlign: "center" }}>
                  <Spin size="large" />
                  <div style={{ marginTop: 12, color: "#666" }}>正在生成预案内容...</div>
                  <div style={{ marginTop: 4, fontSize: 12, color: "#999" }}>
                    您可以切换左侧章节查看实时生成的内容
                  </div>
                </div>
              ) : (
                <>
                  <span>从左侧选择一个章节开始编辑</span>
                  <Button type="primary" icon={<ThunderboltOutlined />} onClick={() => startRealtimeGeneration()} >
                    一键生成全部章节
                  </Button>
                </>
              )}
            </div>
          )}
        </div>
      </div>
      <Modal title="创作风格" open={styleModalOpen} onCancel={() => setStyleModalOpen(false)} footer={null} width={520} destroyOnHidden>
        {styleMode === "panel" ? (
          <StylePanel value={stylePreference}
            onChange={(sp) => { setStylePreference(sp); updatePlan(id!, { style_preference: sp } as any).catch(() => {}); }}
            onPreview={() => { const s = sections && sections[0]; if (s && id) { generateBatchStream(s.section_key, id!, undefined, (e: any) => {}, (err: string) => message.error(err)); setStyleModalOpen(false); } }}
            onSwitchToAdvanced={() => setStyleMode("advanced")}
            showAdvanced />
        ) : (
          <AdvancedStylePanel value={advancedOverrides}
            sections={(sections || []).map(s => ({ key: s.section_key, title: s.title }))}
            defaultSystemPrompt="你是一位持有国家注册安全工程师资格的应急预案编制专家..."
            onChange={(ao) => { setAdvancedOverrides(ao); updatePlan(id!, { style_preference: { ...stylePreference, mode: "advanced" }, advanced_prompt_overrides: ao } as any).catch(() => {}); }}
            onExit={() => setStyleMode("panel")} />
        )}
      </Modal>
    </div>
  );
}
