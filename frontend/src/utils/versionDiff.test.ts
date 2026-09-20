import { describe, expect, it } from "vitest";
import { groupDiffs, plainTextLength, summarizeDiffs } from "./versionDiff";
import type { SectionDiff } from "@/types/plan";

const d = (key: string, type: SectionDiff["change_type"]): SectionDiff => ({
  section_key: key, title: key, change_type: type, old_content: null, new_content: null,
});

describe("groupDiffs", () => {
  it("按 新增→删除→修改→未变 顺序分组，空组不出现", () => {
    const groups = groupDiffs([d("c", "unchanged"), d("a", "modified"), d("b", "added")]);
    expect(groups.map(g => g.kind)).toEqual(["added", "modified", "unchanged"]);
    expect(groups.map(g => g.label)).toEqual(["新增章节", "内容有修改", "未变化"]);
    expect(groups[0].items.map(i => i.section_key)).toEqual(["b"]);
  });

  it("空输入返回空数组", () => {
    expect(groupDiffs(null)).toEqual([]);
    expect(groupDiffs([])).toEqual([]);
  });
});

describe("summarizeDiffs", () => {
  it("统计各类数量并给出 changed 合计", () => {
    const s = summarizeDiffs([
      d("a", "added"), d("b", "removed"), d("c", "modified"), d("d", "unchanged"), d("e", "unchanged"),
    ]);
    expect(s).toEqual({ added: 1, removed: 1, modified: 1, unchanged: 2, changed: 3 });
  });

  it("空输入全 0", () => {
    expect(summarizeDiffs(undefined)).toEqual({ added: 0, removed: 0, modified: 0, unchanged: 0, changed: 0 });
  });
});

describe("plainTextLength", () => {
  it("忽略 HTML 标签与空白，只算正文字数", () => {
    expect(plainTextLength("<h3>总则</h3><p>本预案 适用于</p>")).toBe(8);
    expect(plainTextLength(null)).toBe(0);
  });
});
