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
  onClose: () => void;
  options: SelectOption[];
  value: string | null;
  onChange: (value: string) => void;
  title?: string;
}

export default function SelectSheet({
  open,
  onClose,
  options,
  value,
  onChange,
  title,
}: SelectSheetProps) {
  return (
    <BottomSheet open={open} onClose={onClose} height="60%">
      {title && (
        <h2 className="text-h3 text-neutral-900 text-center px-md pt-md pb-sm">
          {title}
        </h2>
      )}
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
