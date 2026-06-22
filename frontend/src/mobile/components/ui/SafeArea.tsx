import React from "react";

type SafeAreaEdge = "top" | "bottom" | "both";

interface SafeAreaProps {
  edge?: SafeAreaEdge;
  children: React.ReactNode;
  className?: string;
}

export default function SafeArea({
  edge = "both",
  children,
  className = "",
}: SafeAreaProps) {
  const paddingClasses = [
    (edge === "top" || edge === "both") && "pt-[env(safe-area-inset-top,0px)]",
    (edge === "bottom" || edge === "both") &&
      "pb-[env(safe-area-inset-bottom,0px)]",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div className={`${paddingClasses} ${className}`}>
      {children}
    </div>
  );
}
