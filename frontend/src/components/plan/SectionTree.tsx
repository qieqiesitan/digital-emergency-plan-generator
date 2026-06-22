import { Tree } from "antd";
import type { PlanSection } from "@/types/plan";
import type { SectionTemplate } from "@/types/template";
import type { DataNode } from "antd/es/tree";

interface SectionTreeProps {
  sections: PlanSection[];
  templateSections: SectionTemplate[];
  selectedKey: string | null;
  onSelect: (sectionKey: string) => void;
}

function buildTreeNodes(sections: PlanSection[], templates: SectionTemplate[]): DataNode[] {
  const sectionMap = new Map(sections.map((s) => [s.section_key, s]));

  function convert(nodes: SectionTemplate[], level: number): DataNode[] {
    return nodes.map((tpl) => {
      const section = sectionMap.get(tpl.key);
      const hasContent = (section?.content?.trim()?.length ?? 0) > 0;
      const isRequired = tpl.required;

      let iconStr = "";
      if (hasContent) {
        iconStr = "✓ ";
      } else if (isRequired) {
        iconStr = "! ";
      }

      const aiIcon = tpl.ai_generatable ? " 🤖" : "";

      return {
        key: tpl.key,
        title: (
          <span style={{ paddingLeft: level * 12 }}>
            {hasContent && (
              <span style={{ color: "#52c41a", marginRight: 4, fontWeight: "bold" }}>✓</span>
            )}
            {!hasContent && isRequired && (
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

export default function SectionTree({ sections, templateSections, selectedKey, onSelect }: SectionTreeProps) {
  const treeData = buildTreeNodes(sections, templateSections);

  return (
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
  );
}
