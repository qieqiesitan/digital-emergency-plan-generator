import { describe, expect, it } from "vitest";
import { EMERGENCY_CARD_CSS } from "./emergencyCardCss";

describe("EMERGENCY_CARD_CSS", () => {
  it("包含卡片容器与主题配色样式", () => {
    expect(EMERGENCY_CARD_CSS).toContain(".emergency-card-section");
    expect(EMERGENCY_CARD_CSS).toContain(".emergency-card[data-theme=\"danger\"]");
    expect(EMERGENCY_CARD_CSS).toContain(".emergency-card[data-theme=\"action\"]");
    expect(EMERGENCY_CARD_CSS).toContain(".emergency-card[data-theme=\"info\"]");
    expect(EMERGENCY_CARD_CSS).toContain(".emergency-card[data-theme=\"contact\"]");
  });
});
