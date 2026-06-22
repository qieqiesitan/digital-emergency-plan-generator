import dayjs from "dayjs";
import relativeTime from "dayjs/plugin/relativeTime";
import "dayjs/locale/zh-cn";

dayjs.extend(relativeTime);
dayjs.locale("zh-cn");

export function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr) return "-";
  return dayjs(dateStr).format("YYYY-MM-DD HH:mm");
}

export function formatDateShort(dateStr: string | null | undefined): string {
  if (!dateStr) return "-";
  return dayjs(dateStr).format("YYYY-MM-DD");
}

export function fromNow(dateStr: string | null | undefined): string {
  if (!dateStr) return "-";
  return dayjs(dateStr).fromNow();
}

export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
  return (bytes / (1024 * 1024)).toFixed(1) + " MB";
}

export function truncate(text: string, maxLen: number): string {
  if (text.length <= maxLen) return text;
  return text.slice(0, maxLen) + "...";
}

// Alias for backward compatibility
export const formatRelativeTime = fromNow;
