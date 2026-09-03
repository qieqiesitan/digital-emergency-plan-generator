import { useRef, useState } from "react";
import { Button } from "antd";
import { LoadingOutlined } from "@ant-design/icons";
import type { Editor } from "@tiptap/core";
import AppIcon from "@/components/common/AppIcon";
import MermaidRenderer from "./MermaidRenderer";
import AIGenerateButton from "./AIGenerateButton";
import TiptapEditor from "@/components/report/TiptapEditor";

interface RichTextEditorProps {
  content: string;
  onChange: (html: string) => void;
  readOnly?: boolean;
  placeholder?: string;
  aiGenerated?: boolean;
  planId?: string;
  sectionKey?: string;
  sectionTitle?: string;
  diagramSvgs?: Record<string, {
    key?: string;
    placeholder?: boolean;
    reason?: string;
    svg?: string;
  }>;
}

export default function RichTextEditor({
  content, onChange, readOnly, placeholder,
  aiGenerated, planId, sectionKey, sectionTitle, diagramSvgs,
}: RichTextEditorProps) {
  const editorRef = useRef<Editor | null>(null);
  const lastSelectionFrom = useRef(0);
  const lastSelectionTo = useRef(0);

  const [selectionText, setSelectionText] = useState("");
  const [showRewriteBtn, setShowRewriteBtn] = useState(false);
  const [aiRewriteModalOpen, setAiRewriteModalOpen] = useState(false);
  const [isRegenerating, setIsRegenerating] = useState(false);

  const showMermaid =
    readOnly &&
    (content.includes("language-mermaid") ||
      Object.keys(diagramSvgs || {}).length > 0);

  const wrapperStyle = aiGenerated
    ? { borderLeft: "3px solid rgba(24, 144, 255, 0.4)", background: "rgba(24, 144, 255, 0.02)" }
    : undefined;

  return (
    <div style={{ border: "1px solid #d9d9d9", borderRadius: 6, overflow: "hidden", ...wrapperStyle }}>
      {showRewriteBtn && !readOnly && (
        <div style={{ padding: "4px 8px", background: "#e6f7ff", borderBottom: "1px solid #91d5ff", display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ fontSize: 12, color: "#666" }}>已选中 {selectionText.length} 个字符</span>
          {isRegenerating ? (
            <span style={{ fontSize: 12, color: "#1677ff" }}>
              <LoadingOutlined style={{ marginRight: 4 }} />AI 重写中...
            </span>
          ) : (
            <Button size="small" type="primary" ghost icon={<AppIcon name="ai" size={14} />} onClick={() => setAiRewriteModalOpen(true)}>
              AI 重写选中内容
            </Button>
          )}
        </div>
      )}

      {showMermaid ? (
        <MermaidRenderer html={content} diagramSvgs={diagramSvgs} />
      ) : (
        <TiptapEditor
          content={content}
          onChange={onChange}
          readOnly={readOnly}
          placeholder={placeholder}
          onReady={(ed) => { editorRef.current = ed; }}
          onSelectionUpdate={(ed) => {
            const { from, to } = ed.state.selection;
            lastSelectionFrom.current = from;
            lastSelectionTo.current = to;
            if (from !== to) {
              const text = ed.state.doc.textBetween(from, to);
              if (text.length > 10) {
                setSelectionText(text);
                setShowRewriteBtn(true);
                return;
              }
            }
            setShowRewriteBtn(false);
            setSelectionText("");
          }}
        />
      )}

      {editorRef.current && aiRewriteModalOpen && planId && sectionKey && (
        <AIGenerateButton
          planId={planId}
          sectionKey={sectionKey}
          sectionTitle={sectionTitle}
          mode="selection"
          selectedText={selectionText}
          contextBefore={editorRef.current.state.doc.textBetween(
            Math.max(0, lastSelectionFrom.current - 200),
            lastSelectionFrom.current
          )}
          contextAfter={editorRef.current.state.doc.textBetween(
            lastSelectionTo.current,
            Math.min(editorRef.current.state.doc.content.size, lastSelectionTo.current + 200)
          )}
          onContentChunk={() => {
            setIsRegenerating(true);
          }}
          onGenerateComplete={(text) => {
            editorRef.current?.chain().setTextSelection({
              from: lastSelectionFrom.current,
              to: lastSelectionTo.current,
            }).deleteSelection().insertContent(text).run();
            setAiRewriteModalOpen(false);
            setShowRewriteBtn(false);
            setIsRegenerating(false);
          }}
        />
      )}
    </div>
  );
}
