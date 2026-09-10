import { describe, expect, it } from "vitest";
import { filenameFromContentDisposition } from "./download";

describe("filenameFromContentDisposition", () => {
  it("优先解析 RFC 5987 filename*（UTF-8 中文文件名）", () => {
    const name = encodeURIComponent("西安宝岳空间科技有限公司_事故风险评估报告.docx");
    const cd = `attachment; filename="risk.docx"; filename*=UTF-8''${name}`;
    expect(filenameFromContentDisposition(cd, "fallback.docx")).toBe(
      "西安宝岳空间科技有限公司_事故风险评估报告.docx",
    );
  });

  it("无 filename* 时解析普通 filename", () => {
    const cd = 'attachment; filename="report.docx"';
    expect(filenameFromContentDisposition(cd, "fallback.docx")).toBe("report.docx");
  });

  it("无法解析时回退默认名", () => {
    expect(filenameFromContentDisposition("", "fallback.docx")).toBe("fallback.docx");
  });
});
