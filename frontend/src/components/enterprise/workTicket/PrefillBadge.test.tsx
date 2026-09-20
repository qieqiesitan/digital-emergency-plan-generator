import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { SOURCE_LABEL } from "./fieldSources";
import { PrefillBadge } from "./PrefillBadge";

describe("PrefillBadge", () => {
  it("手工填写不渲染徽标", () => {
    expect(renderToStaticMarkup(<PrefillBadge source="manual" />)).toBe("");
  });

  it("来源缺失不渲染徽标", () => {
    expect(renderToStaticMarkup(<PrefillBadge />)).toBe("");
  });

  it("历史票来源显示对应文案", () => {
    expect(renderToStaticMarkup(<PrefillBadge source="history" />)).toContain(
      SOURCE_LABEL.history,
    );
  });

  it("AI 来源显示 AI 徽标（提示需人工确认）", () => {
    expect(renderToStaticMarkup(<PrefillBadge source="ai" />)).toContain(SOURCE_LABEL.ai);
  });

  it("作业包来源显示作业包文案", () => {
    expect(renderToStaticMarkup(<PrefillBadge source="batch" />)).toContain(
      SOURCE_LABEL.batch,
    );
  });
});
