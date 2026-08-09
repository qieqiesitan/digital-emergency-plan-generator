import { Tree } from "antd";
import type { PlanSection } from "@/types/plan";
import type { SectionTemplate } from "@/types/plan";
import type { DataNode } from "antd/es/tree";

interface SectionTreeProps {
  sections: PlanSection[];
  templateSections: SectionTemplate[];
  selectedKey: string | null;
  onSelect: (sectionKey: string) => void;
  generatingKeys?: Set<string>;
}

function buildTreeNodes(sections: PlanSection[], templates: SectionTemplate[], generatingKeys?: Set<string>): DataNode[] {
  const sectionMap = new Map(sections.map((s) => [s.section_key, s]));

  function convert(nodes: SectionTemplate[], level: number): DataNode[] {
    return nodes.map((tpl) => {
      const section = sectionMap.get(tpl.key);
      const hasContent = (section?.content?.trim()?.length ?? 0) > 0;
      const isRequired = tpl.required;

      const isGenerating = generatingKeys?.has(tpl.key) ?? false;


      return {
        key: tpl.key,
        title: (
          <span style={{ paddingLeft: level * 12 }}>
            {hasContent && (
              <span style={{ color: "#52c41a", marginRight: 4, fontWeight: "bold" }}>✓</span>
            )}
            {!hasContent && isGenerating && (
              <span style={{ color: "#faad14", marginRight: 4, fontWeight: "bold" }}>⏳</span>
            )}
            {!hasContent && !isGenerating && isRequired && (
              <span style={{ color: "#ff4d4f", marginRight: 4, fontWeight: "bold" }}>!</span>
            )}
            {tpl.title}
            {tpl.ai_generatable && (
              <span style={{ marginLeft: 4, fontSize: 12 }}>🤖</span>
            )}
          </span>
        ),
        selectable: true,
        children: tpl.subsections.length > 0 ? convert(tpl.subsections, level + 1) : undefined,
      };
    });
  }

  return convert(templates, 0);
}

export default function SectionTree({ sections, templateSections, selectedKey, onSelect, generatingKeys }: SectionTreeProps) {
  const treeData = buildTreeNodes(sections, templateSections, generatingKeys);

  return (
    <>
      <Tree
        treeData={treeData}
        selectedKeys={selectedKey ? [selectedKey] : []}
        onSelect={(keys) => {
          if (keys.length > 0) onSelect(String(keys[0]));
        }}
        defaultExpandAll
        showIcon={false}
        style={{ background: "transparent" }}
      />
      <div style={{ marginTop: 8, paddingTop: 8, borderTop: "1px dashed #eee", fontSize: 12, color: "#666", lineHeight: 1.8 }}>
        <b>图例</b><br />
        ✓ 已完成 · ! 必填未完成 · ⏳ 生成中 · 🤖 可 AI 生成
        <div style={{ color: "#999", fontSize: 11 }}>空章节会列入导出校验清单</div>
      </div>
    </>
  );
}
