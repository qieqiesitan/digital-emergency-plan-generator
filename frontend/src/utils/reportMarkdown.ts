import MarkdownIt from "markdown-it";

// 与 PlanEditorPage 流式预览保持一致的 markdown-it 配置：
// 报告正文（风险评估/应急资源调查）统一用同一渲染管线，避免
// markdown/HTML 表格符号在界面上原样泄漏。
const reportMd = new MarkdownIt({
  html: true,
  linkify: true,
  typographer: true,
  breaks: true,
});

export function renderReportMarkdown(text: string): string {
  return reportMd.render(text || "");
}

/** 标签 → markdown 字符映射（不带左右空白，由调用方决定） */
const INLINE_MARKERS: Record<string, [string, string]> = {
  strong: ["**", "**"],
  b: ["**", "**"],
  em: ["*", "*"],
  i: ["*", "*"],
  u: ["__", "__"],
  s: ["~~", "~~"],
  strike: ["~~", "~~"],
  code: ["`", "`"],
};

const BLOCK_TAGS = new Set([
  "p", "div", "h1", "h2", "h3", "h4", "h5", "h6",
  "ul", "ol", "li", "blockquote", "pre", "table",
]);

function decodeEntities(text: string): string {
  return text
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, "\"")
    .replace(/&#39;/g, "'")
    .replace(/&nbsp;/g, " ")
    .replace(/&amp;/g, "&");
}

/**
 * 把 TipTap / markdown-it 产出的章节 HTML 收敛回 Markdown。
 * 报告章节在草稿阶段以 Markdown 存储（summary.chapters），
 * 编辑器（Tiptap）只处理 HTML，因此保存/合并前需要反向转换。
 * 覆盖报告正文常用结构：段落/标题/列表/表格/代码块与行内粗斜体等；
 * 其余标签降级为纯文本。
 */
export function htmlToMarkdown(html: string): string {
  if (!html) return "";
  const out = convertContent(html);
  const joined = out
    .map((seg) => seg.trim())
    .filter((seg) => seg !== "")
    .join("\n\n")
    .replace(/\n{3,}/g, "\n\n");
  // 连续列表项之间去掉空行（markdown 列表项之间空行可接受，但保持紧凑）
  const lines = joined.split("\n");
  const result: string[] = [];
  for (let i = 0; i < lines.length; i += 1) {
    const line = lines[i];
    const prev = result[result.length - 1];
    if (line === "" && prev !== undefined && isListContinuation(prev)) {
      const next = lines[i + 1];
      if (next !== undefined && isListContinuation(next)) continue;
    }
    result.push(line);
  }
  return result.join("\n").trim();
}

function isListContinuation(line: string): boolean {
  return /^(\s*)([-*+]|\d+[.)])\s+/.test(line);
}

function attr(raw: string, name: string): string {
  const m = new RegExp(`${name}\\s*=\\s*(?:"([^"]*)"|'([^']*)')`, "i").exec(raw);
  return m ? decodeEntities(m[1] ?? m[2] ?? "") : "";
}

interface HtmlToken {
  kind: "text" | "open" | "close" | "self";
  tag?: string;
  raw?: string;
  text?: string;
}

/**
 * HTML 结构扫描器：产生扁平 token 序列（文本 / 开标签 / 自闭合 / 闭标签）。
 */
