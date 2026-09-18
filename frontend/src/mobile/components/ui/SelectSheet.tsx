import { useState } from "react";
import { Check, ChevronDown } from "lucide-react";
import BottomSheet from "./BottomSheet";

interface SelectOption {
  value: string;
  label: string;
  description?: string;
}

interface SelectSheetProps {
  label?: string;
  required?: boolean;
  placeholder?: string;
  options: SelectOption[];
  value: string | null;
  onChange: (value: string) => void;
  title?: string;
  error?: string;
  className?: string;
}

export default function SelectSheet({
  label,
  required,
  placeholder,
  options,
  value,
  onChange,
  title,
  error,
  className = "",
}: SelectSheetProps) {
  const [open, setOpen] = useState(false);
  const selected = options.find((opt) => opt.value === value) ?? null;

  const borderClass = error
    ? "border-[2px] border-danger"
    : "border border-neutral-100";

  return (
    <div className={className}>
      {label && (
        <label className="block text-body-sm text-neutral-600 mb-2 font-medium">
          {label}
          {required && <span className="text-danger"> *</span>}
        </label>
      )}
      {/* 触发器：未选择时显示 placeholder 作为占位值 */}
      <button
        type="button"
        onClick={() => setOpen(true)}
        className={`w-full h-[52px] px-4 flex items-center justify-between gap-2 rounded-sm bg-white ${borderClass}`}
      >
        <span
          className={`flex-1 text-left truncate text-body ${
            selected ? "text-neutral-900" : "text-neutral-400"
          }`}
        >
          {selected ? selected.label : (placeholder || "请选择")}
        </span>
        <ChevronDown size={18} className="shrink-0 text-neutral-400" />
      </button>
      {error && (
        <p className="text-caption text-danger mt-1 ml-1">{error}</p>
      )}

      <BottomSheet open={open} onClose={() => setOpen(false)} height="60%">
      <div className="px-md pt-md pb-sm">
        {(title || label) && (
          <h2 className="text-h3 text-neutral-900 text-center">{title || label}</h2>
        )}
      </div>
      <div className="divide-y divide-neutral-100">
        {options.map((opt) => {
          const isSelected = opt.value === value;
          return (
            <button
              key={opt.value}
              type="button"
              onClick={() => {
                onChange(opt.value);
                setOpen(false);
              }}
              className={`w-full flex items-center h-[52px] px-md text-left ${
                isSelected ? "bg-primary-50" : ""
              }`}
            >
              <div className="flex-1">
                <span
                  className={`text-body ${
                    isSelected
                      ? "text-primary-600 font-semibold"
                      : "text-neutral-900"
                  }`}
                >
                  {opt.label}
                </span>
                {opt.description && (
                  <p className="text-caption text-neutral-400">
                    {opt.description}
                  </p>
                )}
              </div>
              {isSelected && (
                <Check size={20} className="text-primary-600 shrink-0" />
              )}
            </button>
          );
        })}
      </div>
    </BottomSheet>
    </div>
  );
}
