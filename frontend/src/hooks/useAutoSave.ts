import { useEffect, useRef, useCallback } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { updateSection } from "@/services/sectionService";

export function useAutoSave(planId: string, sectionKey: string) {
  const queryClient = useQueryClient();
  const lastSavedRef = useRef<string>("");
  const saveStatusRef = useRef<"saved" | "saving" | "unsaved">("saved");

  const mutation = useMutation({
    mutationFn: (content: string) => updateSection(planId, sectionKey, { content }),
    onSuccess: () => {
      saveStatusRef.current = "saved";
      queryClient.invalidateQueries({ queryKey: ["planSections", planId] });
    },
    onError: () => {
      saveStatusRef.current = "unsaved";
    },
  });

  const save = useCallback(
    (content: string) => {
      if (content === lastSavedRef.current) return;
      saveStatusRef.current = "saving";
      lastSavedRef.current = content;
      mutation.mutate(content);
    },
    [mutation]
  );

  useEffect(() => {
    return () => {
      // cleanup
    };
  }, []);

  return { save, saveStatus: saveStatusRef, isSaving: mutation.isPending };
}
