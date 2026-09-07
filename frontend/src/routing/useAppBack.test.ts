import { describe, expect, it } from "vitest";
import { resolveBackTarget } from "./useAppBack";

describe("resolveBackTarget", () => {
  it("站内历史存在时走浏览器后退", () => {
    expect(resolveBackTarget(true, "/fallback")).toBe(-1);
  });

  it("深层直达（无站内历史）时回逻辑上级", () => {
    expect(resolveBackTarget(false, "/enterprises/abc/hazard")).toBe(
      "/enterprises/abc/hazard",
    );
  });
});
