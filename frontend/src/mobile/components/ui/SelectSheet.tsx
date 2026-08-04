import React from "react";
import { Check } from "lucide-react";
import BottomSheet from "./BottomSheet";

interface SelectOption {
  value: string;
  label: string;
  description?: string;
}

interface SelectSheetProps {
  open: boolean;
  label?: string;
  required?: boolean;
  onClose: () => void;
  placeholder?: string;
  options: SelectOption[];
  value: string | null;
  onChange: (value: string) => void;
  title?: string;
}

export default function SelectSheet({
  label,
  required,
  open,
  placeholder,
  onClose,
  options,
  value,
  onChange,
  title,
}: SelectSheetProps) {
  return (
    <BottomSheet open={open} onClose={onClose} height="60%">
      <div className="px-md pt-md pb-sm">
        {label && <span className="text-body-sm text-neutral-600">{label}{required && <span className="text-danger"> *</span>}</span>}
        {title && <h2 className="text-h3 text-neutral-900 text-center">
          {title}
        </h2>}
      </div>
      <div className="divide-y divide-neutral-100">
        {options.map((opt) => {
          const isSelected = opt.value === value;
          return (
            <button
              key={opt.value}
              onClick={() => {
                onChange(opt.value);
                onClose();
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
  );
}
