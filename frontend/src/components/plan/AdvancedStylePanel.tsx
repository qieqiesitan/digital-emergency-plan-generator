import React, { useState } from "react";

export interface AdvancedPromptOverrides {
  system_prompt_override: string;
  section_overrides: Record<string, string>;
}

interface AdvancedStylePanelProps {
  value: AdvancedPromptOverrides | null;
  sections: Array<{ key: string; title: string }>;
  defaultSystemPrompt: string;
  onChange: (overrides: AdvancedPromptOverrides) => void;
  onExit: () => void;
}

const AdvancedStylePanel: React.FC<AdvancedStylePanelProps> = ({
  value, sections, defaultSystemPrompt, onChange, onExit,
}) => {
  const [systemPrompt, setSystemPrompt] = useState(
    value?.system_prompt_override || defaultSystemPrompt
  );
  const [sectionOverrides, setSectionOverrides] = useState<Record<string, string>>(
    value?.section_overrides || {}
  );

  const handleSystemPromptChange = (text: string) => {
    setSystemPrompt(text);
    onChange({ system_prompt_override: text, section_overrides: sectionOverrides });
  };

  const handleSectionChange = (key: string, text: string) => {
    const next = { ...sectionOverrides, [key]: text };
    if (!text) delete next[key];
    setSectionOverrides(next);
    onChange({ system_prompt_override: systemPrompt, section_overrides: next });
  };

  return (
    <div style={{ padding: "12px", border: "1px solid #e0e0e0", borderRadius: "8px", marginBottom: "16px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "10px" }}>
        <span style={{ fontWeight: 600, fontSize: "14px" }}>创作风格（高级模式）</span>
        <button onClick={onExit} style={{ fontSize: "12px", padding: "2px 8px", cursor: "pointer" }}>退出高级模式</button>
      </div>

      <div style={{ marginBottom: "12px" }}>
        <label style={{ fontSize: "12px", color: "#666", marginBottom: "4px", display: "block" }}>系统角色指令</label>
        <textarea
          value={systemPrompt}
          onChange={(e) => handleSystemPromptChange(e.target.value)}
          rows={6}
          style={{ width: "100%", fontSize: "12px", padding: "6px", border: "1px solid #d9d9d9", borderRadius: "4px", resize: "vertical" }}
        />
        <button onClick={() => handleSystemPromptChange(defaultSystemPrompt)} style={{ fontSize: "11px", marginTop: "4px", cursor: "pointer" }}>恢复默认</button>
      </div>

      <div>
        <label style={{ fontSize: "12px", color: "#666", marginBottom: "6px", display: "block" }}>各章节个性化指令</label>
        {sections.map((sec) => (
          <div key={sec.key} style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "4px" }}>
            <span style={{ width: "120px", fontSize: "12px", overflow: "hidden", textOverflow: "ellipsis" }}>{sec.title}</span>
            {sectionOverrides[sec.key] !== undefined ? (
              <div style={{ flex: 1, display: "flex", gap: "4px" }}>
                <input
                  type="text"
                  value={sectionOverrides[sec.key]}
                  onChange={(e) => handleSectionChange(sec.key, e.target.value)}
                  placeholder="此章节的额外指令..."
                  style={{ flex: 1, fontSize: "12px", padding: "2px 6px", border: "1px solid #d9d9d9", borderRadius: "4px" }}
                />
                <button onClick={() => handleSectionChange(sec.key, "")} style={{ fontSize: "11px", cursor: "pointer" }}>清除</button>
              </div>
            ) : (
              <button onClick={() => handleSectionChange(sec.key, "")} style={{ fontSize: "11px", cursor: "pointer" }}>自定义</button>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};

export { AdvancedStylePanel };
