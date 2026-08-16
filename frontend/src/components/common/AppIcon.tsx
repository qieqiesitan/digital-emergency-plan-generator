import type { CSSProperties } from "react";
import { ICONS, type AppIconName } from "./icons";

export interface AppIconProps {
  name: AppIconName;
  size?: number;
  className?: string;
  style?: CSSProperties;
}

export default function AppIcon({ name, size = 16, className, style }: AppIconProps) {
  const icon = ICONS[name];
  if (!icon) {
    if (import.meta.env.DEV) {
      console.warn(`[AppIcon] unknown icon name: ${String(name)}`);
    }
    return null;
  }
  return (
    <svg
      className={className}
      style={style}
      width={size}
      height={size}
      viewBox={icon.viewBox}
      fill="currentColor"
      aria-hidden="true"
      focusable="false"
    >
      {icon.body}
    </svg>
  );
}
