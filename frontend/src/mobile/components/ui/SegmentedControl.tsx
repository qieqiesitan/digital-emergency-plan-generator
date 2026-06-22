import React from "react";
import { motion } from "framer-motion";

interface SegmentedControlProps {
  options: Array<{ value: string; label: string }>;
  value: string;
  onChange: (value: string) => void;
  className?: string;
}

export default function SegmentedControl({
  options,
  value,
  onChange,
  className = "",
}: SegmentedControlProps) {
  return (
    <div
      className={`inline-flex bg-neutral-100 rounded-md p-0.5 ${className}`}
    >
      {options.map((opt) => {
        const isActive = opt.value === value;
        return (
          <button
            key={opt.value}
            onClick={() => onChange(opt.value)}
            className="relative flex-1 h-8 px-3 rounded-sm text-body-sm font-medium select-none"
          >
            {isActive && (
              <motion.div
                layoutId="segmented-bg"
                className="absolute inset-0 bg-white rounded-sm shadow-card"
                transition={{ type: "spring", duration: 0.2 }}
              />
            )}
            <span
              className={`relative z-10 ${
                isActive ? "text-primary-600 font-semibold" : "text-neutral-600"
              }`}
            >
              {opt.label}
            </span>
          </button>
        );
      })}
    </div>
  );
}
