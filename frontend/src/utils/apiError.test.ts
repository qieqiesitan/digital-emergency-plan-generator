import { describe, expect, it } from "vitest";
import { errorMessage } from "./apiError";

const axiosLike = (data: unknown) => ({ response: { data } });

describe("errorMessage", () => {
  it("字符串 detail 直接返回", () => {
    expect(errorMessage(axiosLike({ detail: "企业不存在" }), "失败")).toBe("企业不存在");
  });

  it("pydantic 校验数组带上字段名（这是 422 最常见的样子）", () => {
    const err = axiosLike({
      detail: [
        { loc: ["body", "employee_count"], msg: "Input should be a valid integer" },
        { loc: ["body", "name"], msg: "String should have at least 1 character" },
      ],
    });
    expect(errorMessage(err, "失败")).toBe(
      "employee_count：Input should be a valid integer；name：String should have at least 1 character",
    );
  });

  it("数组里混入字符串也能处理", () => {
    expect(errorMessage(axiosLike({ detail: ["第一处错误", "第二处错误"] }), "失败")).toBe(
      "第一处错误；第二处错误",
    );
  });

  it("没有 loc 时只返回消息", () => {
    expect(errorMessage(axiosLike({ detail: [{ msg: "值不合法" }] }), "失败")).toBe("值不合法");
  });

  it("带上实际值，便于一眼看出传了什么非法类型", () => {
    const err = axiosLike({
      detail: [
        {
          loc: ["body", "industry"],
          msg: "Input should be a valid string",
          input: { label: "软件业", value: "software" },
        },
      ],
    });
    const text = errorMessage(err, "失败");
    expect(text).toContain("industry");
    expect(text).toContain("Input should be a valid string");
    expect(text).toContain("实际值");
    expect(text).toContain("software");
  });

  it("超长实际值会截断", () => {
    const err = axiosLike({
      detail: [{ loc: ["body", "industry"], msg: "bad", input: "x".repeat(200) }],
    });
    const text = errorMessage(err, "失败");
    expect(text.length).toBeLessThan(160);
    expect(text).toContain("…");
  });

  it("detail 缺失时回落到 message，再回落到 fallback", () => {
    expect(errorMessage({ message: "Network Error" }, "失败")).toBe("Network Error");
    expect(errorMessage({}, "失败")).toBe("失败");
    expect(errorMessage(null, "失败")).toBe("失败");
  });

  it("空数组/空字符串不会冒充有效信息", () => {
    expect(errorMessage(axiosLike({ detail: [] }), "失败")).toBe("失败");
    expect(errorMessage(axiosLike({ detail: "   " }), "失败")).toBe("失败");
  });
});
