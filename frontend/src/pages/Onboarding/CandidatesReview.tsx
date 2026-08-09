import { useState } from "react";
import { Button, Empty, Spin } from "antd";
import type React from "react";
import type { CandidateItem } from "@/types/onboarding";

interface Props {
  accepted: CandidateItem[];
  candidates: CandidateItem[];
  renderItem: (item: CandidateItem) => React.ReactNode;
  onAccept: (item: CandidateItem) => void;
  onModify: (item: CandidateItem) => void;
  onDelete: (item: CandidateItem) => void;
  onGenerateMore: () => void;
  generating?: boolean;
  sourceLabel?: string;
  generateMoreLabel?: string;
  /** 全部采纳：遍历 candidates 批量采纳（返回 Promise，按钮自动 loading/防重复） */
  onAcceptAll?: () => Promise<void> | void;
  /** 全部取消采纳：删除已保存数据并移回候选区（返回 Promise，按钮自动 loading/防重复） */
  onUnacceptAll?: () => Promise<void> | void;
  /** 已采纳区数据回显加载中 */
  acceptedLoading?: boolean;
}

/** 候选核对：已采纳（绿）与新增候选（蓝）两区，支持增量生成 */
export default function CandidatesReview({
  accepted, candidates, renderItem, onAccept, onModify, onDelete,
  onGenerateMore, generating, sourceLabel, generateMoreLabel = "继续生成更多（不覆盖已采纳）",
  onAcceptAll, onUnacceptAll, acceptedLoading,
}: Props) {
  const [acceptAllBusy, setAcceptAllBusy] = useState(false);
  const [unacceptAllBusy, setUnacceptAllBusy] = useState(false);

  const handleAcceptAll = async () => {
    if (!onAcceptAll || acceptAllBusy) return;
    setAcceptAllBusy(true);
    try {
      await onAcceptAll();
    } finally {
      setAcceptAllBusy(false);
    }
  };

  const handleUnacceptAll = async () => {
    if (!onUnacceptAll || unacceptAllBusy) return;
    setUnacceptAllBusy(true);
    try {
      await onUnacceptAll();
    } finally {
      setUnacceptAllBusy(false);
    }
  };

  return (
    <div>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 6,
        }}
      >
        <div style={{ fontSize: 13, fontWeight: 600, color: "#52c41a" }}>
          ✓ 已采纳（{accepted.length} 条，已保存，AI 不会改动）
        </div>
        {onUnacceptAll && accepted.length > 0 && (
          <Button size="small" loading={unacceptAllBusy} onClick={handleUnacceptAll}>
            全部取消采纳
          </Button>
        )}
      </div>
      {acceptedLoading ? (
        <div style={{ padding: "14px 0", color: "#999", fontSize: 12 }}>
          <Spin size="small" style={{ marginRight: 8 }} />
          加载已保存数据…
        </div>
      ) : accepted.length === 0 ? (
        <Empty description="暂无已采纳数据" image={Empty.PRESENTED_IMAGE_SIMPLE} style={{ margin: "8px 0" }} />
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6, marginBottom: 10 }}>
          {accepted.map(item => (
            <div key={item._key} style={{ border: "1px solid #d9f7be", background: "#f6ffed", borderRadius: 8, padding: 8 }}>
              {renderItem(item)}
            </div>
          ))}
        </div>
      )}

      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 6,
        }}
      >
        <div style={{ fontSize: 13, fontWeight: 600 }}>
          新增候选{sourceLabel ? `（${sourceLabel}）` : ""}（{candidates.length} 条）
        </div>
        {onAcceptAll && candidates.length > 0 && (
          <Button
            size="small"
            type="primary"
            ghost
            loading={acceptAllBusy}
            onClick={handleAcceptAll}
          >
            全部采纳
          </Button>
        )}
      </div>
      {candidates.length === 0 ? (
        <Empty description="暂无候选，可输入概况生成或导入文件" image={Empty.PRESENTED_IMAGE_SIMPLE} style={{ margin: "8px 0" }} />
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6, marginBottom: 10 }}>
          {candidates.map(item => (
            <div key={item._key} style={{ border: "1px solid #1677ff", background: "#f0f7ff", borderRadius: 8, padding: 8 }}>
              {renderItem(item)}
              <div style={{ marginTop: 6, display: "flex", gap: 10, justifyContent: "flex-end" }}>
                <Button type="link" size="small" onClick={() => onModify(item)}>修改</Button>
                <Button type="link" size="small" style={{ color: "#52c41a" }} onClick={() => onAccept(item)}>采纳 ✓</Button>
                <Button type="link" size="small" onClick={() => onDelete(item)}>删除</Button>
              </div>
            </div>
          ))}
        </div>
      )}

      <Button block loading={generating} onClick={onGenerateMore}>
        {generating ? "生成中…" : generateMoreLabel}
      </Button>
    </div>
  );
}
