import type { SSEEvent, GenerateBatchRequest } from "@/types/generation";

export function generateSectionStream(
  planId: string,
  sectionKey: string,
  customInstruction?: string,
  onEvent: (event: SSEEvent) => void,
  onError: (error: string) => void,
  onComplete: () => void
): AbortController {
  const controller = new AbortController();
  const token = localStorage.getItem("access_token");

  fetch(`/api/v1/plans/${planId}/generate/${sectionKey}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ custom_instruction: customInstruction || null }),
    signal: controller.signal,
  })
    .then(async (response) => {
      if (!response.ok) {
        const err = await response.json().catch(() => ({ message: "生成请求失败" }));
        onError(err.message || err.detail || "生成请求失败");
        return;
      }

      const reader = response.body?.getReader();
      if (!reader) { onError("无法读取响应流"); return; }

      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) { onComplete(); break; }

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            try {
              const jsonStr = line.replace(/^(?:data: )+/, ""); const event: SSEEvent = JSON.parse(jsonStr);
              onEvent(event);
            } catch {
              // skip malformed events
            }
          }
        }
      }
    })
    .catch((err) => {
      if (err.name !== "AbortError") {
        onError(err.message || "网络错误");
      }
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
  const token = localStorage.getItem("access_token");

  const body: GenerateBatchRequest = { section_keys: sectionKeys };

  fetch(`/api/v1/plans/${planId}/generate/batch`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(body),
    signal: controller.signal,
  })
    .then(async (response) => {
      if (!response.ok) {
        onError("批量生成请求失败");
        return;
      }
      const reader = response.body?.getReader();
      if (!reader) { onError("无法读取响应流"); return; }

      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) { onComplete(); break; }
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";
        for (const line of lines) {
          if (line.startsWith("data: ")) {
            try {
              const jsonStr = line.replace(/^(?:data: )+/, ""); const event: SSEEvent = JSON.parse(jsonStr);
              onEvent(event);
            } catch { /* skip */ }
          }
        }
      }
    })
    .catch((err) => {
      if (err.name !== "AbortError") {
        onError(err.message || "网络错误");
      }
    });

  return controller;
}


export async function generateBatchBackground(
  planId: string,
  sectionKeys: string[] | null
): Promise<{ code: number; message: string }> {
  const token = localStorage.getItem("access_token");
  const body: GenerateBatchRequest = { section_keys: sectionKeys };
  const res = await fetch(`/api/v1/plans/${planId}/generate/batch/background`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ message: "请求失败" }));
    throw new Error(err.message || err.detail || "后台生成请求失败");
  }
  return res.json();
}
export async function stopGeneration(planId: string): Promise<void> {
  const token = localStorage.getItem("access_token");
  await fetch(`/api/v1/plans/${planId}/generate/stop`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
  });
}
