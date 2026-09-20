import dayjs from "dayjs";
import type { WorkTicketFieldDef } from "@/types/workTicket";

/**
 * 表单值 → 落库值：datetime/datetimerange 字段在表单里是 dayjs 对象，
 * 提交前统一转 ISO 字符串。
 */
export function normalizeValues(
  fields: WorkTicketFieldDef[],
  raw: Record<string, unknown>,
): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const field of fields) {
    const value = raw[field.field_key];
    if (value === undefined || value === null || value === "") continue;
    if (field.field_type === "datetime" && dayjs.isDayjs(value)) {
      out[field.field_key] = value.toISOString();
    } else if (
      field.field_type === "datetimerange" &&
      Array.isArray(value) &&
      value.length === 2
    ) {
      const [start, end] = value as [dayjs.Dayjs, dayjs.Dayjs];
      out[field.field_key] = [start.toISOString(), end.toISOString()];
    } else {
      out[field.field_key] = value;
    }
  }
  return out;
}

/**
 * 落库值 → 表单值：预填接口返回的是 ISO 字符串，而 antd 的
 * DatePicker / RangePicker 只接受 dayjs 对象——直接塞字符串会在渲染时抛
 * `isValid is not a function`（2026-09-20 浏览器实测抓到的真实崩溃）。
 */
export function toFormValues(
  fields: WorkTicketFieldDef[],
  values: Record<string, unknown>,
): Record<string, unknown> {
  const out: Record<string, unknown> = { ...values };
  for (const field of fields) {
    const value = out[field.field_key];
    if (field.field_type === "datetime" && typeof value === "string" && value) {
      out[field.field_key] = dayjs(value);
    } else if (
      field.field_type === "datetimerange" &&
      Array.isArray(value) &&
      value.length === 2
    ) {
      out[field.field_key] = value.map((item) =>
        typeof item === "string" ? dayjs(item) : item,
      );
    }
  }
  return out;
}
