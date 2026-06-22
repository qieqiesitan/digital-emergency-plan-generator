import React from "react";

type SkeletonVariant = "text" | "circle" | "card" | "list-item";

interface SkeletonProps {
  variant?: SkeletonVariant;
  width?: string | number;
  height?: string | number;
  count?: number;
  className?: string;
}

function SkeletonItem({
  variant = "text",
  width,
  height,
  className = "",
}: SkeletonProps) {
  const base = "bg-neutral-100 animate-skeleton-pulse";

  switch (variant) {
    case "circle":
      return (
        <div
          className={`${base} rounded-full ${className}`}
          style={{ width: width ?? 44, height: height ?? 44 }}
        />
      );
    case "card":
      return (
        <div
          className={`${base} rounded-md ${className}`}
          style={{ width: width ?? "100%", height: height ?? 96 }}
        />
      );
    case "list-item":
      return (
        <div className={`flex items-center gap-md ${className}`}>
          <SkeletonItem variant="circle" width={44} height={44} />
          <div className="flex-1 space-y-sm">
            <SkeletonItem variant="text" width="60%" height={16} />
            <SkeletonItem variant="text" width="40%" height={12} />
          </div>
        </div>
      );
    case "text":
    default:
      return (
        <div
          className={`${base} rounded-sm ${className}`}
          style={{ width: width ?? "100%", height: height ?? 14 }}
        />
      );
  }
}

export default function Skeleton({ count = 1, ...props }: SkeletonProps) {
  if (count <= 1) return <SkeletonItem {...props} />;

  return (
    <div className="space-y-md">
      {Array.from({ length: count }, (_, i) => (
        <SkeletonItem key={i} {...props} />
      ))}
    </div>
  );
}
