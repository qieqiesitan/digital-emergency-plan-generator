import React from "react";
import { ChevronRight, Building2, Trash2 } from "lucide-react";
import { motion } from "framer-motion";
import Badge from "@/mobile/components/ui/Badge";

interface EnterpriseCardProps {
  enterprise: {
    id: string;
    name: string;
    industry?: string;
    address?: string;
    plans_count?: number;
  };
  onPress: () => void;
  onDelete?: () => void;
}

export default function EnterpriseCard({
  enterprise,
  onPress,
  onDelete,
}: EnterpriseCardProps) {
  const [swiped, setSwiped] = React.useState(false);
  const constraintsRef = React.useRef<HTMLDivElement>(null);

  return (
    <div className="relative overflow-hidden rounded-md" ref={constraintsRef}>
      {/* 左滑删除按钮 */}
      <div className="absolute right-0 top-0 bottom-0 flex items-stretch">
        <button
          className="bg-red-500 text-white px-4 flex items-center justify-center min-w-[72px] font-medium text-body"
          onClick={(e) => {
            e.stopPropagation();
            onDelete?.();
            setSwiped(false);
          }}
        >
          <Trash2 size={18} className="mr-1" />
          删除
        </button>
      </div>

      {/* 卡片主体 */}
      <motion.div
        drag={onDelete ? "x" : undefined}
        dragConstraints={{ left: -80, right: 0 }}
        dragElastic={0.1}
        onDragEnd={(_, info) => {
          if (info.offset.x < -40) setSwiped(true);
          else setSwiped(false);
        }}
        animate={{ x: swiped ? -80 : 0 }}
        className="relative bg-white shadow-card"
      >
        <button
          className="flex items-center w-full px-md py-3 gap-md text-left"
          onClick={onPress}
        >
          <div className="w-11 h-11 rounded-full bg-primary-50 flex items-center justify-center text-primary-600 font-semibold text-body shrink-0">
            {enterprise.name.charAt(0)}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-h3 font-semibold text-neutral-900 truncate">
              {enterprise.name}
            </p>
            <p className="text-caption text-neutral-400 mt-0.5 truncate">
              {[enterprise.industry, enterprise.address]
                .filter(Boolean)
                .join(" · ")}
            </p>
          </div>
          {enterprise.plans_count !== undefined && enterprise.plans_count > 0 && (
            <Badge variant="info">{enterprise.plans_count}个预案</Badge>
          )}
          <ChevronRight size={16} className="text-neutral-400 shrink-0" />
        </button>
      </motion.div>
    </div>
  );
}
