import React, { useState } from "react";
import { Sparkles, ChevronDown, ChevronUp } from "lucide-react";
import BottomSheet from "@/mobile/components/ui/BottomSheet";
import SegmentedControl from "@/mobile/components/ui/SegmentedControl";



// 风格参数类型（与Web端StylePanel对齐）
interface MobileStyleParams {
  formality: "formal" | "standard" | "practical";
  detail_level: "concise" | "balanced" | "comprehensive";
  table_preference: "minimal" | "moderate" | "heavy";
  diagram_preference: "none" | "mermaid";
}

const DEFAULT_MOBILE_STYLE: MobileStyleParams = {
  formality: "standard",
  detail_level: "balanced",
  table_preference: "moderate",
  diagram_preference: "mermaid",
};

interface AIGenerationSheetProps {
  open: boolean;
  onClose: () => void;
  mode: "single" | "batch";
  planId: string;
  sectionName?: string;
  enterpriseName: string;
  contextSummary: {
    riskCount: number;
    resourceCount: number;
  };
  chapters?: Array<{
    key: string;
    name: string;
    aiGeneratable: boolean;
  }>;
  onGenerate: (selectedChapters: string[], styleParams: MobileStyleParams) => void;
}

export default function AIGenerationSheet({
  open,
  onClose,
  mode,
  planId,
  sectionName,
  enterpriseName,
  contextSummary,
  chapters = [],
  onGenerate,
}: AIGenerationSheetProps) {
  const [selectedChapters, setSelectedChapters] = useState<string[]>(
    chapters.filter(c => c.aiGeneratable).map(c => c.key)
  );
  const [contextExpanded, setContextExpanded] = useState(false);
  const [style, setStyle] = useState("standard");

  const toggledChapter = (key: string) => {
    setSelectedChapters(prev =>
      prev.includes(key)
        ? prev.filter(k => k !== key)
        : [...prev, key]
    );
  };

  const handleGenerate = () => {
    onClose();
    onGenerate(mode === "single" && sectionName ? [chapters[0]?.key ?? ""] : selectedChapters);
  };

  return (
    <BottomSheet open={open} onClose={onClose} height="70%">
      <div className="p-md space-y-md">
        {/* 标题 */}
        <div className="flex items-center gap-sm">
          <Sparkles size={22} className="text-indigo-600" />
          <span className="text-h2">AI 智能生成</span>
        </div>

        {/* 上下文卡片 */}
        <div className="bg-neutral-50 rounded-md p-md">
          <div
            className="flex items-center justify-between cursor-pointer"
            onClick={() => setContextExpanded(!contextExpanded)}
          >
            <span className="text-body-sm font-semibold text-neutral-700">📊 将使用的上下文</span>
            {contextExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
          </div>
          <div className="text-caption text-neutral-500 mt-1">
            企业：{enterpriseName}
          </div>
          {contextExpanded && (
            <div className="mt-2 space-y-1 text-caption text-neutral-500">
              <p>风险源数量：{contextSummary.riskCount} 个</p>
              <p>应急资源数量：{contextSummary.resourceCount} 个</p>
              <p>预案 ID：{planId}</p>
            </div>
          )}
        </div>

        {/* 生成风格 */}
        <div>
          <p className="text-body-sm font-semibold text-neutral-700 mb-2">生成风格（可选）</p>
          <SegmentedControl
            segments={[
              { key: "standard", label: "标准化" },
              { key: "detailed", label: "详细" },
              { key: "concise", label: "简洁" },
            ]}
            activeKey={style}
            onChange={setStyle}
          />
        </div>

        {/* batch 模式章节选择 */}
        {mode === "batch" && (
          <div>
            <p className="text-body-sm font-semibold text-neutral-700 mb-2">选择章节</p>
            <div className="space-y-1 max-h-48 overflow-y-auto">
              {chapters.map(ch => (
                <label
                  key={ch.key}
                  className="flex items-center gap-sm px-sm py-2 rounded-md active:bg-neutral-50"
                >
                  <input
                    type="checkbox"
                    checked={selectedChapters.includes(ch.key)}
                    onChange={() => toggledChapter(ch.key)}
                    className="w-4 h-4"
                  />
                  <span className="text-body text-neutral-900">{ch.name}</span>
                </label>
              ))}
            </div>
          </div>
        )}

        {/* 开始生成 */}
        <button
          className="w-full h-12 bg-indigo-600 text-white rounded-md font-semibold text-body flex items-center justify-center gap-sm hover:bg-indigo-700 active:scale-[0.99] transition-transform"
          onClick={handleGenerate}
        >
          <Sparkles size={20} />
          开始生成
        </button>
      </div>
    </BottomSheet>
  );
}
