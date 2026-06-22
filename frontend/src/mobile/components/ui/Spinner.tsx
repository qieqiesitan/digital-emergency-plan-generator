import { Loader2 } from "lucide-react";

type SpinnerSize = "sm" | "md" | "lg";

interface SpinnerProps {
  size?: SpinnerSize;
  color?: string;
  className?: string;
}

const sizeMap: Record<SpinnerSize, number> = {
  sm: 16,
  md: 24,
  lg: 32,
};

export default function Spinner({
  size = "md",
  color = "var(--color-primary-600)",
  className = "",
}: SpinnerProps) {
  return (
    <Loader2
      size={sizeMap[size]}
      color={color}
      className={`animate-spin ${className}`}
    />
  );
}
