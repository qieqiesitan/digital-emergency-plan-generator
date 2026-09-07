import { useEffect, useRef, type ReactNode } from "react";
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
import { LoadingOutlined } from "@ant-design/icons";
import {
  BoldOutlined, ItalicOutlined, UnderlineOutlined, StrikethroughOutlined,
  OrderedListOutlined, UnorderedListOutlined, TableOutlined,
  UndoOutlined, RedoOutlined, AlignLeftOutlined, AlignCenterOutlined, AlignRightOutlined,
} from "@ant-design/icons";
import type { Editor } from "@tiptap/core";

export interface TiptapEditorHandle {
  getEditor: () => Editor | null;
}

interface TiptapEditorProps {
  content: string;
  onChange: (html: string) => void;
  readOnly?: boolean;
  placeholder?: string;
  maxHeight?: string;
  onReady?: (editor: Editor) => void;
  onSelectionUpdate?: (editor: Editor) => void;
}

function ToolbarButton({
  onClick, active, disabled, title, children,
}: {
  onClick: () => void;
  active?: boolean;
  disabled?: boolean;
  title: string;
  children: ReactNode;
}) {
  return (
    <Tooltip title={title}>
      <Button
        type={active ? "primary" : "text"}
        size="small"
        disabled={disabled}
        onClick={onClick}
        style={{ minWidth: 28, padding: "0 6px" }}
      >
        {children}
      </Button>
    </Tooltip>
  );
}

export default function TiptapEditor({
  content, onChange, readOnly, placeholder, maxHeight, onReady, onSelectionUpdate,
}: TiptapEditorProps) {
  const isInternalChange = useRef(false);
  const onReadyRef = useRef(onReady);
  onReadyRef.current = onReady;

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
      isInternalChange.current = false;
    },
    onSelectionUpdate: ({ editor: ed }) => {
      onSelectionUpdate?.(ed);
    },
  });

  // Sync editor when content prop changes externally (e.g., switching sections)
  useEffect(() => {
    if (!editor) return;
    if (isInternalChange.current) return;
    const html = editor.getHTML();
    const next = content || "";
    if (html !== next) {
      editor.commands.setContent(next, { emitUpdate: false });
    }
  }, [content, editor]);

  useEffect(() => {
    if (editor) onReadyRef.current?.(editor);
  }, [editor]);

  if (!editor) {
    return (
      <div
        style={{
          minHeight: 300,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <LoadingOutlined /> <span style={{ marginLeft: 8 }}>编辑器初始化中...</span>
      </div>
    );
  }

  const dividerStyle: React.CSSProperties = {
    width: 1,
    height: 20,
    background: "#d9d9d9",
    margin: "2px 4px",
    display: "inline-block",
  };

  return (
    <div style={{ border: "1px solid #d9d9d9", borderRadius: 8, overflow: "hidden" }}>
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: 4,
          padding: "6px 8px",
          borderBottom: "1px solid #f0f0f0",
          background: "#fafafa",
        }}
      >
        <ToolbarButton title="撤销" disabled={readOnly || !editor.can().undo()} onClick={() => editor.chain().focus().undo().run()}>
          <UndoOutlined />
        </ToolbarButton>
        <ToolbarButton title="重做" disabled={readOnly || !editor.can().redo()} onClick={() => editor.chain().focus().redo().run()}>
          <RedoOutlined />
        </ToolbarButton>
        <span style={dividerStyle} />
        <ToolbarButton title="加粗" active={editor.isActive("bold")} disabled={readOnly} onClick={() => editor.chain().focus().toggleBold().run()}>
          <BoldOutlined />
        </ToolbarButton>
        <ToolbarButton title="斜体" active={editor.isActive("italic")} disabled={readOnly} onClick={() => editor.chain().focus().toggleItalic().run()}>
          <ItalicOutlined />
        </ToolbarButton>
        <ToolbarButton title="下划线" active={editor.isActive("underline")} disabled={readOnly} onClick={() => editor.chain().focus().toggleUnderline().run()}>
          <UnderlineOutlined />
        </ToolbarButton>
        <ToolbarButton title="删除线" active={editor.isActive("strike")} disabled={readOnly} onClick={() => editor.chain().focus().toggleStrike().run()}>
          <StrikethroughOutlined />
        </ToolbarButton>
        <span style={dividerStyle} />
        <ToolbarButton title="标题 1" active={editor.isActive("heading", { level: 1 })} disabled={readOnly} onClick={() => editor.chain().focus().toggleHeading({ level: 1 }).run()}>
          H1
        </ToolbarButton>
        <ToolbarButton title="标题 2" active={editor.isActive("heading", { level: 2 })} disabled={readOnly} onClick={() => editor.chain().focus().toggleHeading({ level: 2 }).run()}>
          H2
        </ToolbarButton>
        <ToolbarButton title="标题 3" active={editor.isActive("heading", { level: 3 })} disabled={readOnly} onClick={() => editor.chain().focus().toggleHeading({ level: 3 }).run()}>
          H3
        </ToolbarButton>
        <span style={dividerStyle} />
        <ToolbarButton title="无序列表" active={editor.isActive("bulletList")} disabled={readOnly} onClick={() => editor.chain().focus().toggleBulletList().run()}>
          <UnorderedListOutlined />
        </ToolbarButton>
        <ToolbarButton title="有序列表" active={editor.isActive("orderedList")} disabled={readOnly} onClick={() => editor.chain().focus().toggleOrderedList().run()}>
          <OrderedListOutlined />
        </ToolbarButton>
        <ToolbarButton title="插入表格" disabled={readOnly} onClick={() => editor.chain().focus().insertTable({ rows: 3, cols: 3, withHeaderRow: true }).run()}>
          <TableOutlined />
        </ToolbarButton>
        <span style={dividerStyle} />
        <ToolbarButton title="左对齐" active={editor.isActive({ textAlign: "left" })} disabled={readOnly} onClick={() => editor.chain().focus().setTextAlign("left").run()}>
          <AlignLeftOutlined />
        </ToolbarButton>
        <ToolbarButton title="居中" active={editor.isActive({ textAlign: "center" })} disabled={readOnly} onClick={() => editor.chain().focus().setTextAlign("center").run()}>
          <AlignCenterOutlined />
        </ToolbarButton>
        <ToolbarButton title="右对齐" active={editor.isActive({ textAlign: "right" })} disabled={readOnly} onClick={() => editor.chain().focus().setTextAlign("right").run()}>
          <AlignRightOutlined />
        </ToolbarButton>
      </div>
      <EditorContent
        editor={editor}
        style={{
          minHeight: 320,
          padding: "12px 16px",
          ...(maxHeight ? { maxHeight, overflow: "auto" } : {}),
        }}
      />
    </div>
  );
}
