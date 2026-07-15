import { useMemo } from "react";
import MarkdownIt from "markdown-it";
import MermaidRenderer from "@/components/plan/MermaidRenderer";

const md = new MarkdownIt({
  html: true,
  linkify: true,
  typographer: true,
  breaks: true,
});

interface MarkdownViewerProps {
  content: string;
  style?: React.CSSProperties;
}

export default function MarkdownViewer({ content, style }: MarkdownViewerProps) {
  const html = useMemo(() => md.render(content || ""), [content]);
  return <MermaidRenderer html={html} />;
}
