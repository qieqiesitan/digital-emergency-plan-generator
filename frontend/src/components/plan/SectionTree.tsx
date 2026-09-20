import { Tree, Tooltip } from "antd";
import type { PlanSection } from "@/types/plan";
import type { SectionTemplate } from "@/types/plan";
import type { DataNode } from "antd/es/tree";

/** 与后端 app/services/data_marks.py 的 DOMAIN_LABELS 保持一致 */
const DOMAIN_LABELS: Record<string, string> = {
  risk_sources: "风险分级管控",
  emergency_resources: "应急资源",
  org_structure: "应急组织",
};

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
      const staleDomains = section?.stale_domains ?? [];
      const staleText = staleDomains
        .map((d) => DOMAIN_LABELS[d] ?? d)
        .join("、");


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
            {staleDomains.length > 0 && (
              <Tooltip title={`依赖数据已更新：${staleText}。建议重新生成本章节。`}>
                <span style={{ marginLeft: 4, color: "#fa8c16", fontWeight: "bold" }}>⚠</span>
              </Tooltip>
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
        ✓ 已完成 · ! 必填未完成 · ⏳ 生成中 · 🤖 可 AI 生成 · ⚠ 依赖数据已更新
        <div style={{ color: "#999", fontSize: 12 }}>空章节会列入导出校验清单</div>
      </div>
    </>
  );
}
