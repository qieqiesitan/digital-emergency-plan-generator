import React from "react";
import Badge from "./Badge";

interface TabItem {
  key: string;
  icon: React.ReactNode;
  activeIcon?: React.ReactNode;
  label: string;
  badge?: number;
}

interface TabBarProps {
  items: TabItem[];
  activeKey: string;
  onChange: (key: string) => void;
}

export default function TabBar({ items, activeKey, onChange }: TabBarProps) {
  return (
    <nav
      className="fixed bottom-0 left-0 right-0 z-40 flex border-t border-neutral-100"
      style={{
        height: "var(--tabbar-height)",
        paddingBottom: "var(--safe-bottom)",
        background: "rgba(255,255,255,0.85)",
        backdropFilter: "blur(20px)",
        WebkitBackdropFilter: "blur(20px)",
      }}
    >
      {items.map((item) => {
        const isActive = item.key === activeKey;
        return (
          <button
            key={item.key}
            onClick={() => onChange(item.key)}
            className="flex-1 flex flex-col items-center justify-center gap-0.5 relative"
          >
            {isActive && (
              <span className="absolute top-0 left-1/2 -translate-x-1/2 w-8 h-0.5 bg-primary-600 rounded-full" />
            )}
            <span className="relative">
              {isActive && item.activeIcon ? item.activeIcon : item.icon}
              {item.badge !== undefined && item.badge > 0 && (
                <span className="absolute -top-1 -right-2">
                  <Badge count={item.badge} />
                </span>
              )}
            </span>
            <span
              className={`text-[10px] font-medium leading-none ${
                isActive ? "text-primary-600" : "text-neutral-400"
              }`}
            >
              {item.label}
            </span>
          </button>
        );
      })}
    </nav>
  );
}
