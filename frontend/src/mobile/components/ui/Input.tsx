import React, { useState } from "react";
import { Eye, EyeOff } from "lucide-react";

type InputType = "text" | "email" | "password" | "number" | "tel" | "search";

interface InputProps
  extends Omit<React.InputHTMLAttributes<HTMLInputElement>, "size" | "onChange" | "value"> {
  label?: string;
  error?: string;
  hint?: string;
  multiline?: boolean;
  suffix?: string;
  value?: string;
  onChange?: (v: string) => void;
  prefixIcon?: React.ReactNode;
  suffixIcon?: React.ReactNode;
  showPasswordToggle?: boolean;
  fullWidth?: boolean;
}

export default function Input({
  label,
  error,
  hint,
  multiline,
  suffix,
  value,
  onChange,
  prefixIcon,
  suffixIcon,
  showPasswordToggle = false,
  fullWidth = false,
  className = "",
  type = "text",
  placeholder,
  disabled,
  ...props
}: InputProps) {
  const [showPassword, setShowPassword] = useState(false);
  const resolvedType =
    type === "password" && showPassword ? "text" : type;

  const borderClass = error
    ? "border-[2px] border-danger"
    : "border border-neutral-100 focus-within:border-[2px] focus-within:border-primary-500";

  const inputOnChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    onChange?.(e.target.value);
  };

  return (
    <div className={fullWidth ? "w-full" : ""}>
      {label && (
        <label className="block text-body-sm text-neutral-600 mb-2 font-medium">
          {label}
        </label>
      )}
      <div
        className={`flex items-center ${multiline ? 'min-h-[52px]' : 'h-[52px]'} rounded-sm bg-white overflow-hidden transition-colors duration-150 ${borderClass} ${disabled ? "bg-neutral-50" : ""} ${className}`}
      >
        {prefixIcon && (
          <span className="shrink-0 text-neutral-400 ml-4">{prefixIcon}</span>
        )}
        {suffix && <span className="shrink-0 text-neutral-400 mr-4">{suffix}</span>}
        {multiline ? (
          <textarea
            value={value}
            onChange={(e) => onChange?.(e.target.value)}
            className="flex-1 min-h-[80px] px-4 py-3 bg-transparent text-body text-neutral-900 placeholder:text-neutral-400 outline-none resize-none disabled:text-neutral-400"
            placeholder={placeholder as string}
            disabled={disabled}
          />
        ) : (
          <input
            type={resolvedType}
            value={value}
            onChange={inputOnChange}
            className="flex-1 h-full px-4 bg-transparent text-body text-neutral-900 placeholder:text-neutral-400 outline-none disabled:text-neutral-400"
            placeholder={placeholder as string}
            disabled={disabled}
          />
        )}
        {suffixIcon && !showPasswordToggle && !suffix && (
          <span className="shrink-0 text-neutral-400 mr-4">{suffixIcon}</span>
        )}
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
