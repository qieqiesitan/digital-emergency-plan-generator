import React from "react";
import { Button, Segmented, Space, Typography } from "antd";
import { ThunderboltOutlined, BulbOutlined, SettingOutlined } from "@ant-design/icons";

const { Text, Title } = Typography;

const FORMALITY_OPTIONS = ["formal", "standard", "practical"] as const;
const DETAIL_OPTIONS = ["concise", "balanced", "comprehensive"] as const;
const TABLE_OPTIONS = ["minimal", "moderate", "heavy"] as const;

const FORMALITY_LABELS: Record<string, string> = { formal: "正式", standard: "标准", practical: "实用" };
const DETAIL_LABELS: Record<string, string> = { concise: "简短", balanced: "适中", comprehensive: "详尽" };
const TABLE_LABELS: Record<string, string> = { minimal: "少用", moderate: "按需", heavy: "多用" };

export interface StylePreference {
  formality: "formal" | "standard" | "practical";
  detail_level: "concise" | "balanced" | "comprehensive";
  table_preference: "minimal" | "moderate" | "heavy";
  diagram_preference: "none" | "mermaid";
  mode: "panel" | "advanced";
}

export const DEFAULT_STYLE: StylePreference = {
  formality: "standard",
  detail_level: "balanced",
  table_preference: "moderate",
  diagram_preference: "mermaid",
  mode: "panel",
};

interface StylePanelProps {
  value: StylePreference;
  onChange: (style: StylePreference) => void;
  onPreview?: () => void;
  onSwitchToAdvanced?: () => void;
  showAdvanced?: boolean;
}

const StylePanel: React.FC<StylePanelProps> = ({
  value, onChange, onPreview, onSwitchToAdvanced, showAdvanced = true,
}) => {
  const update = (key: keyof StylePreference, val: string) => {
    onChange({ ...value, [key]: val });
  };

  return (
    <div style={{ padding: "12px 0" }}>
      <Title level={5} style={{ marginBottom: 12 }}>创作风格</Title>

      <Space direction="vertical" style={{ width: "100%" }} size="small">
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <Text style={{ minWidth: 72 }}>正式程度</Text>
          <Segmented
            size="small"
            options={FORMALITY_OPTIONS.map(v => ({ value: v, label: FORMALITY_LABELS[v] }))}
            value={value.formality}
            onChange={(v) => update("formality", v as string)}
          />
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <Text style={{ minWidth: 72 }}>详略程度</Text>
          <Segmented
            size="small"
            options={DETAIL_OPTIONS.map(v => ({ value: v, label: DETAIL_LABELS[v] }))}
            value={value.detail_level}
            onChange={(v) => update("detail_level", v as string)}
          />
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <Text style={{ minWidth: 72 }}>表格使用</Text>
          <Segmented
            size="small"
            options={TABLE_OPTIONS.map(v => ({ value: v, label: TABLE_LABELS[v] }))}
            value={value.table_preference}
            onChange={(v) => update("table_preference", v as string)}
          />
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <Text style={{ minWidth: 72 }}>流程图</Text>
          <Segmented
            size="small"
            options={[
              { value: "mermaid", label: "生成" },
              { value: "none", label: "不生成" },
            ]}
            value={value.diagram_preference}
            onChange={(v) => update("diagram_preference", v as string)}
          />
        </div>
      </Space>

      <div style={{ marginTop: 12, display: "flex", gap: 8 }}>
        {onPreview && (
          <Button size="small" icon={<BulbOutlined />} onClick={onPreview}>
            预览效果
          </Button>
        )}
        <Button size="small" onClick={() => onChange(DEFAULT_STYLE)}>
          重置默认
        </Button>
        {showAdvanced && onSwitchToAdvanced && (
          <Button size="small" type="link" icon={<SettingOutlined />} onClick={onSwitchToAdvanced}>
            高级模式
          </Button>
        )}
      </div>
    </div>
  );
};

export { StylePanel };
