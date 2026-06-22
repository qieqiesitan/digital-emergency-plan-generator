import React, { useState } from "react";
import { Eye, EyeOff } from "lucide-react";

type InputType = "text" | "email" | "password" | "number" | "tel" | "search";

interface InputProps
  extends Omit<React.InputHTMLAttributes<HTMLInputElement>, "size"> {
  label?: string;
  error?: string;
  hint?: string;
  prefixIcon?: React.ReactNode;
  suffixIcon?: React.ReactNode;
  showPasswordToggle?: boolean;
  fullWidth?: boolean;
}

export default function Input({
  label,
  error,
  hint,
  prefixIcon,
  suffixIcon,
  showPasswordToggle = false,
  fullWidth = false,
  className = "",
  type = "text",
  ...props
}: InputProps) {
  const [showPassword, setShowPassword] = useState(false);
  const resolvedType =
    type === "password" && showPassword ? "text" : type;

  const borderClass = error
    ? "border-[2px] border-danger"
    : "border border-neutral-100 focus-within:border-[2px] focus-within:border-primary-500";

  return (
    <div className={fullWidth ? "w-full" : ""}>
      {label && (
        <label className="block text-body-sm text-neutral-600 mb-2 font-medium">
          {label}
        </label>
      )}
      <div
        className={[
          "flex items-center h-[52px] rounded-sm bg-white overflow-hidden transition-colors duration-150",
          borderClass,
          props.disabled ? "bg-neutral-50" : "",
          className,
        ].join(" ")}
      >
        {prefixIcon && (
          <span className="shrink-0 text-neutral-400 ml-4">{prefixIcon}</span>
        )}
        <input
          type={resolvedType}
          className="flex-1 h-full px-4 bg-transparent text-body text-neutral-900 placeholder:text-neutral-400 outline-none disabled:text-neutral-400"
          {...props}
        />
        {showPasswordToggle && type === "password" && (
          <button
            type="button"
            onClick={() => setShowPassword(!showPassword)}
            className="shrink-0 w-11 h-11 flex items-center justify-center text-neutral-400 hover:text-neutral-600"
            tabIndex={-1}
          >
            {showPassword ? <EyeOff size={20} /> : <Eye size={20} />}
          </button>
        )}
        {suffixIcon && !showPasswordToggle && (
          <span className="shrink-0 text-neutral-400 mr-4">{suffixIcon}</span>
        )}
      </div>
      {error && (
        <p className="text-caption text-danger mt-1 ml-1">{error}</p>
      )}
      {hint && !error && (
        <p className="text-caption text-neutral-400 mt-1 ml-1">{hint}</p>
      )}
    </div>
  );
}
