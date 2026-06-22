import React, { useState, useMemo } from "react";
import {
  ChevronRight, CheckCircle, Circle,
  Sparkles, AlertCircle, GitBranch, Download,
} from "lucide-react";

export interface ChapterNode {
  key: string;
  title: string;
  level: number;
  aiGeneratable: boolean;
  required: boolean;
  children?: ChapterNode[];
}

interface ChapterTreeProps {
  chapters: ChapterNode[];
  sectionStates: Record<string, {
    hasContent: boolean;
    aiGenerated: boolean;
  }>;
  selectedKey: string | null;
  onSelect: (chapter: ChapterNode) => void;
}

function ChapterRow({
  chapter,
  depth,
  state,
  isSelected,
  onSelect,
}: {
  chapter: ChapterNode;
  depth: number;
  state: { hasContent: boolean; aiGenerated: boolean } | undefined;
  isSelected: boolean;
  onSelect: (c: ChapterNode) => void;
}) {
  const [expanded, setExpanded] = useState(true);
  const hasChildren = chapter.children && chapter.children.length > 0;

  let StatusIcon = Circle as React.FC<{ size?: number; className?: string }>;
  let statusClass = "text-neutral-300";
  let statusSize = 18;

  if (state?.hasContent) {
    StatusIcon = CheckCircle;
    statusClass = "text-green-500";
  } else if (state?.aiGenerated) {
    StatusIcon = Sparkles;
    statusClass = "text-blue-500";
  } else if (chapter.required) {
    StatusIcon = AlertCircle;
    statusClass = "text-amber-500";
  }

  return (
    <>
      <button
        className={`flex items-center w-full h-12 px-md text-left active:bg-neutral-50 ${
          isSelected ? "bg-primary-50" : ""
        }`}
        style={{ paddingLeft: `${12 + depth * 16}px` }}
        onClick={() => {
          if (hasChildren) {
            setExpanded(!expanded);
          } else {
            onSelect(chapter);
          }
        }}
      >
        {/* 折叠箭头 */}
        <span className="w-5 shrink-0">
          {hasChildren && (
            <ChevronRight
              size={16}
              className={`text-neutral-400 transition-transform ${expanded ? "rotate-90" : ""}`}
            />
          )}
        </span>

        {/* 标题 */}
        <span className={`flex-1 text-body text-neutral-900 truncate ${
          !hasChildren ? "cursor-pointer" : ""
        }`}>
          {chapter.title}
        </span>

        {/* 状态图标 */}
        <span className="shrink-0 ml-sm">
          <StatusIcon size={statusSize} className={statusClass} />
        </span>
      </button>

      {/* 子章节 */}
      {hasChildren && expanded && chapter.children!.map(child => (
        <ChapterRow
          key={child.key}
          chapter={child}
          depth={depth + 1}
          state={sectionStates[child.key]}
          isSelected={selectedKey === child.key}
          onSelect={onSelect}
        />
      ))}
    </>
  );
}

export default function ChapterTree({
  chapters,
  sectionStates,
  selectedKey,
  onSelect,
}: ChapterTreeProps) {
  return (
    <div className="flex flex-col">
      {chapters.map(chapter => (
        <ChapterRow
          key={chapter.key}
          chapter={chapter}
          depth={0}
          state={sectionStates[chapter.key]}
          isSelected={selectedKey === chapter.key}
          onSelect={onSelect}
        />
      ))}
    </div>
  );
}
