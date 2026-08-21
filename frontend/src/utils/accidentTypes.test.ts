import { describe, expect, it } from "vitest";
import {
  ACCIDENT_TYPES_2025,
  LEGACY_TO_NEW_ACCIDENT_TYPE_MAP,
  normalizeAccidentType,
} from "./accidentTypes";

describe("accidentTypes (GB 6441-2025)", () => {
  it("exposes exactly 27 ordered types", () => {
    expect(ACCIDENT_TYPES_2025).toEqual([
      "物体打击", "厂（场）内车辆致害", "道路（轨道）车辆致害", "机械致害", "起重致害",
      "触电", "淹溺", "灼烫", "火灾", "高处坠落", "跌落", "坍塌", "水害", "容器爆炸",
      "管道爆炸", "可燃气体爆炸", "可燃液体蒸气爆炸", "粉尘爆炸", "民用爆炸物品爆炸",
      "烟花爆竹爆炸", "其他可燃固体爆炸", "高温熔融物爆炸", "中毒", "窒息", "滑坡",
      "泄漏", "其他",
    ]);
    expect(new Set(ACCIDENT_TYPES_2025).size).toBe(27);
  });

  it("maps all 20 old standard types and 2 presets", () => {
    expect(LEGACY_TO_NEW_ACCIDENT_TYPE_MAP["瓦斯爆炸"]).toBe("可燃气体爆炸");
    expect(LEGACY_TO_NEW_ACCIDENT_TYPE_MAP["锅炉爆炸"]).toBe("容器爆炸");
    expect(LEGACY_TO_NEW_ACCIDENT_TYPE_MAP["爆炸"]).toBe("其他");
    expect(LEGACY_TO_NEW_ACCIDENT_TYPE_MAP["中毒窒息"]).toBe("中毒");
    expect(Object.keys(LEGACY_TO_NEW_ACCIDENT_TYPE_MAP)).toHaveLength(22);
  });

  it("normalizes new/legacy/unknown values", () => {
    expect(normalizeAccidentType("火灾")).toBe("火灾");
    expect(normalizeAccidentType("中毒和窒息")).toBe("中毒");
    expect(normalizeAccidentType("设备损坏/数据丢失")).toBe("设备损坏/数据丢失");
    expect(normalizeAccidentType("")).toBe("");
  });
});
