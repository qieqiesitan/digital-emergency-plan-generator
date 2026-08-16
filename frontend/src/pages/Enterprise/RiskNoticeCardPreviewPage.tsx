import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { Alert, App as AntApp, Button, List, Modal, Result, Space, Spin, Tag } from "antd";
import { useQuery } from "@tanstack/react-query";
import RiskNoticeCard, { EMPTY_TEXT } from "@/components/enterprise/RiskNoticeCard";
import { PageHeader } from "@/components/common/PageHeader";
import { getDownloadUrl } from "@/services/exportService";
import {
  aiOptimize,
  aiReviewSigns,
  exportCards,
  fetchCardDetail,
  saveSnapshot,
} from "@/services/riskNoticeCardService";
import type {
  AiSignReviewResponse,
  RightColumn,
  SignCategory,
  SignItem,
} from "@/types/riskNoticeCard";

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

.rnc-sr-item {
  align-items: center;
  display: flex;
  gap: 10px;
}
.rnc-sr-icon {
  flex: none;
  height: 32px;
  width: 32px;
}
.rnc-sr-info {
  flex: 1;
  min-width: 0;
}
.rnc-sr-name {
  font-size: 13px;
  font-weight: 600;
  line-height: 1.4;
}
.rnc-sr-reason {
  color: #595959;
  font-size: 12px;
  line-height: 1.5;
  margin-top: 2px;
}
.rnc-sr-del {
  color: #cf1322;
  text-decoration: line-through;
}
.rnc-sr-add {
  color: #389e0d;
}
.rnc-sr-keep {
  color: #8c8c8c;
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

/** 保存快照用的完整 content：右栏四块 + 标志 + 来源（后端 RightColumn 同构）。 */
interface SignReviewContent extends RightColumn {
  signs: SignItem[];
  signs_source: "rule" | "ai" | "manual";
}

/** 按 svg_name 前缀推断标志类别（svg_name 均以类别英文开头）。 */
function categoryOf(svgName: string): SignCategory {
  if (svgName.startsWith("warning")) return "warning";
  if (svgName.startsWith("prohibition")) return "prohibition";
  if (svgName.startsWith("instruction")) return "instruction";
  return "notice";
}

/** 预览图地址（svg_name 无扩展名，与卡片渲染一致）。 */
function signSrc(svgName: string): string {
  return `/signs/${svgName}.svg`;
}

/** 把 AI 建议应用到当前标志：remove 去掉、add 加入（按 svg_name 匹配），返回新标志列表。 */
function applySignSuggestion(
  current: SignItem[],
  suggestion: AiSignReviewResponse["suggestion"],
): SignItem[] {
  const remove = new Set(suggestion.remove);
  const kept = current.filter((sign) => !remove.has(sign.svg_name));
  const existing = new Set(kept.map((sign) => sign.svg_name));
  const added: SignItem[] = suggestion.add
    .filter((svg) => !existing.has(svg))
    .map((svg) => ({
      category: categoryOf(svg),
      name: svg,
      svg_name: svg,
    }));
  return [...kept, ...added];
}

/** 当前标志的中文名查找表（svg_name → name）。 */
function buildNameLookup(signs: SignItem[]): Map<string, string> {
  return new Map(signs.map((sign) => [sign.svg_name, sign.name]));
}

/** 建议理由查找表（中文名 → 理由）。 */
function buildReasonLookup(
  suggestion: AiSignReviewResponse["suggestion"],
): Map<string, string> {
  return new Map(suggestion.reasons.map((r) => [r.sign_name, r.reason]));
}

/** 标志行展示：图标 + 名称 + 可选理由。 */
function SignRow({
  svgName,
  name,
  reason,
  tone,
}: {
  svgName: string;
  name: string;
  reason?: string;
  tone: "del" | "add" | "keep";
}) {
  const toneClass = tone === "del" ? "rnc-sr-del" : tone === "add" ? "rnc-sr-add" : "rnc-sr-keep";
  return (
    <List.Item>
      <div className="rnc-sr-item">
        <img className="rnc-sr-icon" src={signSrc(svgName)} alt={name} />
        <div className="rnc-sr-info">
          <div className={`rnc-sr-name ${toneClass}`}>{name}</div>
          {reason && <div className="rnc-sr-reason">理由：{reason}</div>}
        </div>
      </div>
    </List.Item>
  );
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

/** AI 审查安全标志差异对比 Modal：建议删除（红删线）/建议增加（绿）/保留（灰）。 */
function SignReviewModal({
  result,
  currentSigns,
  saving,
  onAdopt,
  onDiscard,
}: {
  result: AiSignReviewResponse | null;
  currentSigns: SignItem[];
  saving: boolean;
  onAdopt: () => void;
  onDiscard: () => void;
}) {
  const suggestion = result?.suggestion;
  const reasonLookup = useMemo(
    () => (suggestion ? buildReasonLookup(suggestion) : new Map<string, string>()),
    [suggestion],
  );
  const nameLookup = useMemo(() => buildNameLookup(currentSigns), [currentSigns]);
  const removeSet = useMemo(
    () => (suggestion ? new Set(suggestion.remove) : new Set<string>()),
    [suggestion],
  );
  const kept = currentSigns.filter((sign) => !removeSet.has(sign.svg_name));

  const reasonFor = (svgName: string, fallbackName?: string) =>
    reasonLookup.get(fallbackName ?? "") ?? reasonLookup.get(svgName) ?? "";

  return (
    <Modal
      title="AI 审查安全标志"
      open={!!result}
      width={640}
      onCancel={onDiscard}
      footer={[
        <Button key="discard" onClick={onDiscard} disabled={saving}>
          放弃，保留原版
        </Button>,
        <Button key="adopt" type="primary" loading={saving} onClick={onAdopt}>
          采用建议并保存快照（版本 +1）
        </Button>,
      ]}
    >
      {result && suggestion && (
        <div>
          <List
            header={
              <span style={{ color: "#cf1322", fontWeight: 600 }}>
                建议删除（{suggestion.remove.length}）
              </span>
            }
            size="small"
            dataSource={suggestion.remove}
            locale={{ emptyText: "无" }}
            renderItem={(svgName) => (
              <SignRow
                key={svgName}
                svgName={svgName}
                name={nameLookup.get(svgName) ?? svgName}
                reason={reasonFor(svgName, nameLookup.get(svgName))}
                tone="del"
              />
            )}
          />
          <List
            header={
              <span style={{ color: "#389e0d", fontWeight: 600 }}>
                建议增加（{suggestion.add.length}）
              </span>
            }
            size="small"
            dataSource={suggestion.add}
            locale={{ emptyText: "无" }}
            renderItem={(svgName) => (
              <SignRow
                key={svgName}
                svgName={svgName}
                name={nameLookup.get(svgName) ?? svgName}
                reason={reasonFor(svgName, nameLookup.get(svgName))}
                tone="add"
              />
            )}
          />
          <List
            header={
              <span style={{ color: "#8c8c8c", fontWeight: 600 }}>保留（{kept.length}）</span>
            }
            size="small"
            dataSource={kept}
            locale={{ emptyText: "无" }}
            renderItem={(sign) => (
              <SignRow
                key={sign.svg_name}
                svgName={sign.svg_name}
                name={sign.name}
                reason={reasonFor(sign.svg_name, sign.name)}
                tone="keep"
              />
            )}
          />
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
  const [reviewResult, setReviewResult] = useState<AiSignReviewResponse | null>(null);
  const [aiLoading, setAiLoading] = useState(false);
  const [reviewing, setReviewing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [reviewSaving, setReviewSaving] = useState(false);
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

  /** AI 标志审查（无副作用）：成功后打开差异对比 Modal。 */
  const handleReviewSigns = useCallback(async () => {
    if (!enterpriseId || !objectId) return;
    setReviewing(true);
    try {
      setReviewResult(await aiReviewSigns(enterpriseId, objectId));
    } catch {
      message.error("AI 审查失败，已保留原版");
    } finally {
      setReviewing(false);
    }
  }, [enterpriseId, objectId, message]);

  /** ?ai=1 自动触发一次 AI 优化（从管理页行操作跳转），先触发后清参。 */
  useEffect(() => {
    if (autoTriggered.current) return;
    if (searchParams.get("ai") !== "1") return;
    autoTriggered.current = true;
    // 触发先于清参：若先清参，effect 重跑时 cleanup 可能抢先取消定时器导致永不触发。
    // 同步 setState 仍放到定时器内，规避 react-hooks set-state-in-effect 规则。
    const timer = window.setTimeout(() => {
      void runAiOptimize();
      setSearchParams({}, { replace: true });
    }, 0);
    return () => window.clearTimeout(timer);
  }, [searchParams, setSearchParams, runAiOptimize]);

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
      const refreshed = await refetch();
      if (refreshed.isError) {
        message.error("已保存快照，但刷新卡片数据失败，请稍后重试");
      } else {
        message.success(`已保存快照 V1.${info.version}`);
      }
      setCompare(null);
    } catch {
      message.error("保存快照失败，请重试");
    } finally {
      setSaving(false);
    }
  };

  /** 采用 AI 标志建议：应用到当前标志 → 组装完整 content → 保存快照 → 刷新。 */
  const handleAdoptSigns = async () => {
    if (!card || !reviewResult || reviewSaving) return;
    setReviewSaving(true);
    try {
      const content: SignReviewContent = {
        hazard_description: card.hazard_description,
        accident_types: card.accident_types,
        control_measures: card.control_measures,
        emergency_measures: card.emergency_measures,
        signs: applySignSuggestion(card.signs, reviewResult.suggestion),
        signs_source: "ai",
      };
      const info = await saveSnapshot(enterpriseId, objectId, content);
      const refreshed = await refetch();
      if (refreshed.isError) {
        message.error("已保存快照，但刷新卡片数据失败，请稍后重试");
      } else {
        message.success(`已保存快照 V1.${info.version}`);
      }
      setReviewResult(null);
    } catch {
      message.error("保存快照失败，请重试");
    } finally {
      setReviewSaving(false);
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
        <Button
          loading={reviewing}
          disabled={reviewing}
          onClick={() => void handleReviewSigns()}
        >
          AI 审查标志
        </Button>
      </Space>

      <RiskNoticeCard card={card} />

      <AiCompareModal
        result={compare}
        saving={saving}
        onAdopt={() => void adoptOptimized()}
        onDiscard={() => setCompare(null)}
      />

      <SignReviewModal
        result={reviewResult}
        currentSigns={card.signs}
        saving={reviewSaving}
        onAdopt={() => void handleAdoptSigns()}
        onDiscard={() => setReviewResult(null)}
      />
    </div>
  );
}
