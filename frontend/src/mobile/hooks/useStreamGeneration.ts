import { useState, useRef, useCallback } from "react";

export interface StreamGenerationState {
  isGenerating: boolean;
  content: string;
  error: string | null;
  progress: {
    current: number;
    total: number;
    sectionName: string;
  } | null;
}

interface UseStreamGenerationOptions {
  onChunk?: (chunk: string) => void;
  onComplete?: (fullContent: string) => void;
  onError?: (error: string) => void;
}

export function useStreamGeneration(options: UseStreamGenerationOptions = {}) {
  const [state, setState] = useState<StreamGenerationState>({
    isGenerating: false,
    content: "",
    error: null,
    progress: null,
  });

  const abortRef = useRef<AbortController | null>(null);
  const fullContentRef = useRef("");

  const cancel = useCallback(() => {
    abortRef.current?.abort();
    setState(prev => ({
      ...prev,
      isGenerating: false,
      content: prev.content, // 保留已生成内容
    }));
  }, []);

  const generateSingle = useCallback(async (
    planId: string,
    sectionKey: string,
    sectionName?: string,
  ) => {
    abortRef.current = new AbortController();
    fullContentRef.current = "";

    setState({
      isGenerating: true,
      content: "",
      error: null,
      progress: { current: 1, total: 1, sectionName: sectionName ?? sectionKey },
    });

    try {
      const token = localStorage.getItem("access_token");
      const response = await fetch(`/api/v1/plans/${planId}/generate/${sectionKey}`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        signal: abortRef.current.signal,
      });

      if (!response.ok) {
        throw new Error("生成请求失败");
      }

      const reader = response.body?.getReader();
      if (!reader) throw new Error("无法读取响应流");

      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            try {
              const jsonStr = line.replace(/^(?:data: )+/, "");
              const event = JSON.parse(jsonStr);
              const chunk = event.content ?? event.token ?? event.chunk ?? "";

              if (chunk) {
                fullContentRef.current += chunk;
                setState(prev => ({
                  ...prev,
                  content: fullContentRef.current,
                }));
                options.onChunk?.(chunk);
              }
            } catch {
              // 跳过非 JSON 行
            }
          }
        }
      }

      setState(prev => ({ ...prev, isGenerating: false }));
      options.onComplete?.(fullContentRef.current);
    } catch (err) {
      if ((err as Error).name === "AbortError") return;
      const msg = (err as Error).message ?? "网络错误";
      setState(prev => ({ ...prev, isGenerating: false, error: msg }));
      options.onError?.(msg);
    }
  }, [options]);

  const generateBatch = useCallback(async (
    planId: string,
    sectionKeys: Array<{ key: string; name: string }>,
  ) => {
    const total = sectionKeys.length;
    let allContent = "";

    for (let i = 0; i < total; i++) {
      const { key, name } = sectionKeys[i];

      setState(prev => ({
        ...prev,
        progress: { current: i + 1, total, sectionName: name },
      }));

      const token = localStorage.getItem("access_token");

      try {
        const response = await fetch(`/api/v1/plans/${planId}/generate/${key}`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          signal: abortRef.current?.signal,
        });

        if (!response.ok) continue;

        const reader = response.body?.getReader();
        if (!reader) continue;

        const decoder = new TextDecoder();
        let buffer = "";
        let sectionContent = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() ?? "";

          for (const line of lines) {
            if (line.startsWith("data: ")) {
              try {
                const jsonStr = line.replace(/^(?:data: )+/, "");
                const event = JSON.parse(jsonStr);
                const chunk = event.content ?? event.token ?? event.chunk ?? "";
                if (chunk) {
                  sectionContent += chunk;
                  setState(prev => ({
                    ...prev,
                    content: allContent + sectionContent,
                  }));
                  options.onChunk?.(chunk);
                }
              } catch { /* skip */ }
            }
          }
        }

        allContent += sectionContent;
      } catch {
        // 继续下一个
      }
    }

    setState(prev => ({ ...prev, isGenerating: false }));
    options.onComplete?.(allContent);
  }, [options]);

  return { state, generateSingle, generateBatch, cancel };
}
