import { useEffect, useRef } from "react";
import mermaid from "mermaid";

// Initialize mermaid once
let initialized = false;
function initMermaid() {
  if (initialized) return;
  mermaid.initialize({
    startOnLoad: false,
    theme: "default",
    securityLevel: "loose",
    suppressErrorRendering: true,
    flowchart: { useMaxWidth: true, htmlLabels: true },
  });
  initialized = true;
}

/** Sanitize Mermaid node labels: replace fullwidth punctuation, strip non-Mermaid prefix,
 *  prepend flowchart header for orphan edge blocks */
function sanitizeMermaidText(text: string): string {
  let result = text;

  // 注意：不再把全角标点（（）［］｛｝：）转成半角。
  // mermaid v11 中全角括号/方括号/花括号/冒号在节点文本与边标签里是安全字面量，
  // 转成半角后反而会被当成语法符号导致解析失败（docx 用的旧版 mermaid 能容忍，
  // 前端 v11 不能，这是「docx 正常但预览失败」的根因之一）。

  // Strip leading non-Mermaid lines (e.g. stray section headings before the diagram)
  const MERMAID_KEYWORDS = [
    "flowchart ", "graph ", "sequencediagram", "classdiagram",
    "statediagram", "erdiagram", "gantt", "pie", "gitgraph",
    "mindmap", "timeline", "journey", "quadrantchart",
  ];
  let lines = result.split("\n");
  let startIdx = -1;
  for (let i = 0; i < lines.length; i++) {
    const t = lines[i].trim().toLowerCase();
    if (MERMAID_KEYWORDS.some((kw) => t.startsWith(kw))) {
      startIdx = i;
      break;
    }
  }
  if (startIdx > 0) {
    result = lines.slice(startIdx).join("\n");
  }

  // If no diagram header is present but edge syntax exists, prepend flowchart TD
  if (startIdx < 0 && (result.includes("-->") || result.includes(" -- "))) {
    result = "flowchart TD\n" + result;
  }

  // Fix: Convert old syntax "A -- text --> B" to "A -->|text| B"
  result = result.replace(/(\w+)\s+--\s+(.+?)\s+-->\s+(\w+)/g, "$1 -->|$2| $3");
  result = result.replace(/(\w+)\s+--\s+(.+?)\s+->\s+(\w+)/g, "$1 ->|$2| $3");
  // Fix: Quote pipe labels with parentheses
  result = result.replace(/(-->|-\.->|==>)\|([^|"\n]*?\([^|"\n]*?\)[^|"\n]*?)\|/g, "$1|\"$2\"|");
  result = result.replace(/(->)\|([^|"\n]*?\([^|"\n]*?\)[^|"\n]*?)\|/g, "$1|\"$2\"|");
  // Fix: Quote subgraph/end names with parentheses
  result = result.replace(/\b(subgraph)\s+(.+)/g, '$1 "$2"');

  // Fix: Wrap node labels containing English parentheses in quotes
  // (mermaid v11 treats bare "(" inside [..]/{..} as syntax and fails;
  //  the docx export uses an older mermaid that tolerates it.)
  // A[text (with parens)] -> A["text (with parens)"]
  result = result.replace(
    /(\w+)\s*(\[|\{)([\s\S]*?\([\s\S]*?\)[\s\S]*?)(\]|\})/g,
    (m, id, open, text, close) => {
      const trimmed = text.trim();
      if (trimmed.startsWith('"') && trimmed.endsWith('"')) {
        return m;
      }
      return `${id}${open}"${trimmed}"${close}`;
    }
  );

  // Fix: Join broken edge definitions (arrow on one line, label on next)
  lines = result.split("\n");
  const cleaned: string[] = [];
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trimEnd();
    const stripped = line.trim();
    const bareArrow = /^(\s*\w+\s*(?:-->|->)\s*)$/.test(line);
    const partial = /^(.+?(?:-->|->)\|?)\s*$/.test(line) &&
      !stripped.endsWith("]") && !stripped.endsWith("}") && !stripped.endsWith(")");
    if ((bareArrow || partial) && i + 1 < lines.length) {
      let j = i + 1;
      while (j < lines.length && !lines[j].trim()) j++;
      if (j < lines.length && lines[j].trim().startsWith("|")) {
        cleaned.push(line.trimEnd() + lines[j].trim());
        i = j;
        continue;
      }
    }
    if (!stripped) continue;
    cleaned.push(line);
  }
  result = cleaned.join("\n");

  return result;
}

interface MermaidRendererProps {
  html: string;
  diagramSvgs?: Record<string, {
    key?: string;
    placeholder?: boolean;
    reason?: string;
    svg?: string;
  }>;
}

/**
 * Extracts ```mermaid code blocks from HTML, renders them as SVG,
 * and returns the HTML with diagrams inserted after each code block.
 * Failed blocks are shown with a visible red-tinted error card.
 */
export default function MermaidRenderer({ html, diagramSvgs = {} }: MermaidRendererProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    // Render ALL mermaid code blocks + display pre-rendered SVGs in old-format divs
    const codeBlocks = containerRef.current.querySelectorAll(
      "code.language-mermaid"
    );

    // Display pre-rendered SVGs from old <div class="mermaid-rendered"> blocks
    containerRef.current.querySelectorAll("div.mermaid-rendered").forEach((div) => {
      const svg = div.querySelector("svg");
      if (svg) {
        const wrapper = document.createElement("div");
        wrapper.className = "mermaid-diagram";
        wrapper.style.cssText = "margin:16px 0; padding:16px; background:#fafafa; border:1px solid #e8e8e8; border-radius:6px; overflow-x:auto;";
        const label = document.createElement("div");
        label.style.cssText = "font-size:12px; color:#999; margin-bottom:8px; font-weight:500;";
        label.textContent = "流程图";
        wrapper.appendChild(label);
        const svgContainer = document.createElement("div");
        svgContainer.style.cssText = "text-align:center;";
        svgContainer.innerHTML = svg.outerHTML;
        wrapper.appendChild(svgContainer);
        div.replaceWith(wrapper);
      }
    });

    if (codeBlocks.length === 0) return;

    initMermaid();
    codeBlocks.forEach(async (codeBlock) => {
      const text = codeBlock.textContent || "";
      const key = sanitizeMermaidText(text).trim();

      let svg = "";
      let success = true;
      try {
        const { svg: rendered } = await mermaid.render(
          `mermaid-${Math.random().toString(36).slice(2, 9)}`,
          key
        );
        svg = rendered;
      } catch {
        success = false;
      }

      const pre = codeBlock.parentElement;
      if (!pre || pre.tagName !== "PRE") return;

      const wrapper = document.createElement("div");
      wrapper.className = "mermaid-diagram";
      wrapper.style.cssText = success
        ? "margin:16px 0; padding:16px; background:#fafafa; border:1px solid #e8e8e8; border-radius:6px; overflow-x:auto;"
        : "margin:16px 0; padding:16px; background:#fff2f0; border:1px solid #ffccc7; border-radius:6px; overflow-x:auto;";

      const label = document.createElement("div");
      label.style.cssText = success
        ? "font-size:12px; color:#999; margin-bottom:8px; font-weight:500;"
        : "font-size:12px; color:#ff4d4f; margin-bottom:8px; font-weight:500;";
      label.textContent = success ? "流程图" : "流程图渲染失败（语法错误）";
      wrapper.appendChild(label);

      const svgContainer = document.createElement("div");
      svgContainer.innerHTML = svg;
      svgContainer.style.cssText = "text-align:center;";
      wrapper.appendChild(svgContainer);

      pre.replaceWith(wrapper);
    });
  }, [html]);

  // 非占位 SVG 直接内嵌
  const svgHtml = Object.values(diagramSvgs)
    .filter((meta) => meta?.svg && !meta?.placeholder)
    .map((meta) => meta!.svg!)
    .join("");

  // 占位块
  const diagramHtml = Object.entries(diagramSvgs)
    .filter(([, meta]) => meta?.placeholder)
    .map(([key, meta]) =>
      `<div class="diagram-placeholder" data-diagram-key="${key}" style="border:2px dashed #d9d9d9;border-radius:8px;padding:24px;text-align:center;color:#999;margin:16px 0;">
         <div style="font-size:14px;font-weight:500;color:#666;">【${key}】</div>
         <div style="font-size:12px;margin-top:8px;">待补充企业数据后生成（${meta?.reason || ""}）</div>
       </div>`
    )
    .join("");

  return <div ref={containerRef} dangerouslySetInnerHTML={{ __html: html + svgHtml + diagramHtml }} />;
}
