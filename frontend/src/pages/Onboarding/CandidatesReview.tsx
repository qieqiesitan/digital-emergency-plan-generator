import { Button, Empty } from "antd";
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
}

/** 候选核对：已采纳（绿）与新增候选（蓝）两区，支持增量生成 */
export default function CandidatesReview({
  accepted, candidates, renderItem, onAccept, onModify, onDelete,
  onGenerateMore, generating, sourceLabel, generateMoreLabel = "继续生成更多（不覆盖已采纳）",
}: Props) {
  return (
    <div>
      <div style={{ fontSize: 13, fontWeight: 600, color: "#52c41a", marginBottom: 6 }}>
        ✓ 已采纳（{accepted.length} 条，已保存，AI 不会改动）
      </div>
      {accepted.length === 0 ? (
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

      <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 6 }}>
        新增候选{sourceLabel ? `（${sourceLabel}）` : ""}（{candidates.length} 条）
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
