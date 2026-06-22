import React from "react";
import Button from "./Button";

interface EmptyStateProps {
  icon?: React.ReactNode;
  title: string;
  description?: string;
  action?: {
    label: string;
    onPress: () => void;
  };
  className?: string;
}

export default function EmptyState({
  icon,
  title,
  description,
  action,
  className = "",
}: EmptyStateProps) {
  return (
    <div
      className={`flex flex-col items-center justify-center py-xl px-md text-center ${className}`}
    >
      {icon && (
        <div className="text-neutral-300 mb-md">{icon}</div>
      )}
      <h3 className="text-h3 text-neutral-900 mb-sm">{title}</h3>
      {description && (
        <p className="text-body-sm text-neutral-400 mb-md max-w-[280px]">
          {description}
        </p>
      )}
      {action && (
        <Button variant="primary" size="md" onClick={action.onPress}>
          {action.label}
        </Button>
      )}
    </div>
  );
}
