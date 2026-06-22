import React from "react";

interface CardProps {
  children: React.ReactNode;
  pressable?: boolean;
  selected?: boolean;
  className?: string;
  onClick?: () => void;
}

export default function Card({
  children,
  pressable = false,
  selected = false,
  className = "",
  onClick,
}: CardProps) {
  const base = "bg-white rounded-md shadow-card p-md";

  const stateClasses = [
    pressable && "cursor-pointer active:scale-[0.99] active:brightness-[0.98]",
    selected && "border-2 border-primary-500 bg-primary-50",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div
      className={`${base} ${stateClasses} ${className}`}
      onClick={onClick}
      role={pressable ? "button" : undefined}
      tabIndex={pressable ? 0 : undefined}
    >
      {children}
    </div>
  );
}
