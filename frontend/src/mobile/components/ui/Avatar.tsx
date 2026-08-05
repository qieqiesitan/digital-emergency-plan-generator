import { User } from "lucide-react";

type AvatarSize = "sm" | "md" | "lg";

interface AvatarProps {
  src?: string;
  name?: string;
  size?: AvatarSize;
  colorSeed?: string;
  className?: string;
}

const sizeMap: Record<AvatarSize, { size: number; text: string }> = {
  sm: { size: 32, text: "text-sm" },
  md: { size: 44, text: "text-base" },
  lg: { size: 72, text: "text-2xl" },
};

const bgPalette = [
  "bg-blue-100 text-blue-700",
  "bg-green-100 text-green-700",
  "bg-red-100 text-red-700",
  "bg-amber-100 text-amber-700",
  "bg-indigo-100 text-indigo-700",
  "bg-pink-100 text-pink-700",
];

function getColorIndex(seed: string): number {
  let hash = 0;
  for (let i = 0; i < seed.length; i++) {
    hash = seed.charCodeAt(i) + ((hash << 5) - hash);
  }
  return Math.abs(hash) % bgPalette.length;
}

export default function Avatar({
  src,
  name,
  size = "md",
  colorSeed,
  className = "",
}: AvatarProps) {
  const { size: px, text: textClass } = sizeMap[size];

  // 图片模式
  if (src) {
    return (
      <img
        src={src}
        alt={name ?? ""}
        className={`rounded-full object-cover shrink-0 ${className}`}
        style={{ width: px, height: px }}
      />
    );
  }

  // 首字母模式
  const initial = name ? name.charAt(0) : "";
  const paletteClass = colorSeed
    ? bgPalette[getColorIndex(colorSeed)]
    : "bg-neutral-200 text-neutral-600";

  return (
    <div
      className={`rounded-full flex items-center justify-center font-semibold shrink-0 ${paletteClass} ${textClass} ${className}`}
      style={{ width: px, height: px }}
    >
      {initial || <User size={px * 0.45} />}
    </div>
  );
}
