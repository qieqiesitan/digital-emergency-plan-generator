import { describe, expect, it } from "vitest";
import { renderToString } from "react-dom/server";
import TiptapEditor from "./TiptapEditor";

describe("TiptapEditor", () => {
  it("初始化不抛错并可输出 HTML", () => {
    const html = renderToString(
      <TiptapEditor content="<p>测试</p>" onChange={() => {}} />,
    );
    expect(html).toContain("编辑器初始化中");
  });
});
