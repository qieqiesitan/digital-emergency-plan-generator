import { describe, expect, it } from "vitest";
import { libraryItemToPrefill } from "./chemicalLibraryPrefill";
import type { ChemicalLibraryItem } from "@/types/chemicalLibrary";

describe("libraryItemToPrefill", () => {
  it("maps standard fields and attaches library_id", () => {
    const item: ChemicalLibraryItem = {
      id: "lib-1",
      name: "乙醇",
      alias: "酒精",
      cas_no: "67-56-1",
      remark: null,
      un_no: "1170",
      physical_state: "液体",
      flash_point: "12℃",
      explosion_limit: null,
      ignition_temp: null,
      density: null,
      boiling_point: null,
      health_hazard: "中枢神经抑制",
      fire_hazard: null,
      leak_response: null,
      storage_transport: null,
      first_aid: null,
      protective_measures: null,
      created_at: "",
      updated_at: "",
    };
    const out = libraryItemToPrefill(item);
    expect(out.name).toBe("乙醇");
    expect(out.cas_no).toBe("67-56-1");
    expect(out.flash_point).toBe("12℃");
    expect(out.health_hazard).toBe("中枢神经抑制");
    expect(out.library_id).toBe("lib-1");
    expect(out).not.toHaveProperty("location");
    expect(out).not.toHaveProperty("created_at");
  });
});
