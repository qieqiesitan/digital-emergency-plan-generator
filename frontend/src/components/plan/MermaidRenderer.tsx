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

  // Replace fullwidth punctuation that confuse the Mermaid parser
  // Fullwidth parentheses, colon, brackets, braces
  result = result.replace(/\uff08/g, "(").replace(/\uff09/g, ")");
  result = result.replace(/\uff1a/g, ":");
  result = result.replace(/\uff3b/g, "[").replace(/\uff3d/g, "]");
  result = result.replace(/\uff5b/g, "{").replace(/\uff5d/g, "}");

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

  // Fix: Join broken edge definitions (arrow on one line, label on next)
  lines = result.split("\n");
  const cleaned: string[] = [];
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trimEnd();
    const stripped = line.trim();
    // Is this line a bare arrow?
    const bareArrow = /^(\s*\w+\s*(?:-->|->)\s*)$/.test(line);
    const partial = /^(.+?(?:-->|->)\|?)\s*$/.test(line) &&
      !stripped.endsWith("]") && !stripped.endsWith("}") && !stripped.endsWith(")");
    if ((bareArrow || partial) && i + 1 < lines.length) {
      // Look ahead for label, skipping empty lines
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
}

/**
 * Extracts ```mermaid code blocks from HTML, renders them as SVG,
 * and returns the HTML with diagrams inserted after each code block.
 * Failed blocks are shown with a visible red-tinted error card.
 */
export default function MermaidRenderer({ html }: MermaidRendererProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const svgCache = useRef<Map<string, string>>(new Map());

  useEffect(() => {
    if (!containerRef.current) return;
    initMermaid();

    // Find all <code class="language-mermaid"> elements
    const codeBlocks = containerRef.current.querySelectorAll("code.language-mermaid");

    codeBlocks.forEach(async (codeBlock) => {
      const text = codeBlock.textContent || "";
      const key = sanitizeMermaidText(text).trim();

      // Check cache
      let svg: string;
      let success = true;
      if (svgCache.current.has(key)) {
        svg = svgCache.current.get(key)!;
      } else {
        try {
          const { svg: rendered } = await mermaid.render(
            `mermaid-${Math.random().toString(36).slice(2, 9)}`,
            key
          );
          svg = rendered;
          svgCache.current.set(key, svg);
        } catch {
          success = false;
          svg = "";
        }
      }

      // Replace the code block parent with the rendered SVG
      const pre = codeBlock.parentElement;
      if (pre && pre.tagName === "PRE") {
        const wrapper = document.createElement("div");
        wrapper.className = "mermaid-diagram";

        if (success) {
          wrapper.style.cssText =
            "margin:16px 0; padding:16px; background:#fafafa; border:1px solid #e8e8e8; border-radius:6px; overflow-x:auto;";
        } else {
          wrapper.style.cssText =
            "margin:16px 0; padding:16px; background:#fff2f0; border:1px solid #ffccc7; border-radius:6px; overflow-x:auto;";
        }

        // Add a label
        const label = document.createElement("div");
        if (success) {
          label.style.cssText =
            "font-size:12px; color:#999; margin-bottom:8px; font-weight:500;";
          label.textContent = "流程图";
        } else {
          label.style.cssText =
            "font-size:12px; color:#ff4d4f; margin-bottom:8px; font-weight:500;";
          label.textContent = "流程图渲染失败（语法错误）";
        }
        wrapper.appendChild(label);

        // Add the SVG or error content
        const svgContainer = document.createElement("div");
        svgContainer.innerHTML = svg;
        svgContainer.style.cssText = "text-align:center;";
        wrapper.appendChild(svgContainer);

        // Add collapsible source code
        const details = document.createElement("details");
        details.style.cssText = "margin-top:8px;";
        const summary = document.createElement("summary");
        summary.style.cssText = "font-size:11px; color:#bbb; cursor:pointer;";
        summary.textContent = "查看源码";
        details.appendChild(summary);
        const codeDisplay = document.createElement("pre");
        codeDisplay.style.cssText =
          "margin-top:4px; padding:8px; background:#f5f5f5; border-radius:4px; font-size:11px; overflow-x:auto;";
        codeDisplay.textContent = text;
        details.appendChild(codeDisplay);
        wrapper.appendChild(details);

        pre.replaceWith(wrapper);
      }
    });
  }, [html]);

  return <div ref={containerRef} dangerouslySetInnerHTML={{ __html: html }} />;
}
