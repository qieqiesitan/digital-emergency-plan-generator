import { useMemo, useState } from "react";
import { Alert, Button, Collapse, Input, Modal, Select, Space, Tag, Typography } from "antd";
import type { MeasureMeta, MeasureSuggestion, WorkTicketMeasureDef } from "@/types/workTicket";
import {
  partitionMeasures,
  REASON_OPTIONS,
  withConfirmed,
  withNotApplicable,
  withReverted,
} from "./measureMeta";

const { Text } = Typography;

export interface MeasureChecklistProps {
  measures: WorkTicketMeasureDef[];
  suggestions: MeasureSuggestion[];
  meta: Record<string, MeasureMeta>;
  onChange: (next: Record<string, MeasureMeta>) => void;
  /** 同包其他作业票提示（作业包场景），仅展示 */
  packageHint?: string | null;
}

/**
 * 措施三态列表。
 *
 * 刻意**不提供**无条件"全部确认"：那会鼓励"没看就勾"。这里只允许
 * "确认引擎建议涉及的 M 条"（本来就要做），其余必须逐条处理；
 * 标记"本票不涉及"必须选理由 + 填说明，且可撤销。
 */
export function MeasureChecklist({
  measures,
  suggestions,
  meta,
  onChange,
  packageHint,
}: MeasureChecklistProps) {
  const { main, folded, statedCount, total, suggestedApplicableCount } = useMemo(
    () => partitionMeasures(measures, suggestions, meta),
    [measures, suggestions, meta],
  );
  const [pendingOrder, setPendingOrder] = useState<number | null>(null);
  const [reasonCode, setReasonCode] = useState<string>(REASON_OPTIONS[0].value);
  const [reasonText, setReasonText] = useState("");

  const reasonFor = (order: number) => meta[String(order)]?.reason_text;

  const confirmAllSuggested = () => {
    let next = meta;
    for (const item of suggestions) {
      if (item.suggest === "applicable" && !meta[String(item.sort_order)]) {
        next = withConfirmed(next, item.sort_order);
      }
    }
    onChange(next);
  };

  return (
    <Space orientation="vertical" size={12} style={{ width: "100%" }}>
      <Space wrap>
        <Text strong>
          已表态 {statedCount} / {total} 条
        </Text>
        {suggestedApplicableCount > 0 && (
          <Button size="small" onClick={confirmAllSuggested}>
            确认全部建议涉及的（{suggestedApplicableCount} 条）
          </Button>
        )}
      </Space>

      {packageHint && <Alert type="info" showIcon title={packageHint} />}

      {main.map((measure) => {
        const state = meta[String(measure.sort_order)]?.state ?? "pending";
        return (
          <div key={measure.sort_order} style={{ display: "flex", gap: 8 }}>
            <div style={{ flex: 1 }}>
              <Text>{measure.measure_text}</Text>{" "}
              <Tag color="blue">{measure.article_anchor}</Tag>
              {state === "confirmed" && <Tag color="green">已确认涉及</Tag>}
              {state === "not_applicable" && (
                <Tag color="default">本票不涉及：{reasonFor(measure.sort_order)}</Tag>
              )}
              {suggestions.find((s) => s.sort_order === measure.sort_order)?.reason && (
                <div>
                  <Text type="secondary">
                    {suggestions.find((s) => s.sort_order === measure.sort_order)?.reason}
                  </Text>
                </div>
              )}
            </div>
            <Space>
              {state === "pending" ? (
                <>
                  <Button
                    size="small"
                    type="primary"
                    onClick={() => onChange(withConfirmed(meta, measure.sort_order))}
                  >
                    确认涉及
                  </Button>
                  <Button size="small" onClick={() => setPendingOrder(measure.sort_order)}>
                    本票不涉及
                  </Button>
                </>
              ) : (
                <Button size="small" onClick={() => onChange(withReverted(meta, measure.sort_order))}>
                  撤销
                </Button>
              )}
            </Space>
          </div>
        );
      })}

      {folded.length > 0 && (
        <Collapse
          defaultActiveKey={["folded"]}
          items={[
            {
              key: "folded",
              label: `建议不涉及（${folded.length} 条）—— 按现场条件判定，需你确认`,
              children: folded.map((measure) => (
                <div key={measure.sort_order} style={{ display: "flex", gap: 8 }}>
                  <div style={{ flex: 1 }}>
                    <Text>{measure.measure_text}</Text>{" "}
                    <Tag color="blue">{measure.article_anchor}</Tag>
                    <div>
                      <Text type="secondary">
                        {suggestions.find((s) => s.sort_order === measure.sort_order)?.reason}
                      </Text>
                    </div>
                  </div>
                  <Space>
                    <Button
                      size="small"
                      onClick={() => onChange(withConfirmed(meta, measure.sort_order))}
                    >
                      确认涉及
                    </Button>
                    <Button size="small" onClick={() => setPendingOrder(measure.sort_order)}>
                      标记不涉及
                    </Button>
                  </Space>
                </div>
              )),
            },
          ]}
        />
      )}

      <Modal
        open={pendingOrder !== null}
        title="标记为「本票不涉及」"
        okText="确认"
        cancelText="取消"
        okButtonProps={{ disabled: !reasonText.trim() }}
        onCancel={() => {
          setPendingOrder(null);
          setReasonText("");
        }}
        onOk={() => {
          if (pendingOrder === null) return;
          onChange(withNotApplicable(meta, pendingOrder, reasonCode, reasonText.trim()));
          setPendingOrder(null);
          setReasonText("");
        }}
      >
        <Space orientation="vertical" size={8} style={{ width: "100%" }}>
          <Text type="secondary">
            不涉及也要留痕：理由会写进票面记录，事后可追溯、可撤销。
          </Text>
          <Select
            value={reasonCode}
            onChange={setReasonCode}
            options={REASON_OPTIONS}
            style={{ width: "100%" }}
          />
          <Input.TextArea
            rows={3}
            value={reasonText}
            onChange={(e) => setReasonText(e.target.value)}
            placeholder="补充说明（必填），例如：作业点周边无窨井、地沟"
          />
        </Space>
      </Modal>
    </Space>
  );
}

export default MeasureChecklist;
