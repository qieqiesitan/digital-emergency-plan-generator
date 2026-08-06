import { describe, it, expect } from "vitest";
import { flattenHierarchyEvents } from "./riskHierarchyEvents";
import type { HierarchyZone } from "@/types/riskManagement";

function zone(overrides: Partial<HierarchyZone> = {}): HierarchyZone {
  return {
    id: "z1",
    name: "重大风险区",
    description: null,
    objects: [],
    ...overrides,
  };
}

describe("flattenHierarchyEvents", () => {
  it("flattens object-level events with zone and object but no unit", () => {
    const zones = [
      zone({
        objects: [
          {
            id: "obj1",
            name: "锅炉房",
            category: null,
            is_risk_point: false,
            units: [],
            events: [
              {
                id: "ev1",
                accident_type: "火灾",
                description: null,
                risk_level: "重大",
                risk_score: null,
                method_type: "LEC",
                method_params: {},
                measures: [],
              },
            ],
          },
        ],
      }),
    ];

    const rows = flattenHierarchyEvents(zones);

    expect(rows).toEqual([
      {
        id: "ev1",
        accident_type: "火灾",
        risk_level: "重大",
        zone: "重大风险区",
        object: "锅炉房",
        unit: null,
      },
    ]);
  });

  it("flattens unit-level events with zone, object and unit", () => {
    const zones = [
      zone({
        objects: [
          {
            id: "obj1",
            name: "储罐区",
            category: null,
            is_risk_point: false,
            units: [
              {
                id: "unit1",
                name: "储罐 A",
                unit_type: "storage",
                events: [
                  {
                    id: "ev2",
                    accident_type: "泄漏",
                    description: null,
                    risk_level: "较大",
                    risk_score: null,
                    method_type: "LEC",
                    method_params: {},
                    measures: [],
                  },
                ],
              },
            ],
            events: [],
          },
        ],
      }),
    ];

    const rows = flattenHierarchyEvents(zones);

    expect(rows).toEqual([
      {
        id: "ev2",
        accident_type: "泄漏",
        risk_level: "较大",
        zone: "重大风险区",
        object: "储罐区",
        unit: "储罐 A",
      },
    ]);
  });

  it("returns an empty list when there are no zones or events", () => {
    expect(flattenHierarchyEvents([])).toEqual([]);
    expect(flattenHierarchyEvents([zone()])).toEqual([]);
  });
});
