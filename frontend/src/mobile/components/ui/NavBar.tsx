import React from "react";
import { ArrowLeft } from "lucide-react";

interface NavBarAction {
  icon: React.ReactNode;
  onPress: () => void;
  label?: string;
}

interface NavBarProps {
  title: string;
  showBack?: boolean;
  onBack?: () => void;
  rightActions?: NavBarAction[];
  largeTitle?: boolean;
  border?: boolean;
}

export default function NavBar({
  title,
  showBack = false,
  onBack,
  rightActions = [],
  largeTitle = false,
  border = true,
}: NavBarProps) {
  if (largeTitle) {
    return (
      <div
        className={`bg-white ${border ? "border-b border-neutral-100" : ""}`}
        style={{ paddingTop: "var(--safe-top)" }}
      >
        <div className="flex items-center justify-between h-11 px-md">
          <div className="w-11" />
          <span className="text-h3 font-semibold text-neutral-900 truncate">
            {title}
          </span>
          <div className="w-11 flex justify-end">
            {rightActions.length > 0 && (
              <button
                onClick={rightActions[0].onPress}
                className="w-11 h-11 flex items-center justify-center text-primary-600"
                aria-label={rightActions[0].label}
              >
                {rightActions[0].icon}
              </button>
            )}
          </div>
        </div>
        <div className="px-md pb-md">
          <h1 className="text-display text-neutral-900">{title}</h1>
        </div>
      </div>
    );
  }

  return (
    <div
      className={`bg-white ${border ? "border-b border-neutral-100" : ""}`}
      style={{ paddingTop: "var(--safe-top)" }}
    >
      <div className="flex items-center h-11 px-md">
        {/* 左侧 */}
        <div className="w-11">
          {showBack && (
            <button
              onClick={onBack}
              className="w-11 h-11 flex items-center justify-center -ml-2 text-neutral-900"
              aria-label="返回"
            >
              <ArrowLeft size={24} />
            </button>
          )}
        </div>

        {/* 标题 */}
        <span className="flex-1 text-center text-h3 font-semibold text-neutral-900 truncate">
          {title}
        </span>

        {/* 右侧操作 */}
        <div className="w-11 flex justify-end gap-xs">
          {rightActions.slice(0, 2).map((action, i) => (
            <button
              key={i}
              onClick={action.onPress}
              className="w-11 h-11 flex items-center justify-center text-primary-600"
              aria-label={action.label}
            >
              {action.icon}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
