import { describe, expect, it, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import AppIcon from "./AppIcon";

describe("AppIcon", () => {
  it("renders svg with size, viewBox and aria-hidden", () => {
    const html = renderToStaticMarkup(<AppIcon name="risk" size={24} />);
    expect(html).toContain("<svg");
    expect(html).toContain('width="24"');
    expect(html).toContain('height="24"');
    expect(html).toContain('viewBox="0 0 1024 1024"');
    expect(html).toContain('aria-hidden="true"');
  });

  it("forwards className", () => {
    const html = renderToStaticMarkup(<AppIcon name="ai" className="foo" />);
    expect(html).toContain('class="foo"');
  });

  it("warns and renders nothing for unknown name", () => {
    const spy = vi.spyOn(console, "warn").mockImplementation(() => {});
    const html = renderToStaticMarkup(<AppIcon name={"nope" as never} />);
    expect(html).toBe("");
    expect(spy).toHaveBeenCalled();
    spy.mockRestore();
  });
});
