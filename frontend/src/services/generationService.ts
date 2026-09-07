import type { SSEEvent, GenerateBatchRequest, GenerationStatusData } from "@/types/plan";
import { sseFetch, apiJsonFetch } from "./sseFetch";

export function generateSectionStream(
  planId: string,
  sectionKey: string,
  onEvent: (event: SSEEvent) => void,
  onError: (error: string) => void,
  onComplete: () => void,
  customInstruction?: string
): AbortController {
  const controller = new AbortController();

  sseFetch({
    path: `/plans/${planId}/generate/${sectionKey}`,
    method: "POST",
    body: { custom_instruction: customInstruction || null },
    signal: controller.signal,
    errorMessage: "生成请求失败",
    onData: (data) => {
      try {
        onEvent(JSON.parse(data) as SSEEvent);
      } catch {
        // skip malformed events
      }
    },
    onComplete,
    onError,
  });

  return controller;
}

export function generateBatchStream(
  planId: string,
  sectionKeys: string[] | null,
  onEvent: (event: SSEEvent) => void,
  onError: (error: string) => void,
  onComplete: () => void
): AbortController {
  const controller = new AbortController();

  const body: GenerateBatchRequest = { section_keys: sectionKeys };

  sseFetch({
    path: `/plans/${planId}/generate/batch`,
    method: "POST",
    body,
    signal: controller.signal,
    errorMessage: "批量生成请求失败",
    onData: (data) => {
      try {
        onEvent(JSON.parse(data) as SSEEvent);
      } catch {
        // skip malformed events
      }
    },
    onComplete,
    onError,
  });

  return controller;
}


export async function generateBatchBackground(
  planId: string,
  sectionKeys: string[] | null
): Promise<{ code: number; message: string; failed_sections?: Array<{ section_key: string; title: string }> }> {
  const body: GenerateBatchRequest = { section_keys: sectionKeys };
  return apiJsonFetch<{ code: number; message: string; failed_sections?: Array<{ section_key: string; title: string }> }>({
    path: `/plans/${planId}/generate/batch/background`,
    method: "POST",
    body,
    errorMessage: "后台生成请求失败",
  });
}

export async function getGenerationStatus(
  planId: string
): Promise<{ code: number; data: GenerationStatusData }> {
  return apiJsonFetch<{ code: number; data: { generating: boolean; failed_sections: Array<{ section_key: string; title: string }> } }>({
    path: `/plans/${planId}/generate/status`,
    errorMessage: "查询生成状态失败",
  });
}
export async function stopGeneration(planId: string): Promise<void> {
  await apiJsonFetch({
    path: `/plans/${planId}/generate/stop`,
    method: "POST",
    errorMessage: "停止生成失败",
  });
}

export function regenerateSelectionStream(
  planId: string,
  sectionKey: string,
  selectedText: string,
  contextBefore: string | null,
  contextAfter: string | null,
  onEvent: (event: SSEEvent) => void,
  onError: (error: string) => void,
  onComplete: () => void,
  customInstruction: string | null = null
): AbortController {
  const controller = new AbortController();

  sseFetch({
    path: `/plans/${planId}/sections/${sectionKey}/regenerate`,
    method: "POST",
    body: {
      selected_text: selectedText,
      surrounding_context_before: contextBefore,
      surrounding_context_after: contextAfter,
      custom_instruction: customInstruction,
    },
    signal: controller.signal,
    errorMessage: "请求失败",
    onData: (data) => {
      try {
        onEvent(JSON.parse(data) as SSEEvent);
      } catch {
        // skip malformed events
      }
    },
    onComplete,
    onError,
  });

  return controller;
}
