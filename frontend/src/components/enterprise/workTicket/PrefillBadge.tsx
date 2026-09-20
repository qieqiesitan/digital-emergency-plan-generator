import { Tag, Tooltip } from "antd";
import type { FieldSource } from "@/types/workTicket";
import { SOURCE_LABEL } from "./fieldSources";

/**
 * 票面字段的来源徽标。
 *
 * - `manual`（或来源缺失）不渲染任何东西——手填是默认状态，标出来只会干扰视线
 * - `ai` 用紫色，提示该值必须人工确认后才能提交（与后端门禁一致）
 */
export function PrefillBadge({
  source,
  detail,
}: {
  source?: FieldSource;
  detail?: string;
}) {
  if (!source || source === "manual") return null;
  const label = SOURCE_LABEL[source];
  return (
    <Tooltip title={detail || label}>
      <Tag color={source === "ai" ? "purple" : "blue"} style={{ marginInlineStart: 6 }}>
        {label}
      </Tag>
    </Tooltip>
  );
}

export default PrefillBadge;
