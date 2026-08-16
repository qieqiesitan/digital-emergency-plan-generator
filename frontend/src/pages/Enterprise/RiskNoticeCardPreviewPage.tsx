import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import {
  Alert,
  App as AntApp,
  Button,
  Checkbox,
  List,
  Modal,
  Result,
  Space,
  Spin,
  Tag,
} from "antd";
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
import {
  MAX_SIGNS_PER_CATEGORY,
  MAX_TOTAL_SIGNS,
  SIGN_CATEGORY_ORDER,
  applySignSuggestion,
  buildNameLookup,
  buildReasonLookup,
  buildSignLookup,
  countSignsByCategory,
  signSrc,
  sortSignsByCategory,
} from "@/utils/riskNoticeCardSigns";

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

.rnc-edit-current {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}
.rnc-edit-chip {
  align-items: center;
  background: #fafafa;
  border: 1px solid #f0f0f0;
  border-radius: 4px;
  display: flex;
  gap: 6px;
  padding: 4px 8px;
}
.rnc-edit-chip img {
  height: 24px;
  width: 24px;
}
.rnc-edit-remove {
  color: #999;
  cursor: pointer;
  font-size: 14px;
  line-height: 1;
}
.rnc-edit-remove:hover {
  color: #ff4d4f;
}
.rnc-edit-category {
  color: #595959;
  font-size: 12px;
  font-weight: 600;
  margin: 10px 0 6px;
}
.rnc-edit-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.rnc-edit-item {
  align-items: center;
  border: 1px solid #f0f0f0;
  border-radius: 4px;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 8px 6px 6px;
  width: 92px;
}
.rnc-edit-item:hover {
  border-color: #91caff;
}
.rnc-edit-item-selected {
  background: #f0f7ff;
  border-color: #1677ff;
}
.rnc-edit-item img {
  height: 40px;
  width: 40px;
}
.rnc-edit-name {
  color: #333;
  font-size: 12px;
  line-height: 1.3;
  text-align: center;
}
`;

const COMPARE_BLOCKS = [
  { key: "hazard_description", label: "主要危险因素描述" },
  { key: "control_measures", label: "主要风险控制措施" },
  { key: "emergency_measures", label: "应急处置措施" },
] as const;

/** 类别中文标签（编辑 Modal 分组标题）。 */
const CATEGORY_LABELS: Record<SignCategory, string> = {
  warning: "警告类",
  prohibition: "禁止类",
  instruction: "指令类",
  notice: "提示类",
};

interface AiCompareResult {
  original: RightColumn;
  optimized: RightColumn;
}

/** 保存快照用的完整 content：右栏四块 + 标志 + 来源（后端 RightColumn 同构）。 */
interface SignReviewContent extends RightColumn {
  signs: SignItem[];
  signs_source: "rule" | "ai" | "manual";
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
  const catalogLookup = useMemo(
    () => (result ? buildSignLookup(result.catalog) : new Map<string, SignItem>()),
    [result],
  );
  const removeSet = useMemo(
    () => (suggestion ? new Set(suggestion.remove) : new Set<string>()),
    [suggestion],
  );
  const kept = sortSignsByCategory(
    currentSigns.filter((sign) => !removeSet.has(sign.svg_name)),
  );

  const reasonFor = (svgName: string, fallbackName?: string) =>
    reasonLookup.get(fallbackName ?? "") ?? reasonLookup.get(svgName) ?? "";
  // add/delete 行中文名优先取候选库（AI 返回 svg_name，catalog 映射真实中文名）
  const nameFor = (svgName: string) =>
    catalogLookup.get(svgName)?.name ?? nameLookup.get(svgName) ?? svgName;

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
                name={nameFor(svgName)}
                reason={reasonFor(svgName, nameFor(svgName))}
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
                name={nameFor(svgName)}
                reason={reasonFor(svgName, nameFor(svgName))}
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

/** 编辑 Modal 正文（随 open 挂载/卸载，每次打开用当前标志初始化状态）。 */
function SignEditBody({
  catalog,
  initialSigns,
  saving,
  onSave,
  onCancel,
}: {
  catalog: SignItem[];
  initialSigns: SignItem[];
  saving: boolean;
  onSave: (signs: SignItem[]) => void;
  onCancel: () => void;
}) {
  const { message } = AntApp.useApp();
  const [selected, setSelected] = useState<SignItem[]>(() =>
    sortSignsByCategory(initialSigns),
  );

  const selectedNames = useMemo(
    () => new Set(selected.map((sign) => sign.svg_name)),
    [selected],
  );
  const categoryCounts = useMemo(() => countSignsByCategory(selected), [selected]);
  const sortedCatalog = useMemo(() => sortSignsByCategory(catalog), [catalog]);

  const toggleSign = (sign: SignItem) => {
    if (selectedNames.has(sign.svg_name)) {
      setSelected((prev) => prev.filter((s) => s.svg_name !== sign.svg_name));
      return;
    }
    if ((categoryCounts.get(sign.category) ?? 0) >= MAX_SIGNS_PER_CATEGORY) {
      message.warning(`「${sign.name}」同类标志最多选择 ${MAX_SIGNS_PER_CATEGORY} 个`);
      return;
    }
    if (selected.length >= MAX_TOTAL_SIGNS) {
      message.warning(`标志总数最多选择 ${MAX_TOTAL_SIGNS} 个`);
      return;
    }
    setSelected((prev) => sortSignsByCategory([...prev, sign]));
  };

  return (
    <div>
      <div style={{ color: "#8c8c8c", fontSize: 12, marginBottom: 8 }}>
        当前已选（{selected.length}/{MAX_TOTAL_SIGNS}），每类不超过 {MAX_SIGNS_PER_CATEGORY}{" "}
        个
      </div>
      <div className="rnc-edit-current">
        {selected.length ? (
          selected.map((sign) => (
            <div className="rnc-edit-chip" key={sign.svg_name}>
              <img src={signSrc(sign.svg_name)} alt={sign.name} />
              <span>{sign.name}</span>
              <span
                className="rnc-edit-remove"
                title="移除"
                onClick={() => toggleSign(sign)}
              >
                ×
              </span>
            </div>
          ))
        ) : (
          <span style={{ color: "#bfbfbf" }}>暂无已选标志</span>
        )}
      </div>
      <div style={{ color: "#8c8c8c", fontSize: 12, marginBottom: 8 }}>
        候选库（{catalog.length}）
      </div>
      {sortedCatalog.length ? (
        SIGN_CATEGORY_ORDER.map((category) => {
          const items = sortedCatalog.filter((sign) => sign.category === category);
          if (!items.length) return null;
          const count = categoryCounts.get(category) ?? 0;
          return (
            <div key={category}>
              <div className="rnc-edit-category">
                {CATEGORY_LABELS[category]}（{count}/{MAX_SIGNS_PER_CATEGORY}）
              </div>
              <div className="rnc-edit-grid">
                {items.map((sign) => {
                  const checked = selectedNames.has(sign.svg_name);
                  return (
                    <div
                      className={`rnc-edit-item${checked ? " rnc-edit-item-selected" : ""}`}
                      key={sign.svg_name}
                      onClick={() => toggleSign(sign)}
                    >
                      <img src={signSrc(sign.svg_name)} alt={sign.name} />
                      <span className="rnc-edit-name">{sign.name}</span>
                      <Checkbox checked={checked} />
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })
      ) : (
        <div style={{ color: "#bfbfbf" }}>
          候选库未加载，请先运行「AI 审查标志」获取候选库后重试（当前仍可移除已选标志）。
        </div>
      )}
      <div style={{ marginTop: 16, textAlign: "right" }}>
        <Space>
          <Button onClick={onCancel} disabled={saving}>
            取消（不保存）
          </Button>
          <Button type="primary" loading={saving} onClick={() => onSave(selected)}>
            保存并更新卡片（版本 +1）
          </Button>
        </Space>
      </div>
    </div>
  );
}

/** 人工微调编辑 Modal：当前已选标志可移除 + 候选库网格勾选添加（每类 ≤2、总数 ≤8）。 */
function SignEditModal({
  open,
  catalog,
  initialSigns,
  saving,
  onSave,
  onCancel,
}: {
  open: boolean;
  catalog: SignItem[];
  initialSigns: SignItem[];
  saving: boolean;
  onSave: (signs: SignItem[]) => void;
  onCancel: () => void;
}) {
  return (
    <Modal title="编辑安全标志" open={open} width={680} onCancel={onCancel} footer={null}>
      {open && (
        <SignEditBody
          catalog={catalog}
          initialSigns={initialSigns}
          saving={saving}
          onSave={onSave}
          onCancel={onCancel}
        />
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
  /** AI 审查响应中的候选库（与 reviewResult 生命周期解耦，供人工微调复用）。 */
  const [signCatalog, setSignCatalog] = useState<SignItem[]>([]);
  const [aiLoading, setAiLoading] = useState(false);
  const [reviewing, setReviewing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [reviewSaving, setReviewSaving] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [editSaving, setEditSaving] = useState(false);
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
      const result = await aiReviewSigns(enterpriseId, objectId);
      setReviewResult(result);
      setSignCatalog(result.catalog);
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
        signs: applySignSuggestion(card.signs, reviewResult.suggestion, reviewResult.catalog),
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

  /** 人工微调保存：组装完整 content（右栏 + 调整后 signs + manual）→ 快照 → 刷新。 */
  const handleSaveManualSigns = async (signs: SignItem[]) => {
    if (!card || editSaving) return;
    setEditSaving(true);
    try {
      const content: SignReviewContent = {
        hazard_description: card.hazard_description,
        accident_types: card.accident_types,
        control_measures: card.control_measures,
        emergency_measures: card.emergency_measures,
        signs,
        signs_source: "manual",
      };
      const info = await saveSnapshot(enterpriseId, objectId, content);
      const refreshed = await refetch();
      if (refreshed.isError) {
        message.error("已保存快照，但刷新卡片数据失败，请稍后重试");
      } else {
        message.success(`已保存快照 V1.${info.version}`);
      }
      setEditOpen(false);
    } catch {
      message.error("保存快照失败，请重试");
    } finally {
      setEditSaving(false);
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

      <RiskNoticeCard card={card} onEditSigns={() => setEditOpen(true)} />

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

      <SignEditModal
        open={editOpen}
        catalog={signCatalog}
        initialSigns={card.signs}
        saving={editSaving}
        onSave={(signs) => void handleSaveManualSigns(signs)}
        onCancel={() => setEditOpen(false)}
      />
    </div>
  );
}
