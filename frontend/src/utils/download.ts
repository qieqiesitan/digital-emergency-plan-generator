export function filenameFromContentDisposition(
  contentDisposition: string,
  fallback: string,
): string {
  if (!contentDisposition) return fallback;
  // RFC 5987: filename*=UTF-8''<percent-encoded>
  const star = /filename\*=UTF-8''([^;]+)/i.exec(contentDisposition);
  if (star?.[1]) {
    try {
      return decodeURIComponent(star[1].trim());
    } catch {
      // fall through to plain filename
    }
  }
  const plain = /filename="?([^";]+)"?/i.exec(contentDisposition);
  return plain?.[1]?.trim() || fallback;
}
