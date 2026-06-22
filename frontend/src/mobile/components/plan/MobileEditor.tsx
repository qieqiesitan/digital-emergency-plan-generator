import React, { forwardRef, useState, useCallback } from "react";
import { Eye, Edit3 } from "lucide-react";

interface MobileEditorProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  readOnly?: boolean;
  onFocus?: () => void;
  onBlur?: () => void;
  className?: string;
}

const MobileEditor = forwardRef<HTMLTextAreaElement, MobileEditorProps>(
  function MobileEditor(
    { value, onChange, placeholder, readOnly, onFocus, onBlur, className = "" },
    ref
  ) {
    const [preview, setPreview] = useState(false);

    const handleChange = useCallback(
      (e: React.ChangeEvent<HTMLTextAreaElement>) => {
        onChange(e.target.value);
      },
      [onChange]
    );

    // 简易 Markdown 渲染（加粗、标题、列表）
    const renderPreview = (md: string) => {
      let html = md
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        // 标题
        .replace(/^### (.+)$/gm, '<h4 class="text-h3 font-semibold mt-4 mb-2">$1</h4>')
        .replace(/^## (.+)$/gm, '<h3 class="text-h2 font-semibold mt-4 mb-2">$1</h3>')
        .replace(/^# (.+)$/gm, '<h2 class="text-h1 font-semibold mt-4 mb-2">$1</h2>')
        // 粗体
        .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
        // 斜体
        .replace(/\*(.+?)\*/g, "<em>$1</em>")
        // 无序列表
        .replace(/^- (.+)$/gm, '<li class="ml-4 list-disc">$1</li>')
        // 分割线
        .replace(/^---$/gm, '<hr class="my-4 border-neutral-200" />')
        // 换行
        .replace(/\n\n/g, "</p><p class='mb-2'>")
        .replace(/\n/g, "<br />");

      html = "<p class='mb-2'>" + html + "</p>";
      return html;
    };

    if (preview) {
      return (
        <div className={`flex-1 overflow-y-auto ${className}`}>
          <div className="flex items-center justify-end px-md py-2 bg-neutral-50 border-b border-neutral-100">
            <button
              className="flex items-center gap-xs text-caption text-primary-600 font-medium"
              onClick={() => setPreview(false)}
            >
              <Edit3 size={14} /> 编辑
            </button>
          </div>
          <div
            className="p-md prose prose-sm max-w-none text-body leading-relaxed"
            dangerouslySetInnerHTML={{ __html: renderPreview(value) }}
          />
        </div>
      );
    }

    return (
      <div className={`flex-1 flex flex-col ${className}`}>
        {value.length > 0 && (
          <div className="flex items-center justify-end px-md py-1 bg-neutral-50">
            <button
              className="flex items-center gap-xs text-caption text-primary-600 font-medium"
              onClick={() => setPreview(true)}
            >
              <Eye size={14} /> 预览
            </button>
          </div>
        )}
        <textarea
          ref={ref}
          className="flex-1 w-full p-md text-body bg-white focus:outline-none resize-none font-sans leading-relaxed placeholder:text-neutral-400"
          style={{ minHeight: "60vh", paddingBottom: "60px" }}
          value={value}
          onChange={handleChange}
          placeholder={placeholder ?? "开始编辑…"}
          readOnly={readOnly}
          onFocus={onFocus}
          onBlur={onBlur}
          autoCapitalize="sentences"
          autoCorrect="on"
          spellCheck
        />
      </div>
    );
  }
);

export default MobileEditor;
