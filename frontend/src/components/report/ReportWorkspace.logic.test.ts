import { describe, expect, it } from "vitest";
import type { ReportChapter } from "@/types/reportWorkspace";
import { addFailedChapter } from "./ReportWorkspace";

describe("ReportWorkspace 失败章节 reducer", () => {
  it("追加新失败章节", () => {
    const list: ReportChapter[] = [];
    const next = addFailedChapter(list, "ch1", "一、辨识");
    expect(next).toEqual([{ key: "ch1", title: "一、辨识", content: "" }]);
    expect(list).toHaveLength(0); // 纯函数不修改原数组
  });

  it("同一 key 不重复追加", () => {
    const base = addFailedChapter([], "ch1", "一、辨识");
    const next = addFailedChapter(base, "ch1");
    expect(next).toHaveLength(1);
  });

  it("缺 title 时回退为 key", () => {
    const next = addFailedChapter([], "ch3");
    expect(next[0].title).toBe("ch3");
  });
});