function tokenize(html: string): HtmlToken[] {
  const toks: HtmlToken[] = [];
  let i = 0;
  let textBuf = "";
  const flushText = () => {
    if (textBuf) {
      toks.push({ kind: "text", text: textBuf });
      textBuf = "";
    }
  };
  while (i < html.length) {
    if (html[i] !== "<") {
      textBuf += html[i];
      i += 1;
      continue;
    }
    const m = /^<\s*(\/?)\s*([a-zA-Z][a-zA-Z0-9]*)((?:"[^"]*"|'[^']*'|[^>"'])*)(\/?)\s*>/.exec(html.slice(i));
    if (!m) {
      textBuf += "<";
      i += 1;
      continue;
    }
    const [, slash, name, attrsRaw, selfSlash] = m;
    const tag = name.toLowerCase();
    const raw = html.slice(i, i + m[0].length);
    const selfClosing = selfSlash === "/" || tag === "br" || tag === "img" || tag === "hr";
    flushText();
    if (slash) toks.push({ kind: "close", tag, raw });
    else if (selfClosing) toks.push({ kind: "self", tag, raw });
    else toks.push({ kind: "open", tag, raw });
    i += m[0].length;
    void attrsRaw;
  }
  flushText();
  return toks;
}

/**
 * 从 tokens 的 pos 开始渲染块内容为 Markdown 行数组。
 * stopTag 非空时，扫描到该标签的闭标签即停（闭标签不消费）。
 */
/** 找到 tag 的配对闭标签下标；未找到返回 tokens.length */
function findCloseIndex(tokens: HtmlToken[], from: number, tag: string): number {
  let depth = 1;
  for (let i = from; i < tokens.length; i += 1) {
    const t = tokens[i];
    if (t.kind === "open" && t.tag === tag) depth += 1;
    else if (t.kind === "close" && t.tag === tag) {
      depth -= 1;
      if (depth === 0) return i;
    }
  }
  return tokens.length;
}

/** 渲染一段行内 token 序列为 Markdown 文本 */
function renderInline(tokens: HtmlToken[], from: number, to: number): string {
  let out = "";
  let i = from;
  while (i < to && i < tokens.length) {
    const tok = tokens[i];
    if (tok.kind === "text") {
      out += tok.text ?? "";
      i += 1;
      continue;
    }
    if (tok.kind === "self") {
      out += tok.tag === "br" ? "\n" : "";
      i += 1;
      continue;
    }
    if (tok.kind === "close") {
      i += 1;
      continue;
    }
    // open：处理配对标签
    const tag = tok.tag!;
    const close = findCloseIndex(tokens, i + 1, tag);
    if (close >= tokens.length) {
      out += tok.raw ?? "";
      i += 1;
      continue;
    }
    if (tag === "a") {
      const href = attr(tok.raw || "", "href");
      const text = renderInline(tokens, i + 1, close).trim();
      out += href && text ? `[${text}](${href})` : text;
    } else if (tag === "img") {
      const src = attr(tok.raw || "", "src");
      const alt = attr(tok.raw || "", "alt");
      out += src ? `![${alt}](${src})` : alt || "";
    } else if (INLINE_MARKERS[tag]) {
      const [a, b] = INLINE_MARKERS[tag];
      const text = renderInline(tokens, i + 1, close);
      out += `${a}${text}${b}`;
    } else if (tag === "span" || tag === "font" || tag === "div") {
      out += renderInline(tokens, i + 1, close);
    } else {
      out += tok.raw ?? "";
      out += renderInline(tokens, i + 1, close);
      out += `</${tag}>`;
    }
    i = close + 1;
  }
  return decodeEntities(out);
}

/**
 * 块级渲染主入口：把 token 流按块结构转换为 Markdown 行数组。
 * 纯文本段落之间以连续块划分；块元素递归渲染。
 */
function renderBlocks(tokens: HtmlToken[]): string[] {
  const lines: string[] = [];
  let inlineStart = 0;
  let i = 0;
  const flushInline = () => {
    const text = renderInline(tokens, inlineStart, i).replace(/\s+/g, " ").trim();
    if (text) lines.push(text);
  };
  while (i < tokens.length) {
    const tok = tokens[i];
    if (tok.kind === "open" && BLOCK_TAGS.has(tok.tag!)) {
      flushInline();
      const close = findCloseIndex(tokens, i + 1, tok.tag!);
      const end = close >= tokens.length ? i + 1 : close;
      const inner = tokens.slice(i + 1, end);
      const line = renderBlockElement(tok.tag!, inner);
      if (line) lines.push(line);
      i = close >= tokens.length ? i + 1 : close + 1;
      inlineStart = i;
      continue;
    }
    i += 1;
  }
  flushInline();
  return lines;
}

/** 渲染单个块元素内容（已剥离外层标签），返回其 markdown 文本 */
function renderBlockElement(tag: string, inner: HtmlToken[]): string {
  switch (tag) {
    case "h1": case "h2": case "h3": case "h4": case "h5": case "h6": {
      const level = Number(tag[1]);
      return `${"#".repeat(level)} ${renderInline(inner, 0, inner.length).trim()}`;
    }
    case "p": case "div": {
      return renderInline(inner, 0, inner.length).trim();
    }
    case "li": {
      const nestedIdx = inner.findIndex(
        (t) => t.kind === "open" && (t.tag === "ul" || t.tag === "ol"),
      );
      if (nestedIdx >= 0) {
        const head = renderInline(inner, 0, nestedIdx).trim();
        const nestedLines = renderBlocks(inner.slice(nestedIdx));
        return ["- " + head, ...nestedLines.map((l) => `  ${l}`)].join("\n");
      }
      return "- " + renderInline(inner, 0, inner.length).trim();
    }
    case "ul": case "ol": {
      return renderBlocks(inner).join("\n");
    }
    case "blockquote": {
      return renderBlocks(inner).map((l) => `> ${l}`).join("\n");
    }
    case "pre": {
      const code = inner.filter((t) => t.kind === "text").map((t) => t.text ?? "").join("");
      return "```\n" + decodeEntities(code).replace(/\n+$/, "") + "\n```";
    }
    case "table": {
      return renderTable(inner);
    }
    default:
      return renderInline(inner, 0, inner.length).trim();
  }
}

/** 渲染 <table> 内容为 markdown 管道表（inner 为 table 内部 token） */
function renderTable(inner: HtmlToken[]): string {
  const rows: string[][] = [];
  let i = 0;
  while (i < inner.length) {
    if (inner[i].kind === "open" && inner[i].tag === "tr") {
      const trEnd = findCloseIndex(inner, i + 1, "tr");
      const row = inner.slice(i + 1, trEnd);
      const cells: string[] = [];
      let j = 0;
      while (j < row.length) {
        const t = row[j];
        if (t.kind === "open" && (t.tag === "td" || t.tag === "th")) {
          const cellEnd = findCloseIndex(row, j + 1, t.tag!);
          cells.push(renderInline(row, j + 1, cellEnd).trim());
          j = cellEnd + 1;
        } else {
          j += 1;
        }
      }
      rows.push(cells);
      i = trEnd + 1;
    } else {
      i += 1;
    }
  }
  if (rows.length === 0) return "";
  const widths = (rows[0] || []).map((_, ci) =>
    Math.max(...rows.map((r) => (r[ci] ?? "").length)),
  );
  const fmtRow = (r: string[]) =>
    `| ${r.map((c, ci) => (c ?? "").padEnd(widths[ci] ?? 0)).join(" | ")} |`;
  const sep = `| ${widths.map((w) => "-".repeat(Math.max(3, w))).join(" | ")} |`;
  return [fmtRow(rows[0] || []), sep, ...rows.slice(1).map(fmtRow)].join("\n");
}

/** 渲染全部 html 为 Markdown 行数组 */
function convertContent(html: string): string[] {
  return renderBlocks(tokenize(html));
}
