import { describe, expect, it } from "vitest";
import dayjs from "dayjs";
import type { WorkTicketFieldDef } from "@/types/workTicket";
import { normalizeValues, toFormValues } from "./formValues";

const FIELDS: WorkTicketFieldDef[] = [
  { field_key: "work_content", label: "作业内容", field_type: "textarea" },
  { field_key: "apply_time", label: "作业申请时间", field_type: "datetime" },
  { field_key: "work_period", label: "作业实施时间", field_type: "datetimerange" },
];

describe("normalizeValues（表单 → 落库）", () => {
  it("datetime 转 ISO 字符串", () => {
    const out = normalizeValues(FIELDS, {
      apply_time: dayjs("2026-09-20T08:00:00+08:00"),
    });
    expect(typeof out.apply_time).toBe("string");
    expect(String(out.apply_time)).toContain("2026-09-20");
  });

  it("datetimerange 转两个 ISO 字符串", () => {
    const out = normalizeValues(FIELDS, {
      work_period: [dayjs("2026-09-20T08:00:00+08:00"), dayjs("2026-09-20T16:00:00+08:00")],
    });
    expect(Array.isArray(out.work_period)).toBe(true);
    expect((out.work_period as string[]).length).toBe(2);
  });

  it("空值字段不产出", () => {
    expect(normalizeValues(FIELDS, { apply_time: null, work_content: "" })).toEqual({});
  });
});

describe("toFormValues（预填 → 表单）", () => {
  it("ISO 字符串还原成 dayjs，避免 DatePicker 崩溃", () => {
    const out = toFormValues(FIELDS, {
      apply_time: "2026-09-20T08:00:00+08:00",
    });
    expect(dayjs.isDayjs(out.apply_time)).toBe(true);
  });

  it("datetimerange 的字符串数组还原成 dayjs 数组", () => {
    const out = toFormValues(FIELDS, {
      work_period: ["2026-09-20T08:00:00+08:00", "2026-09-20T16:00:00+08:00"],
    });
    const period = out.work_period as unknown[];
    expect(period.every((item) => dayjs.isDayjs(item))).toBe(true);
  });

  it("非日期字段原样透传", () => {
    const out = toFormValues(FIELDS, { work_content: "更换阀门" });
    expect(out.work_content).toBe("更换阀门");
  });

  it("已是 dayjs 的值不会被二次包装", () => {
    const original = dayjs("2026-09-20T08:00:00+08:00");
    const out = toFormValues(FIELDS, { apply_time: original });
    expect(out.apply_time).toBe(original);
  });
});
