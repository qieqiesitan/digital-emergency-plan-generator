import React, { useState } from "react";
import { Button, Input, Space, Typography, List, Tag } from "antd";
import { UndoOutlined, DeleteOutlined, EditOutlined } from "@ant-design/icons";

const { Text } = Typography;

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
    const next = { ...sectionOverrides };
    if (text) {
      next[key] = text;
    } else {
      delete next[key];
    }
    setSectionOverrides(next);
    onChange({ system_prompt_override: systemPrompt, section_overrides: next });
  };

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
        <Text strong>系统角色指令</Text>
        <Button size="small" onClick={onExit} type="link" danger>退出高级模式</Button>
      </div>

      <Input.TextArea
        value={systemPrompt}
        onChange={(e) => handleSystemPromptChange(e.target.value)}
        rows={5}
        style={{ fontSize: 12, marginBottom: 4 }}
      />
      <Button
        size="small"
        icon={<UndoOutlined />}
        onClick={() => handleSystemPromptChange(defaultSystemPrompt)}
        style={{ marginBottom: 16 }}
      >
        恢复默认
      </Button>

      <Text strong style={{ display: "block", marginBottom: 8 }}>各章节个性化指令</Text>
      <List
        size="small"
        dataSource={sections}
        renderItem={(sec) => (
          <List.Item style={{ padding: "4px 0" }}>
            <Space style={{ width: "100%", justifyContent: "space-between" }}>
              <Text style={{ fontSize: 12, maxWidth: 160 }} ellipsis>{sec.title}</Text>
              {sectionOverrides[sec.key] !== undefined ? (
                <Space.Compact style={{ width: "60%" }}>
                  <Input
                    size="small"
                    value={sectionOverrides[sec.key]}
                    onChange={(e) => handleSectionChange(sec.key, e.target.value)}
                    placeholder="此章节的额外指令..."
                    style={{ fontSize: 12 }}
                  />
                  <Button
                    size="small"
                    icon={<DeleteOutlined />}
                    onClick={() => handleSectionChange(sec.key, "")}
                  />
                </Space.Compact>
              ) : (
                <Button
                  size="small"
                  type="dashed"
                  icon={<EditOutlined />}
                  onClick={() => handleSectionChange(sec.key, "")}
                >
                  自定义
                </Button>
              )}
            </Space>
          </List.Item>
        )}
      />
    </div>
  );
};

export { AdvancedStylePanel };
