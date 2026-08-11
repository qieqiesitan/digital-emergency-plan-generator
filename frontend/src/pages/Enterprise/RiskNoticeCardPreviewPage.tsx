import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { Alert, App as AntApp, Button, Modal, Result, Space, Spin, Tag } from "antd";
import { useQuery } from "@tanstack/react-query";
import RiskNoticeCard from "@/components/enterprise/RiskNoticeCard";
import { PageHeader } from "@/components/common/PageHeader";
import { getDownloadUrl } from "@/services/exportService";
import {
  aiOptimize,
  exportCards,
  fetchCardDetail,
  saveSnapshot,
} from "@/services/riskNoticeCardService";
import type { RightColumn } from "@/types/riskNoticeCard";

const EMPTY_TEXT = "暂无，请先完善风险评估数据";

/** AI 优化对比面板样式（.rnc-cmp-* 前缀）。 */
const COMPARE_CSS = `
.rnc-cmp-block {
  border: 1px solid #f0f0f0;
  margin-bottom: 12px;
}
.rnc-cmp-label {
  background: #fafafa;
  border-bottom: 1px solid #f0f0f0;
  font-size: 13px;
  font-weight: 600;
  padding: 6px 10px;
}
.rnc-cmp-cols {
  display: flex;
}
.rnc-cmp-col {
  flex: 1;
  font-size: 12.5px;
  line-height: 1.7;
  padding: 8px 10px;
  word-break: break-word;
}
.rnc-cmp-col + .rnc-cmp-col {
  border-left: 1px dashed #e8e8e8;
}
.rnc-diff {
  background: #fffbe6;
  border-left: 3px solid #faad14;
  border-radius: 2px;
  margin: 1px 0;
  padding: 1px 4px;
  white-space: pre-wrap;
}
.rnc-cmp-empty {
  color: #bfbfbf;
}
`;

const COMPARE_BLOCKS = [
  { key: "hazard_description", label: "主要危险因素描述" },
  { key: "control_measures", label: "主要风险控制措施" },
  { key: "emergency_measures", label: "应急处置措施" },
] as const;

interface AiCompareResult {
  original: RightColumn;
  optimized: RightColumn;
}

function toLines(value: string | string[]): string[] {
  if (Array.isArray(value)) return value;
  return value ? value.split("\n") : [];
}

/** 单块对比：左右逐行对齐，差异行黄色高亮，扩充/完善打标。 */
function CompareBlock({
  label,
  original,
  optimized,
}: {
  label: string;
  original: string | string[];
  optimized: string | string[];
}) {
  const originalLines = toLines(original);
  const optimizedLines = toLines(optimized);
  const changed = originalLines.join("\n") !== optimizedLines.join("\n");
  const expanded = optimizedLines.length > originalLines.length;
  const maxLen = Math.max(originalLines.length, optimizedLines.length);
  const rows: { index: number; original: string; optimized: string; diff: boolean }[] = [];
  for (let i = 0; i < maxLen; i++) {
    const o = originalLines[i] ?? "";
    const n = optimizedLines[i] ?? "";
    rows.push({ index: i, original: o, optimized: n, diff: o !== n });
  }

  return (
    <div className="rnc-cmp-block">
      <div className="rnc-cmp-label">
        {label}
        {changed && (
          <Tag color={expanded ? "blue" : "green"} style={{ marginLeft: 8 }}>
            {expanded ? "已扩充" : "已完善"}
          </Tag>
        )}
      </div>
      <div className="rnc-cmp-cols">
        <div className="rnc-cmp-col">
          {originalLines.length ? (
            rows.map((row) => (
              <div key={row.index} className={row.diff ? "rnc-diff" : undefined}>
                {row.original || "\u00A0"}
              </div>
            ))
          ) : (
            <span className="rnc-cmp-empty">{EMPTY_TEXT}</span>
          )}
        </div>
        <div className="rnc-cmp-col">
          {optimizedLines.length ? (
            rows.map((row) => (
              <div key={row.index} className={row.diff ? "rnc-diff" : undefined}>
                {row.optimized || "\u00A0"}
              </div>
            ))
          ) : (
            <span className="rnc-cmp-empty">{EMPTY_TEXT}</span>
          )}
        </div>
      </div>
    </div>
  );
}

function AiCompareModal({
  result,
  saving,
  onAdopt,
  onDiscard,
}: {
  result: AiCompareResult | null;
  saving: boolean;
  onAdopt: () => void;
  onDiscard: () => void;
}) {
  return (
    <Modal
      title="AI 优化对比"
      open={!!result}
      width={1000}
      onCancel={onDiscard}
      footer={[
        <Button key="discard" onClick={onDiscard} disabled={saving}>
          放弃，保留原版
        </Button>,
        <Button key="adopt" type="primary" loading={saving} onClick={onAdopt}>
          采用优化版并保存快照（版本 +1）
        </Button>,
      ]}
    >
      {result && (
        <div>
          <div style={{ color: "#8c8c8c", display: "flex", fontSize: 12, marginBottom: 8 }}>
            <div style={{ flex: 1 }}>原版（当前版本）</div>
            <div style={{ flex: 1 }}>优化版（AI 生成）</div>
          </div>
          {COMPARE_BLOCKS.map(({ key, label }) => (
            <CompareBlock
              key={key}
              label={label}
              original={result.original[key]}
              optimized={result.optimized[key]}
            />
          ))}
        </div>
      )}
    </Modal>
  );
}

