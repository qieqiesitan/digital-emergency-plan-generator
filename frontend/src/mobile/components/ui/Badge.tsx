import React from "react";

type BadgeVariant = "default" | "success" | "warning" | "danger" | "info";

interface BadgeProps {
  variant?: BadgeVariant;
  children?: React.ReactNode;
  dot?: boolean;
  count?: number;
  className?: string;
}

const variantClasses: Record<BadgeVariant, string> = {
  default: "bg-neutral-100 text-neutral-600",
  success: "bg-green-100 text-green-800",
  warning: "bg-amber-100 text-amber-800",
  danger: "bg-red-100 text-red-800",
  info: "bg-indigo-100 text-indigo-800",
};

export default function Badge({
  variant = "default",
  children,
  dot = false,
  count,
  className = "",
}: BadgeProps) {
  // 圆点模式
  if (dot) {
    return (
      <span
        className={`inline-block w-2 h-2 rounded-full ${variantClasses[variant].split(" ")[0]} ${className}`}
      />
    );
  }

  // 数字模式
  if (count !== undefined) {
    return (
      <span
        className={`inline-flex items-center justify-center min-w-[16px] h-4 px-1 rounded-full bg-danger text-white text-[10px] font-semibold leading-none ${className}`}
      >
        {count > 99 ? "99+" : count}
      </span>
    );
  }

  // 标签模式
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded-full text-caption font-medium ${variantClasses[variant]} ${className}`}
    >
      {children}
    </span>
  );
}
