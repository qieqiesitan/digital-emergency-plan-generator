import React from "react";

interface ProgressBarProps {
  value?: number;
  percent?: number;
  indeterminate?: boolean;
  size?: "sm" | "md";
  color?: string;
  className?: string;
}

export default function ProgressBar({
  value,
  percent,
  indeterminate = false,
  size = "md",
  color = "var(--color-primary-600)",
  className = "",
}: ProgressBarProps) {
  const resolvedValue = percent ?? value ?? 0;
  const h = size === "sm" ? "h-0.5" : "h-1";

  if (indeterminate) {
    return (
      <div className={`w-full ${h} bg-neutral-100 rounded-full overflow-hidden ${className}`}>
        <div
          className="h-full rounded-full animate-[indeterminate_1.5s_ease-in-out_infinite]"
          style={{ width: "33%", backgroundColor: color }}
        />
      </div>
    );
  }

  const pct = Math.min(100, Math.max(0, resolvedValue));

  return (
    <div className={`w-full ${h} bg-neutral-100 rounded-full overflow-hidden ${className}`}>
      <div
        className="h-full rounded-full transition-all duration-300"
        style={{ width: `${pct}%`, backgroundColor: color }}
      />
    </div>
  );
}
