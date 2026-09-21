import { useState } from "react";
import { App as AntApp, Select, Space, Typography } from "antd";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { linkRiskObject, listLinkableRiskObjects } from "@/services/majorHazardService";
import type { LinkableRiskObject } from "@/types/majorHazard";

interface Props {
  enterpriseId: string;
  unitId: string;
  riskObjectId?: string | null;
  /** 关联成功后的回调：带上被选中的风险点（解除关联时传 null），供调用方带出字段。 */
  onLinked?: (object: LinkableRiskObject | null) => void;
}

/**
 * 单元 ↔ 风险点关联选择器。
 *
 * 关联本身由后端做同企业校验；前端只负责选择与反馈。
 * 解除关联传 null（而不是删字段），与后端「传 null 表示解除」的契约一致。
 */
export default function RiskObjectPicker({
  enterpriseId,
  unitId,
  riskObjectId,
  onLinked,
}: Props) {
  const { message } = AntApp.useApp();
  const queryClient = useQueryClient();
  const [saving, setSaving] = useState(false);

  const { data: objects = [], isLoading } = useQuery({
    queryKey: ["linkable-risk-objects", enterpriseId],
    queryFn: () => listLinkableRiskObjects(enterpriseId),
    enabled: !!enterpriseId,
  });

  const handleChange = async (value?: string) => {
    setSaving(true);
    try {
      await linkRiskObject(unitId, value ?? null);
      message.success(value ? "已关联风险点" : "已解除关联");
      queryClient.invalidateQueries({ queryKey: ["major-hazard-units", enterpriseId] });
      // 选择器只管关联，不碰表单——带出的字段由调用方决定怎么用。
      onLinked?.(value ? (objects.find((o) => o.id === value) ?? null) : null);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Space orientation="vertical" style={{ width: "100%" }} size="small">
      <Select
        showSearch
        allowClear
        optionFilterProp="label"
        placeholder="选择该单元对应的风险点"
        style={{ width: "100%", maxWidth: 420 }}
        loading={isLoading}
        disabled={saving}
        value={riskObjectId ?? undefined}
        onChange={handleChange}
        notFoundContent="本企业暂无标记为风险点的对象"
        options={objects.map((o) => ({ value: o.id, label: o.name }))}
      />
      <Typography.Text type="secondary" style={{ fontSize: 12 }}>
        风险点来自「风险分级管控」中标记为风险点的对象；选中后会把对方的所在位置、责任部门、
        责任人、联系电话填入下方空白的表单项，改完记得点保存。关联后，预案生成会引用该单元的辨识结论。
      </Typography.Text>
    </Space>
  );
}
