import React from "react";

const FORMALITY_OPTIONS = [
  { value: "formal", label: "正式" },
  { value: "standard", label: "标准" },
  { value: "practical", label: "实用" },
];

const DETAIL_OPTIONS = [
  { value: "concise", label: "简短" },
  { value: "balanced", label: "适中" },
  { value: "comprehensive", label: "详尽" },
];

const TABLE_OPTIONS = [
  { value: "minimal", label: "少用" },
  { value: "moderate", label: "按需" },
  { value: "heavy", label: "多用" },
];

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
  onPreview: () => void;
  onSwitchToAdvanced: () => void;
}

const StylePanel: React.FC<StylePanelProps> = ({ value, onChange, onPreview, onSwitchToAdvanced }) => {
  const update = (key: keyof StylePreference, val: string) => {
    onChange({ ...value, [key]: val });
  };

  return (
    <div style={{ padding: "12px", border: "1px solid #e0e0e0", borderRadius: "8px", marginBottom: "16px" }}>
      <div style={{ fontWeight: 600, marginBottom: "10px", fontSize: "14px" }}>创作风格</div>

      <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "8px" }}>
        <span style={{ width: "72px", fontSize: "13px", color: "#666" }}>正式程度</span>
        <SegmentedControl options={FORMALITY_OPTIONS} value={value.formality} onChange={(v) => update("formality", v)} />
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "8px" }}>
        <span style={{ width: "72px", fontSize: "13px", color: "#666" }}>详略程度</span>
        <SegmentedControl options={DETAIL_OPTIONS} value={value.detail_level} onChange={(v) => update("detail_level", v)} />
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "8px" }}>
        <span style={{ width: "72px", fontSize: "13px", color: "#666" }}>表格使用</span>
        <SegmentedControl options={TABLE_OPTIONS} value={value.table_preference} onChange={(v) => update("table_preference", v)} />
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "10px" }}>
        <span style={{ width: "72px", fontSize: "13px", color: "#666" }}>流程图</span>
        <SegmentedControl
          options={[
            { value: "mermaid", label: "生成" },
            { value: "none", label: "不生成" },
          ]}
          value={value.diagram_preference}
          onChange={(v) => update("diagram_preference", v)}
        />
      </div>

      <div style={{ display: "flex", gap: "8px" }}>
        <button onClick={onPreview} style={{ fontSize: "12px", padding: "4px 10px", cursor: "pointer" }}>预览一段</button>
        <button onClick={() => onChange(DEFAULT_STYLE)} style={{ fontSize: "12px", padding: "4px 10px", cursor: "pointer" }}>重置默认</button>
        <button onClick={onSwitchToAdvanced} style={{ fontSize: "12px", padding: "4px 10px", cursor: "pointer", marginLeft: "auto" }}>高级模式 →</button>
      </div>
    </div>
  );
};

// Inline SegmentedControl component
const SegmentedControl: React.FC<{
  options: { value: string; label: string }[];
  value: string;
  onChange: (value: string) => void;
}> = ({ options, value, onChange }) => (
  <div style={{ display: "flex", border: "1px solid #d9d9d9", borderRadius: "4px", overflow: "hidden" }}>
    {options.map((opt) => (
      <button
        key={opt.value}
        onClick={() => onChange(opt.value)}
        style={{
          padding: "3px 10px",
          fontSize: "12px",
          border: "none",
          background: value === opt.value ? "#1890ff" : "transparent",
          color: value === opt.value ? "#fff" : "#333",
          cursor: "pointer",
          transition: "background 0.15s",
        }}
      >
        {opt.label}
      </button>
    ))}
  </div>
);

export { StylePanel };