/** 风险告知卡单卡预览 + AI 优化对比页。 */
export default function RiskNoticeCardPreviewPage() {
  const { id: enterpriseId = "", objectId = "" } = useParams<{
    id: string;
    objectId: string;
  }>();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const { message } = AntApp.useApp();
  const [compare, setCompare] = useState<AiCompareResult | null>(null);
  const [aiLoading, setAiLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [exporting, setExporting] = useState(false);
  const autoTriggered = useRef(false);

  const { data: card, isLoading, isError, refetch } = useQuery({
    queryKey: ["risk-notice-card", enterpriseId, objectId],
    queryFn: () => fetchCardDetail(enterpriseId, objectId),
    enabled: !!enterpriseId && !!objectId,
  });

  const runAiOptimize = useCallback(async () => {
    if (!enterpriseId || !objectId) return;
    setAiLoading(true);
    try {
      const result = await aiOptimize(enterpriseId, objectId);
      setCompare(result);
    } catch {
      message.error("AI 优化失败，已保留原版");
    } finally {
      setAiLoading(false);
    }
  }, [enterpriseId, objectId, message]);

  /** ?ai=1 自动触发一次 AI 优化（从管理页行操作跳转），触发后清除参数。 */
  useEffect(() => {
    if (!card || autoTriggered.current) return;
    if (searchParams.get("ai") !== "1") return;
    autoTriggered.current = true;
    setSearchParams({}, { replace: true });
    // 下一轮调度再触发，避免 effect 体内同步 setState（react-hooks 规则）
    const timer = window.setTimeout(() => {
      void runAiOptimize();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [card, searchParams, setSearchParams, runAiOptimize]);

  const copyPublicLink = async () => {
    if (!card) return;
    try {
      await navigator.clipboard.writeText(`${window.location.origin}${card.public_url}`);
      message.success("公开链接已复制");
    } catch {
      message.error("复制失败，请手动复制");
    }
  };

  const exportSingle = async () => {
    if (exporting) return;
    setExporting(true);
    try {
      const { file_key, warnings } = await exportCards(enterpriseId, [objectId]);
      window.open(getDownloadUrl(file_key), "_blank");
      if (warnings.length) {
        message.warning(`部分卡片未导出：${warnings.length} 张`);
      }
    } catch {
      message.error("导出失败，请稍后重试");
    } finally {
      setExporting(false);
    }
  };

  const adoptOptimized = async () => {
    if (!compare || saving) return;
    setSaving(true);
    try {
      const info = await saveSnapshot(enterpriseId, objectId, compare.optimized);
      message.success(`已保存快照 V1.${info.version}`);
      setCompare(null);
      void refetch();
    } catch {
      message.error("保存快照失败，请重试");
    } finally {
      setSaving(false);
    }
  };

  if (isLoading) {
    return <Spin size="large" style={{ display: "block", margin: "100px auto" }} />;
  }
  if (isError || !card) {
    return (
      <Result
        status="error"
        title="卡片加载失败"
        subTitle="请稍后重试"
        extra={
          <Button type="primary" onClick={() => void refetch()}>
            重新加载
          </Button>
        }
      />
    );
  }

  const versionText = card.snapshot
    ? `V1.${card.snapshot.version} · AI 优化`
    : "V1.0 · 规则生成";

  return (
    <div style={{ maxWidth: 920, margin: "0 auto" }}>
      <style>{COMPARE_CSS}</style>
      <PageHeader
        title={`${card.name}安全风险告知卡`}
        subtitle={`${card.enterprise_name} · 编制日期 ${card.generated_at.slice(0, 10)}`}
        onBack={() => navigate(`/enterprises/${enterpriseId}/risk-notice-cards`)}
        extra={<Tag color={card.snapshot ? "blue" : "default"}>{versionText}</Tag>}
      />

      {card.stale && (
        <Alert
          type="warning"
          showIcon
          message="风险数据已变更，建议重新生成"
          style={{ marginBottom: 16 }}
        />
      )}

      <Space style={{ marginBottom: 16 }} wrap>
        <Button onClick={() => void copyPublicLink()}>复制公开链接</Button>
        <Button loading={exporting} disabled={exporting} onClick={() => void exportSingle()}>
          导出单张 Word
        </Button>
        <Button
          type="primary"
          loading={aiLoading}
          disabled={aiLoading}
          onClick={() => void runAiOptimize()}
        >
          AI 优化
        </Button>
      </Space>

      <RiskNoticeCard card={card} />

      <AiCompareModal
        result={compare}
        saving={saving}
        onAdopt={() => void adoptOptimized()}
        onDiscard={() => setCompare(null)}
      />
    </div>
  );
}
