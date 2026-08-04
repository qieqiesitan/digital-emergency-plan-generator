// @ts-nocheck
import { useState, useEffect, useRef, useCallback } from "react";
import { Button, Spin, Alert, Space, Typography, Empty, message, Progress } from "antd";
import {
  ThunderboltOutlined,
  DownloadOutlined,
  EyeOutlined,
  StopOutlined,
  ExclamationCircleOutlined,
  CheckCircleFilled,
  LoadingOutlined,
  ClockCircleFilled,
} from "@ant-design/icons";
import {
  getResourceInvestigation,
  downloadResourceInvestigation,
  generateResourceInvestigationStream,
  mergeResourceInvestigation,
} from "@/services/resourceInvestigationService";
import type { ResourceInvestigationReport } from "@/types/resourceInvestigation";
import type { SSEEvent } from "@/types/riskAssessment";
import { useNavigate } from "react-router-dom";

const { Title, Paragraph } = Typography;

interface Props {
  enterpriseId: string;
}

// 与后端 CHAPTER_DEFINITIONS 保持一致的章节定义
const FALLBACK_CHAPTERS = [
  { key: "ch1_purpose",      title: "一、调查目的与依据" },
  { key: "ch2_basic_info",   title: "二、企业基本情况与风险概况" },
  { key: "ch3_internal",     title: "三、内部应急资源调查" },
  { key: "ch4_external",     title: "四、外部救援资源调查" },
  { key: "ch5_gap_analysis", title: "五、应急资源需求与能力评估" },
  { key: "ch6_conclusion",   title: "六、调查结论与建议" },
];

type ChapterStatus = "pending" | "generating" | "completed";

/** Animated loading dots */
function LoadingDots() {
  const [dots, setDots] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setDots((d) => (d + 1) % 4), 400);
    return () => clearInterval(t);
  }, []);
  return <span>{".".repeat(dots)}</span>;
}

