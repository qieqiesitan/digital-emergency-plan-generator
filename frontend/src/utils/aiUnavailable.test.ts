import { describe, expect, it } from "vitest";
import {
  AI_CONFIG_ROUTE,
  AI_NOT_CONFIGURED_HINT,
  aiErrorDisplay,
  isAiNotConfiguredError,
} from "./aiUnavailable";

describe("aiUnavailable", () => {
  it("识别后端 detail 中的 AI 未配置文案", () => {
    expect(isAiNotConfiguredError("系统未配置 AI 模型，请联系管理员")).toBe(true);
    expect(isAiNotConfiguredError("系统尚未配置 AI 模型，请联系管理员")).toBe(true);
    expect(isAiNotConfiguredError("尚未配置 AI")).toBe(true);
    expect(isAiNotConfiguredError("AI 未配置")).toBe(true);
    expect(isAiNotConfiguredError("请先配置 AI 模型")).toBe(true);
  });

  it("不误判普通错误 / 空消息", () => {
    expect(isAiNotConfiguredError("模型调用超时，请重试")).toBe(false);
    expect(isAiNotConfiguredError("生成章节失败")).toBe(false);
    expect(isAiNotConfiguredError("")).toBe(false);
    expect(isAiNotConfiguredError(undefined)).toBe(false);
    expect(isAiNotConfiguredError(null)).toBe(false);
  });

  it("AI 未配置错误归一化为统一引导文案（含配置页路径）", () => {
    const disp = aiErrorDisplay("系统未配置 AI 模型，请联系管理员", "请求失败");
    expect(disp.notConfigured).toBe(true);
    expect(disp.text).toBe(AI_NOT_CONFIGURED_HINT);
    expect(disp.text).toContain("设置→AI 配置");
  });

  it("其余错误保留原文；空消息回退通用文案", () => {
    const disp = aiErrorDisplay("模型超时", "生成失败");
    expect(disp.notConfigured).toBe(false);
    expect(disp.text).toBe("模型超时");
    expect(aiErrorDisplay(undefined, "生成失败").text).toBe("生成失败");
    expect(aiErrorDisplay("", "请求失败").text).toBe("请求失败");
  });

  it("导出 AI 配置页路由", () => {
    expect(AI_CONFIG_ROUTE).toBe("/settings/ai-config");
  });
});
