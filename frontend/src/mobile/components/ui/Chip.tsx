import React from "react";
import { X } from "lucide-react";

type ChipVariant = "default" | "selected";

interface ChipProps {
  variant?: ChipVariant;
  children?: React.ReactNode;
  label?: string;
  selected?: boolean;
  icon?: React.ReactNode;
  onRemove?: () => void;
  onClick?: () => void;
  className?: string;
}

const variantClasses: Record<ChipVariant, string> = {
  default: "bg-neutral-100 text-neutral-600",
  selected: "bg-primary-50 text-primary-600 border border-primary-500",
};

export default function Chip({
  children,
  label,
  selected,
  variant = "default",
  icon,
  onRemove,
  onClick,
  className = "",
}: ChipProps) {
  const resolvedVariant: ChipVariant = selected ? "selected" : variant;
  return (
    <span
      className={`inline-flex items-center h-8 px-3 rounded-full text-body-sm font-medium gap-1.5 select-none ${
        onClick ? "cursor-pointer active:scale-95" : ""
      } ${variantClasses[resolvedVariant]} ${className}`}
      onClick={onClick}
    >
      {icon && <span className="shrink-0">{icon}</span>}
      <span>{children || label}</span>
      {onRemove && (
        <button
          onClick={(e) => {
            e.stopPropagation();
            onRemove();
          }}
          className="shrink-0 ml-0.5 w-5 h-5 flex items-center justify-center rounded-full text-neutral-400 hover:text-neutral-600 hover:bg-neutral-200"
        >
          <X size={12} />
        </button>
      )}
    </span>
  );
}