export default function ResourceInvestigationTab({ enterpriseId }: Props) {
  const navigate = useNavigate();
  const [report, setReport] = useState<ResourceInvestigationReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [editing, setEditing] = useState(false);
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const [batchProgress, setBatchProgress] = useState({ current: 0, total: 0, message: "" });
  const [chapterStatuses, setChapterStatuses] = useState<Record<string, ChapterStatus>>({});
  const [CHAPTERS, setChapters] = useState(FALLBACK_CHAPTERS);
  useEffect(() => {
    import("@/services/resourceInvestigationService").then(({ getResourceInvestigationChapters }) => {
      getResourceInvestigationChapters(enterpriseId).then(setChapters).catch(() => {});
    });
  }, [enterpriseId]);
  // Trigger re-render when chunk content updates for the selected chapter
  const [renderTick, setRenderTick] = useState(0);

  const genContentRef = useRef<Record<string, string>>({});
  const editedContentRef = useRef<Record<string, string>>({});
  const selectedKeyRef = useRef<string | null>(null);
  const controllerRef = useRef<AbortController | null>(null);

  // Keep selectedKeyRef in sync
  useEffect(() => {
    selectedKeyRef.current = selectedKey;
  }, [selectedKey]);

  const editingContent = selectedKey ? (genContentRef.current[selectedKey] || "") : "";

  const loadReport = async () => {
    try {
      setLoading(true);
      const r = await getResourceInvestigation(enterpriseId);
      setReport(r);
    } catch {
      setReport(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadReport();
  }, [enterpriseId]);

  // Elapsed timer
  useEffect(() => {
    if (!generating) return;
    const t = setInterval(() => setElapsed((prev) => prev + 1), 1000);
    return () => clearInterval(t);
  }, [generating]);

  const handleGenerate = () => {
    setGenerating(true);
    setError(null);
    setElapsed(0);
    setRenderTick(0);
    setBatchProgress({ current: 0, total: CHAPTERS.length, message: "准备开始..." });
    // Reset all statuses to pending
    const initial: Record<string, ChapterStatus> = {};
    CHAPTERS.forEach((c) => { initial[c.key] = "pending"; });
    setChapterStatuses(initial);
    genContentRef.current = {};
    selectedKeyRef.current = null;

    const controller = generateResourceInvestigationStream(
      enterpriseId,
      undefined,
      (event: SSEEvent) => {
        switch (event.type) {
          case "progress": {
            if (event.section_key) {
              setChapterStatuses((prev) => ({
                ...prev,
                [event.section_key!]: "generating",
              }));
              genContentRef.current[event.section_key] = genContentRef.current[event.section_key] || "";
              // Auto-select the generating chapter on first encounter
              if (!genContentRef.current[event.section_key]) {
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
          }

          case "chunk": {
            if (event.content && event.section_key) {
              genContentRef.current[event.section_key] =
                (genContentRef.current[event.section_key] || "") + event.content;
              // Trigger re-render if the viewed section is the one being updated
              if (selectedKeyRef.current === event.section_key) {
                setRenderTick((t) => t + 1);
              }
            }
            break;
          }

          case "section_done": {
            if (event.section_key) {
              setChapterStatuses((prev) => ({
                ...prev,
                [event.section_key!]: "completed",
              }));
            }
            break;
          }

          case "batch_done": {
            setGenerating(false);
            setEditing(true);
            // Copy generated content to editable ref
            editedContentRef.current = { ...genContentRef.current };
            setBatchProgress({ current: 0, total: 0, message: "" });
            message.success(`报告生成完成，共 ${CHAPTERS.length} 个章节`);
            break;
          }

          case "error": {
            setError(event.message || "生成失败");
            setGenerating(false);
            break;
          }
        }
      },
      (err: string) => {
        setError(err);
        setGenerating(false);
      },
      () => {}
    );
    controllerRef.current = controller;
  };

  const handleStop = () => {
    controllerRef.current?.abort();
    setGenerating(false);
  };

  const handleMerge = async () => {
    const chapters = CHAPTERS.map((ch) => ({
      key: ch.key,
      title: ch.title,
      content: editedContentRef.current[ch.key] || genContentRef.current[ch.key] || "",
    }));
    try {
      setEditing(false);
      setLoading(true);
      await mergeResourceInvestigation(enterpriseId, chapters);
      message.success("\u62a5\u544a\u5408\u5e76\u5b8c\u6210");
      await loadReport();
    } catch (err: any) {
      message.error(err.message || "\u5408\u5e76\u5931\u8d25");
      setEditing(true);
      setLoading(false);
    }
  };

  const handleExport = async () => {
    try {
      await downloadResourceInvestigation(enterpriseId);
    } catch (err: any) {
      message.error(err.message || "export failed");
    }
  };

  // ---- Chapter sidebar item ----
  const renderChapterItem = (ch: typeof CHAPTERS[0]) => {
    const status = chapterStatuses[ch.key] || "pending";
    const isSelected = selectedKey === ch.key;

    let statusIcon: React.ReactNode;
    if (status === "completed") {
      statusIcon = <CheckCircleFilled style={{ color: "#52c41a", fontSize: 14 }} />;
    } else if (status === "generating") {
      statusIcon = <LoadingOutlined style={{ color: "#1677ff", fontSize: 14 }} />;
    } else {
      statusIcon = <ClockCircleFilled style={{ color: "#d9d9d9", fontSize: 14 }} />;
    }

    return (
      <div
        key={ch.key}
        onClick={() => {
          if (status !== "pending") {
            setSelectedKey(ch.key);
          }
        }}
        style={{
          display: "flex",
          alignItems: "flex-start",
          gap: 10,
          padding: "10px 12px",
          cursor: status !== "pending" ? "pointer" : "default",
          background: isSelected ? "#e6f4ff" : "transparent",
          borderLeft: isSelected ? "3px solid #1677ff" : "3px solid transparent",
          borderBottom: "1px solid #f0f0f0",
          transition: "background 0.2s",
        }}
      >
        <div style={{ marginTop: 1, flexShrink: 0 }}>{statusIcon}</div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{
            fontSize: 13,
            fontWeight: isSelected ? 600 : 400,
            color: status === "pending" ? "#bbb" : "#333",
          }}>
            {ch.title}
          </div>
          {status === "generating" && (
            <div style={{ fontSize: 11, color: "#1677ff", marginTop: 2 }}>
              正在生成... <LoadingDots />
            </div>
          )}
          {status === "completed" && genContentRef.current[ch.key] && (
            <div style={{ fontSize: 11, color: "#52c41a", marginTop: 2 }}>
              {(genContentRef.current[ch.key] || "").length} 字
            </div>
          )}
        </div>
      </div>
    );
  };

  if (loading) return <Spin size="large" />;

  // ---- Empty state ----
  if (!report && !generating && !editing) {
    return (
      <div style={{ textAlign: "center", padding: "60px 0" }}>
        <Empty
          image={<ExclamationCircleOutlined style={{ fontSize: 64, color: "#faad14" }} />}
          description={
            <>
              <Title level={4}>尚未生成应急资源调查报告</Title>
              <Paragraph type="secondary">
                根据法规要求，编制应急预案前需先完成应急资源调查。
                <br />
                系统将基于已录入的应急资源数据自动生成。
              </Paragraph>
            </>
          }
        >
          <Button
            type="primary"
            size="large"
            icon={<ThunderboltOutlined />}
            onClick={handleGenerate}
          >
            AI 生成应急资源调查报告
          </Button>
        </Empty>
      </div>
    );
  }

  // ---- Generating state ----
  if (generating) {
    const completedCount = Object.values(chapterStatuses).filter((s) => s === "completed").length;

    return (
      <div>
        {/* Progress header */}
        <div style={{ marginBottom: 16 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 16, marginBottom: 8 }}>
            <Progress
              percent={batchProgress.total > 0
                ? Math.round((completedCount / batchProgress.total) * 100)
                : 0}
              format={() => `${completedCount}/${batchProgress.total}`}
              status="active"
              strokeColor={{ from: "#1677ff", to: "#52c41a" }}
              style={{ flex: 1 }}
            />
            <Button danger icon={<StopOutlined />} onClick={handleStop}>
              取消生成
            </Button>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: 13 }}>
            <span style={{ color: "#1677ff", fontWeight: 500 }}>
              {batchProgress.message || "正在连接 AI 服务..."}
            </span>
            <span style={{ color: "#999" }}>
              耗时 {elapsed}s
            </span>
          </div>
          {elapsed > 30 && completedCount === 0 && (
            <Alert
              type="warning"
              message="AI 响应时间较长，请耐心等待或检查 AI 配置是否正常"
              style={{ marginTop: 8 }}
              showIcon
            />
          )}
        </div>

        {error && <Alert type="error" title={error} style={{ marginBottom: 12 }} closable />}

        {/* Main: sidebar + content */}
        <div style={{ display: "flex", gap: 16, height: "60vh" }}>
          {/* Chapter sidebar */}
          <div style={{
            width: 260,
            flexShrink: 0,
            border: "1px solid #f0f0f0",
            borderRadius: 8,
            overflow: "auto",
            background: "#fff",
          }}>
            <div style={{
              padding: "10px 12px",
              fontWeight: 600,
              fontSize: 13,
              borderBottom: "1px solid #f0f0f0",
              background: "#fafafa",
              color: "#666",
            }}>
              报告章节
            </div>
            {CHAPTERS.map((ch) => renderChapterItem(ch))}
          </div>

          {/* Content area */}
          <div style={{
            flex: 1,
            background: "#fff",
            padding: 24,
            border: "1px solid #f0f0f0",
            borderRadius: 8,
            overflow: "auto",
            fontFamily: "SimSun, serif",
            fontSize: 15,
            lineHeight: 2,
            position: "relative",
          }}>


            {selectedKey && editingContent ? (
              <div style={{ whiteSpace: "pre-wrap" }}>{editingContent}</div>
            ) : selectedKey ? (
              <div style={{ textAlign: "center", padding: "40px 0", color: "#999" }}>
                <Spin size="default" style={{ marginBottom: 12 }} />
                <div>AI 正在生成此章节...</div>
              </div>
            ) : (
              <div style={{ textAlign: "center", padding: "60px 0", color: "#999" }}>
                <Spin size="default" style={{ marginBottom: 12 }} />
                <div>AI 正在逐章生成应急资源调查报告</div>
                <div style={{ fontSize: 12, marginTop: 8, color: "#bbb" }}>
                  请从左侧选择章节查看实时生成内容
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    );
  }

  // ---- Editing state (after generation, before merge) ----
  if (editing) {
    return (
      <div>
        <div style={{ marginBottom: 16, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span style={{ fontSize: 16, fontWeight: 600 }}>
            {batchProgress.message || "\u7f16\u8f91\u5404\u7ae0\u8282\uff0c\u786e\u8ba4\u65e0\u8bef\u540e\u70b9\u51fb\u5408\u5e76"}
          </span>
          <Space>
            <Button onClick={() => {
              // Reset to empty state
              setEditing(false);
              setReport(null);
              genContentRef.current = {};
              editedContentRef.current = {};
              setSelectedKey(null);
              setChapterStatuses({});
            }}>
              {"\u653e\u5f03\u7f16\u8f91"}
            </Button>
            <Button type="primary" icon={<ThunderboltOutlined />} onClick={handleMerge}>
              {"\u5408\u5e76\u751f\u6210\u5b8c\u6574\u62a5\u544a"}
            </Button>
          </Space>
        </div>

        <div style={{ display: "flex", gap: 16, height: "60vh" }}>
          <div style={{
            width: 260, flexShrink: 0, border: "1px solid #f0f0f0",
            borderRadius: 8, overflow: "auto", background: "#fff",
          }}>
            <div style={{
              padding: "10px 12px", fontWeight: 600, fontSize: 13,
              borderBottom: "1px solid #f0f0f0", background: "#fafafa", color: "#666",
            }}>
              {"\u62a5\u544a\u7ae0\u8282"}
            </div>
            {CHAPTERS.map((ch) => (
              <div
                key={ch.key}
                onClick={() => setSelectedKey(ch.key)}
                style={{
                  display: "flex", alignItems: "center", gap: 8,
                  padding: "10px 12px", cursor: "pointer",
                  background: selectedKey === ch.key ? "#e6f4ff" : "transparent",
                  borderLeft: selectedKey === ch.key ? "3px solid #1677ff" : "3px solid transparent",
                  borderBottom: "1px solid #f0f0f0",
                }}
              >
                <CheckCircleFilled style={{ color: "#52c41a", fontSize: 14 }} />
                <span style={{ fontSize: 13, fontWeight: selectedKey === ch.key ? 600 : 400 }}>
                  {ch.title}
                </span>
              </div>
            ))}
          </div>

          <div style={{
            flex: 1, background: "#fff", padding: 16, border: "1px solid #f0f0f0",
            borderRadius: 8, overflow: "auto", display: "flex", flexDirection: "column",
          }}>
            {selectedKey ? (
              <>
                <div style={{ fontWeight: 600, marginBottom: 8, color: "#333" }}>
                  {CHAPTERS.find((c) => c.key === selectedKey)?.title}
                </div>
                <textarea
                  value={editedContentRef.current[selectedKey] || genContentRef.current[selectedKey] || ""}
                  onChange={(e) => {
                    editedContentRef.current = {
                      ...editedContentRef.current,
                      [selectedKey!]: e.target.value,
                    };
                    setRenderTick((t) => t + 1);
                  }}
                  style={{
                    flex: 1, width: "100%", border: "1px solid #d9d9d9",
                    borderRadius: 6, padding: 12, fontSize: 14, lineHeight: 1.8,
                    fontFamily: "SimSun, serif", resize: "none", outline: "none",
                  }}
                  placeholder={"\u7f16\u8f91\u6b64\u7ae0\u8282\u5185\u5bb9..."}
                />
              </>
            ) : (
              <div style={{ textAlign: "center", padding: "60px 0", color: "#999" }}>
                {"\u8bf7\u4ece\u5de6\u4fa7\u9009\u62e9\u7ae0\u8282\u8fdb\u884c\u7f16\u8f91"}
              </div>
            )}
          </div>
        </div>
      </div>
    );
  }

  // ---- Completed state ----
  return (
    <div>
      <Space style={{ marginBottom: 16 }}>
        <Button
          type="primary"
          icon={<ThunderboltOutlined />}
          onClick={() => {
            if (window.confirm("重新生成将覆盖当前报告，确定继续？")) {
              handleGenerate();
            }
          }}
        >
          重新生成
        </Button>
        <Button icon={<DownloadOutlined />} onClick={handleExport}>
          导出 Word
        </Button>
        <Button
          icon={<EyeOutlined />}
          onClick={() => navigate(`/enterprises/${enterpriseId}/resource-investigation/preview`)}
        >
          预览
        </Button>
      </Space>

      <div style={{ color: "#999", marginBottom: 12 }}>
        生成时间：{report.generated_at ? new Date(report.generated_at).toLocaleString("zh-CN") : "-"}
      </div>

      <div
        style={{
          background: "#fff",
          padding: 24,
          border: "1px solid #f0f0f0",
          borderRadius: 8,
          maxHeight: "65vh",
          overflow: "auto",
          fontFamily: "SimSun, serif",
          fontSize: 15,
          lineHeight: 2,
          whiteSpace: "pre-wrap",
        }}
      >

        <div style={{ whiteSpace: "pre-wrap" }}>{report.content}</div>
      </div>
    </div>
  );
}
