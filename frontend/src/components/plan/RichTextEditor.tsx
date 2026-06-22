import { useRef, useEffect } from "react";
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
import {
  BoldOutlined, ItalicOutlined, UnderlineOutlined, StrikethroughOutlined,
  OrderedListOutlined, UnorderedListOutlined, TableOutlined,
  UndoOutlined, RedoOutlined, AlignLeftOutlined, AlignCenterOutlined, AlignRightOutlined,
} from "@ant-design/icons";
import MermaidRenderer from "./MermaidRenderer";

interface RichTextEditorProps {
  content: string;
  onChange: (html: string) => void;
  readOnly?: boolean;
  placeholder?: string;
}

export default function RichTextEditor({ content, onChange, readOnly, placeholder }: RichTextEditorProps) {
  const isInternalChange = useRef(false);

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

  const showMermaid = readOnly && content.includes("language-mermaid");

  return (
    <div style={{ border: "1px solid #d9d9d9", borderRadius: 6, overflow: "hidden" }}>
      {!readOnly && (
        <div style={{ borderBottom: "1px solid #d9d9d9", padding: "4px 8px", background: "#fafafa", display: "flex", flexWrap: "wrap", gap: 2 }}>
          <Tooltip title="Bold"><Button type="text" size="small" icon={<BoldOutlined />} onClick={() => editor.chain().focus().toggleBold().run()} /></Tooltip>
          <Tooltip title="Italic"><Button type="text" size="small" icon={<ItalicOutlined />} onClick={() => editor.chain().focus().toggleItalic().run()} /></Tooltip>
          <Tooltip title="Underline"><Button type="text" size="small" icon={<UnderlineOutlined />} onClick={() => editor.chain().focus().toggleUnderline().run()} /></Tooltip>
          <Tooltip title="Strikethrough"><Button type="text" size="small" icon={<StrikethroughOutlined />} onClick={() => editor.chain().focus().toggleStrike().run()} /></Tooltip>
          <span style={{ width: 1, height: 20, background: "#d9d9d9", margin: "2px 4px", display: "inline-block" }} />
          <Tooltip title="H1"><Button type="text" size="small" onClick={() => editor.chain().focus().toggleHeading({ level: 1 }).run()}>H1</Button></Tooltip>
          <Tooltip title="H2"><Button type="text" size="small" onClick={() => editor.chain().focus().toggleHeading({ level: 2 }).run()}>H2</Button></Tooltip>
          <Tooltip title="H3"><Button type="text" size="small" onClick={() => editor.chain().focus().toggleHeading({ level: 3 }).run()}>H3</Button></Tooltip>
          <span style={{ width: 1, height: 20, background: "#d9d9d9", margin: "2px 4px", display: "inline-block" }} />
          <Tooltip title="Bullet List"><Button type="text" size="small" icon={<UnorderedListOutlined />} onClick={() => editor.chain().focus().toggleBulletList().run()} /></Tooltip>
          <Tooltip title="Ordered List"><Button type="text" size="small" icon={<OrderedListOutlined />} onClick={() => editor.chain().focus().toggleOrderedList().run()} /></Tooltip>
          <Tooltip title="Table"><Button type="text" size="small" icon={<TableOutlined />} onClick={() => editor.chain().focus().insertTable({ rows: 3, cols: 3, withHeaderRow: true }).run()} /></Tooltip>
          <span style={{ width: 1, height: 20, background: "#d9d9d9", margin: "2px 4px", display: "inline-block" }} />
          <Tooltip title="Left"><Button type="text" size="small" icon={<AlignLeftOutlined />} onClick={() => editor.chain().focus().setTextAlign("left").run()} /></Tooltip>
          <Tooltip title="Center"><Button type="text" size="small" icon={<AlignCenterOutlined />} onClick={() => editor.chain().focus().setTextAlign("center").run()} /></Tooltip>
          <Tooltip title="Right"><Button type="text" size="small" icon={<AlignRightOutlined />} onClick={() => editor.chain().focus().setTextAlign("right").run()} /></Tooltip>
          <span style={{ width: 1, height: 20, background: "#d9d9d9", margin: "2px 4px", display: "inline-block" }} />
          <Tooltip title="Undo"><Button type="text" size="small" icon={<UndoOutlined />} onClick={() => editor.chain().focus().undo().run()} /></Tooltip>
          <Tooltip title="Redo"><Button type="text" size="small" icon={<RedoOutlined />} onClick={() => editor.chain().focus().redo().run()} /></Tooltip>
        </div>
      )}
      {showMermaid ? (
        <MermaidRenderer html={content} />
      ) : (
        <EditorContent editor={editor} style={{ padding: "12px 16px", minHeight: 300, maxHeight: "calc(100vh - 320px)", overflow: "auto" }} />
      )}
    </div>
  );
}
