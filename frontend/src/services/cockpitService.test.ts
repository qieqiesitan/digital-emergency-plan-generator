import { describe, expect, it, vi, beforeEach } from "vitest";

vi.mock("@/services/api", () => ({
  default: { get: vi.fn() },
}));

import api from "@/services/api";
import { getCockpitSummary } from "@/services/cockpitService";
import type { CockpitSummary } from "@/types/cockpit";

const mockedGet = vi.mocked(api.get);

describe("cockpitService", () => {
  beforeEach(() => {
    mockedGet.mockReset();
  });

  it("requests cockpit-summary with the enterprise id", async () => {
    const summary: CockpitSummary = {
      risk_counts: { major: 1, larger: 1, general: 1, low: 1, total: 4 },
      zone_risks: [],
      top_risks: [],
      risk_index: 55,
      hazard_counts: { open: 3, due: 2, overdue: 0 },
      todos: [],
      completion: { percent: 50, modules: [] },
      recent_activities: [],
    };
    mockedGet.mockResolvedValue({ data: { data: summary } });

    const result = await getCockpitSummary("e1");

    expect(mockedGet).toHaveBeenCalledWith("/enterprises/e1/cockpit-summary");
    expect(result).toEqual(summary);
  });
});
