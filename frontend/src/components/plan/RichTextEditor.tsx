import { useRef, useEffect, useState } from "react";
import { useEditor, EditorContent } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import Underline from "@tiptap/extension-underline";
import TextAlign from "@tiptap/extension-text-align";
import Placeholder from "@tiptap/extension-placeholder";
import { Table } from "@tiptap/extension-table";
import { TableRow } from "@tiptap/extension-table-row";
import { TableCell } from "@tiptap/extension-table-cell";
import { TableHeader } from "@tiptap/extension-table-header";
import { Button, Tooltip } from "antd";
import { RobotOutlined, LoadingOutlined } from "@ant-design/icons";
import {
  BoldOutlined, ItalicOutlined, UnderlineOutlined, StrikethroughOutlined,
  OrderedListOutlined, UnorderedListOutlined, TableOutlined,
  UndoOutlined, RedoOutlined, AlignLeftOutlined, AlignCenterOutlined, AlignRightOutlined,
} from "@ant-design/icons";
import MermaidRenderer from "./MermaidRenderer";
import AIGenerateButton from "./AIGenerateButton";

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
  const isInternalChange = useRef(false);
  const lastSelectionFrom = useRef(0);
  const lastSelectionTo = useRef(0);

  const [selectionText, setSelectionText] = useState("");
  const [showRewriteBtn, setShowRewriteBtn] = useState(false);
  const [aiRewriteModalOpen, setAiRewriteModalOpen] = useState(false);
  const [isRegenerating, setIsRegenerating] = useState(false);

  const editor = useEditor({
    extensions: [
      StarterKit,
      Underline,
      TextAlign.configure({ types: ["heading", "paragraph"] }),
      Placeholder.configure({ placeholder: placeholder || "编辑章节内容..." }),
      Table.configure({ resizable: true }),
      TableRow, TableCell, TableHeader,
    ],
    content,
    editable: !readOnly,
    onUpdate: ({ editor: ed }) => {
      isInternalChange.current = true;
      onChange(ed.getHTML());
    },
    onSelectionUpdate: ({ editor: ed }) => {
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
    },
  });

  // Sync editor when content prop changes externally (e.g., switching sections)
  useEffect(() => {
    if (editor && !isInternalChange.current) {
      const currentHTML = editor.getHTML();
      if (content !== currentHTML) {
        editor.commands.setContent(content);
      }
    }
    isInternalChange.current = false;
  }, [content, editor]);

  if (!editor) return null;

  const showMermaid =
    readOnly &&
    (content.includes("language-mermaid") ||
      Object.keys(diagramSvgs || {}).length > 0);

  const wrapperStyle = aiGenerated
    ? { borderLeft: "3px solid rgba(24, 144, 255, 0.4)", background: "rgba(24, 144, 255, 0.02)" }
    : undefined;

  return (
    <div style={{ border: "1px solid #d9d9d9", borderRadius: 6, overflow: "hidden", ...wrapperStyle }}>
      {!readOnly && (
        <div style={{ borderBottom: "1px solid #d9d9d9", padding: "4px 8px", background: "#fafafa", display: "flex", flexWrap: "wrap", gap: 2 }}>
          <Tooltip title="加粗"><Button type="text" size="small" icon={<BoldOutlined />} onClick={() => editor.chain().focus().toggleBold().run()} /></Tooltip>
          <Tooltip title="斜体"><Button type="text" size="small" icon={<ItalicOutlined />} onClick={() => editor.chain().focus().toggleItalic().run()} /></Tooltip>
          <Tooltip title="下划线"><Button type="text" size="small" icon={<UnderlineOutlined />} onClick={() => editor.chain().focus().toggleUnderline().run()} /></Tooltip>
          <Tooltip title="删除线"><Button type="text" size="small" icon={<StrikethroughOutlined />} onClick={() => editor.chain().focus().toggleStrike().run()} /></Tooltip>
          <span style={{ width: 1, height: 20, background: "#d9d9d9", margin: "2px 4px", display: "inline-block" }} />
          <Tooltip title="H1"><Button type="text" size="small" onClick={() => editor.chain().focus().toggleHeading({ level: 1 }).run()}>H1</Button></Tooltip>
          <Tooltip title="H2"><Button type="text" size="small" onClick={() => editor.chain().focus().toggleHeading({ level: 2 }).run()}>H2</Button></Tooltip>
          <Tooltip title="H3"><Button type="text" size="small" onClick={() => editor.chain().focus().toggleHeading({ level: 3 }).run()}>H3</Button></Tooltip>
          <span style={{ width: 1, height: 20, background: "#d9d9d9", margin: "2px 4px", display: "inline-block" }} />
          <Tooltip title="无序列表"><Button type="text" size="small" icon={<UnorderedListOutlined />} onClick={() => editor.chain().focus().toggleBulletList().run()} /></Tooltip>
          <Tooltip title="有序列表"><Button type="text" size="small" icon={<OrderedListOutlined />} onClick={() => editor.chain().focus().toggleOrderedList().run()} /></Tooltip>
          <Tooltip title="表格"><Button type="text" size="small" icon={<TableOutlined />} onClick={() => editor.chain().focus().insertTable({ rows: 3, cols: 3, withHeaderRow: true }).run()} /></Tooltip>
          <span style={{ width: 1, height: 20, background: "#d9d9d9", margin: "2px 4px", display: "inline-block" }} />
          <Tooltip title="左对齐"><Button type="text" size="small" icon={<AlignLeftOutlined />} onClick={() => editor.chain().focus().setTextAlign("left").run()} /></Tooltip>
          <Tooltip title="居中"><Button type="text" size="small" icon={<AlignCenterOutlined />} onClick={() => editor.chain().focus().setTextAlign("center").run()} /></Tooltip>
          <Tooltip title="右对齐"><Button type="text" size="small" icon={<AlignRightOutlined />} onClick={() => editor.chain().focus().setTextAlign("right").run()} /></Tooltip>
          <span style={{ width: 1, height: 20, background: "#d9d9d9", margin: "2px 4px", display: "inline-block" }} />
          <Tooltip title="撤销"><Button type="text" size="small" icon={<UndoOutlined />} onClick={() => editor.chain().focus().undo().run()} /></Tooltip>
          <Tooltip title="重做"><Button type="text" size="small" icon={<RedoOutlined />} onClick={() => editor.chain().focus().redo().run()} /></Tooltip>
        </div>
      )}

      {showRewriteBtn && !readOnly && (
        <div style={{ padding: "4px 8px", background: "#e6f7ff", borderBottom: "1px solid #91d5ff", display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ fontSize: 12, color: "#666" }}>已选中 {selectionText.length} 个字符</span>
          {isRegenerating ? (
            <span style={{ fontSize: 12, color: "#1677ff" }}>
              <LoadingOutlined style={{ marginRight: 4 }} />AI 重写中...
            </span>
          ) : (
            <Button size="small" type="primary" ghost icon={<RobotOutlined />} onClick={() => setAiRewriteModalOpen(true)}>
              AI 重写选中内容
            </Button>
          )}
        </div>
      )}

      {showMermaid ? (
        <MermaidRenderer html={content} diagramSvgs={diagramSvgs} />
      ) : (
        <EditorContent editor={editor} style={{ padding: "12px 16px", minHeight: 300, maxHeight: "calc(100vh - 320px)", overflow: "auto" }} />
      )}

      {aiRewriteModalOpen && planId && sectionKey && (
        <AIGenerateButton
          planId={planId}
          sectionKey={sectionKey}
          sectionTitle={sectionTitle}
          mode="selection"
          selectedText={selectionText}
          contextBefore={editor.state.doc.textBetween(
            Math.max(0, lastSelectionFrom.current - 200),
            lastSelectionFrom.current
          )}
          contextAfter={editor.state.doc.textBetween(
            lastSelectionTo.current,
            Math.min(editor.state.doc.content.size, lastSelectionTo.current + 200)
          )}
          onContentChunk={() => {
            setIsRegenerating(true);
          }}
          onGenerateComplete={(text) => {
            editor.chain().setTextSelection({
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
