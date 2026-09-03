import { describe, expect, it } from "vitest";
import { htmlToMarkdown, renderReportMarkdown } from "./reportMarkdown";

describe("renderReportMarkdown（报告正文 markdown → HTML，与预案 PlanEditorPage 同配置）", () => {
  it("Markdown 表格渲染为 <table>", () => {
    const html = renderReportMarkdown(
      "| 序号 | 名称 |\n| --- | --- |\n| 1 | 干粉灭火器 |",
    );
    expect(html).toContain("<table>");
    expect(html).toContain("<th>名称</th>");
    expect(html).toContain("<td>干粉灭火器</td>");
  });

  it("HTML table 标签原样保留（风险评估模板输出 HTML 表格）", () => {
    const raw = '<table border="1"><tr><td>风险等级</td></tr></table>';
    expect(renderReportMarkdown(raw)).toContain(raw);
  });

  it("标题与粗体转成 HTML", () => {
    const html = renderReportMarkdown("## 一、调查目的\n\n这是**重点**内容。");
    expect(html).toContain("<h2>一、调查目的</h2>");
    expect(html).toContain("<strong>重点</strong>");
  });

  it("mermaid 围栏保留为代码块而非原样泄漏分隔符", () => {
    const html = renderReportMarkdown(
      "```mermaid\nflowchart TD\nA[开始] --> B[结束]\n```",
    );
    expect(html).toContain("language-mermaid");
    expect(html).not.toContain("```mermaid");
  });

  it("空文本安全返回空字符串", () => {
    expect(renderReportMarkdown("")).toBe("");
  });
});

describe("htmlToMarkdown（Tiptap/报告 HTML → 草稿 Markdown）", () => {
  it("段落与标题", () => {
    const html = "<h2>一、辨识</h2><p>本章结论</p><p>第二段</p>";
    expect(htmlToMarkdown(html)).toBe("## 一、辨识\n\n本章结论\n\n第二段");
  });

  it("行内粗体/斜体/下划线/删除线/行内代码", () => {
    const html =
      "<p>涉及<strong>液氨</strong>、<em>重大</em>危险源，" +
      "<u>必须</u>配置<code>detector</code>，历史<strike>错误</strike>做法。</p>";
    const md = htmlToMarkdown(html);
    expect(md).toContain("**液氨**");
    expect(md).toContain("*重大*");
    expect(md).toContain("__必须__");
    expect(md).toContain("`detector`");
    expect(md).toContain("~~错误~~");
  });

  it("无序/有序列表", () => {
    const html = "<ul><li>干粉灭火器</li><li>消火栓</li></ul>";
    expect(htmlToMarkdown(html)).toBe("- 干粉灭火器\n- 消火栓");
  });

  it("HTML 表格 → markdown 管道表", () => {
    const html = "<table><thead><tr><th>序号</th><th>名称</th></tr></thead>" +
      "<tbody><tr><td>1</td><td>干粉灭火器</td></tr></tbody></table>";
    expect(htmlToMarkdown(html)).toBe(
      "| 序号 | 名称    |\n| --- | ----- |\n| 1  | 干粉灭火器 |",
    );
  });

  it("代码块与链接", () => {
    const html = '<pre><code>console.log(1)</code></pre><p><a href="/x">查看</a></p>';
    const md = htmlToMarkdown(html);
    expect(md).toContain("```\nconsole.log(1)\n```");
    expect(md).toContain("[查看](/x)");
  });

  it("markdown → renderReportMarkdown → htmlToMarkdown 往返保留正文结构", () => {
    const md = "## 一、辨识\n\n该企业主要涉及**液氨**存储。\n\n- 罐区 1\n- 罐区 2";
    const roundTrip = htmlToMarkdown(renderReportMarkdown(md));
    expect(roundTrip).toContain("## 一、辨识");
    expect(roundTrip).toContain("该企业主要涉及**液氨**存储");
    expect(roundTrip).toContain("- 罐区 1");
    expect(roundTrip).toContain("- 罐区 2");
  });
});
