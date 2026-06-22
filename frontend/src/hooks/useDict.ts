import { useState, useEffect } from "react";
import { fetchDictItems } from "@/services/dictService";
import type { DictItem } from "@/services/dictService";

export function useDict(dictType: string) {
  const [items, setItems] = useState<DictItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    fetchDictItems(dictType)
      .then((res) => {
        setItems(res || []);
      })
      .catch(() => {
        setItems([]);
      })
      .finally(() => {
        setLoading(false);
      });
  }, [dictType]);

  return { items, loading };
}
