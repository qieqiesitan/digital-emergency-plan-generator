import React from "react";
import { Loader2 } from "lucide-react";

type ButtonVariant = "primary" | "secondary" | "danger" | "ghost";
type ButtonSize = "sm" | "md" | "lg";

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
  icon?: React.ReactNode;
  fullWidth?: boolean;
}

const variantClasses: Record<ButtonVariant, string> = {
  primary:
    "bg-primary-600 text-white hover:brightness-90 active:scale-[0.98] disabled:opacity-40",
  secondary:
    "bg-white text-primary-600 border border-primary-500 hover:bg-primary-50 active:scale-[0.98] disabled:opacity-40",
  danger:
    "bg-danger text-white hover:brightness-90 active:scale-[0.98] disabled:opacity-40",
  ghost:
    "bg-transparent text-primary-600 hover:bg-primary-50 active:scale-[0.98] disabled:opacity-40",
};

const sizeClasses: Record<ButtonSize, string> = {
  sm: "h-9 px-3 text-body-sm rounded-sm gap-1.5",
  md: "h-11 px-4 text-body rounded-sm gap-2",
  lg: "h-[52px] px-5 text-body rounded-sm gap-2",
};

export default function Button({
  variant = "primary",
  size = "md",
  loading = false,
  icon,
  fullWidth = false,
  children,
  className = "",
  disabled,
  ...props
}: ButtonProps) {
  return (
    <button
      className={[
        "inline-flex items-center justify-center font-semibold transition-all duration-150 select-none",
        variantClasses[variant],
        sizeClasses[size],
        fullWidth ? "w-full" : "",
        className,
      ].join(" ")}
      disabled={disabled || loading}
      {...props}
    >
      {loading ? (
        <Loader2
          size={size === "sm" ? 14 : size === "md" ? 18 : 20}
          className="animate-spin shrink-0"
        />
      ) : icon ? (
        <span className="shrink-0">{icon}</span>
      ) : null}
      {children && <span>{children}</span>}
    </button>
  );
}
