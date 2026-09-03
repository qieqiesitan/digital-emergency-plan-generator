import { describe, expect, it, vi, beforeEach } from "vitest";
import api from "./api";
import {
  listLibrary,
  collectChemical,
} from "./chemicalLibraryService";

vi.mock("./api", () => ({ default: { get: vi.fn(), post: vi.fn() } }));

describe("chemicalLibraryService", () => {
  beforeEach(() => {
    vi.mocked(api.get).mockReset();
    vi.mocked(api.post).mockReset();
  });

  it("listLibrary calls GET /chemical-library", async () => {
    vi.mocked(api.get).mockResolvedValue({
      data: { data: { items: [], total: 0, page: 1, page_size: 20 } },
    });
    await listLibrary("乙醇");
    expect(api.get).toHaveBeenCalledWith(
      "/chemical-library",
      expect.objectContaining({ params: expect.objectContaining({ keyword: "乙醇" }) }),
    );
  });

  it("collectChemical posts enterprise_id + chemical_id", async () => {
    vi.mocked(api.post).mockResolvedValue({ data: { data: { id: "lib-2" } } });
    await collectChemical("ent-1", "chem-1");
    expect(api.post).toHaveBeenCalledWith(
      "/chemical-library/collect",
      { enterprise_id: "ent-1", chemical_id: "chem-1" },
    );
  });
});
