import React from "react";
import { ChevronRight, FileText, Target, Factory } from "lucide-react";
import Badge from "@/mobile/components/ui/Badge";
import type { PlanType } from "@/types/plan";

const PLAN_TYPE_ICONS: Record<string, React.ReactNode> = {
  comprehensive: <FileText size={16} />,
  special: <Target size={16} />,
  onsite: <Factory size={16} />,
};

const PLAN_TYPE_COLORS: Record<string, "info" | "warning" | "success"> = {
  comprehensive: "info",
  special: "warning",
  onsite: "success",
};

const PLAN_TYPE_LABELS: Record<string, string> = {
  comprehensive: "综合",
  special: "专项",
  onsite: "现场",
};

interface PlanCardProps {
  id: string;
  title: string;
  planType: PlanType | string;
  status: string;
  enterpriseName?: string;
  updatedAt?: string;
  accidentType?: string;
  onPress: () => void;
}

export default function PlanCard({
  title,
  planType,
  status,
  enterpriseName,
  updatedAt,
  accidentType,
  onPress,
}: PlanCardProps) {
  const typeVar = PLAN_TYPE_COLORS[planType] ?? "default";
  const typeLabel = PLAN_TYPE_LABELS[planType] ?? planType;
  const typeIcon = PLAN_TYPE_ICONS[planType] ?? <FileText size={16} />;

  const statusLabel =
    status === "completed" ? "已完成" :
    status === "generating" ? "生成中" : "草稿";
  const statusVar =
    status === "completed" ? "success" :
    status === "generating" ? "info" : "default";

  return (
    <button
      className="w-full text-left bg-white rounded-md shadow-card p-md active:bg-neutral-50 transition-colors"
      onClick={onPress}
    >
      <div className="flex items-start gap-md">
        {/* 类型图标 */}
        <div className="w-10 h-10 rounded-full bg-primary-50 flex items-center justify-center text-primary-600 shrink-0 mt-0.5">
          {typeIcon}
        </div>

        {/* 内容 */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-xs mb-1">
            <Badge variant={typeVar}>{typeLabel}</Badge>
            <Badge variant={statusVar}>{statusLabel}</Badge>
          </div>
          <p className="text-h3 font-semibold text-neutral-900 truncate">{title}</p>
          {accidentType && (
            <p className="text-caption text-neutral-400 mt-0.5">事故类型：{accidentType}</p>
          )}
          <div className="flex items-center gap-xs mt-1.5 text-caption text-neutral-400">
            {enterpriseName && <span>{enterpriseName}</span>}
            {enterpriseName && updatedAt && <span>·</span>}
            {updatedAt && <span>{updatedAt}</span>}
          </div>
        </div>

        {/* 箭头 */}
        <ChevronRight size={16} className="text-neutral-400 shrink-0 mt-1" />
      </div>
    </button>
  );
}
