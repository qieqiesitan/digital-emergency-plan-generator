import { useEffect, useMemo, useState } from "react";
import { Button, Drawer, Input, Space, message } from "antd";
import { useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import {
  generateResourcesAI,
  batchCreateResources,
  listResources,
  deleteResource,
} from "@/services/emergencyResourceService";
import type { EmergencyResourceCreate } from "@/types/emergencyResource";
import EmergencyResourceForm from "@/components/enterprise/EmergencyResourceForm";
import CandidatesReview from "./CandidatesReview";
import ImportDrawer from "./ImportDrawer";
import type { CandidateItem, ImportResult } from "@/types/onboarding";

interface Props {
  enterpriseId: string;
  onDone: () => void;
  onPrev: () => void;
  imported?: CandidateItem[];
  onAddImported?: (stepKey: string, items: CandidateItem[]) => void;
  onRemoveImported?: (stepKey: string, itemKey: string) => void;
}

/** 候选 dict 收窄为 EmergencyResourceCreate（数量/布尔/数值字段显式转换） */
function toCreatePayload(item: CandidateItem): EmergencyResourceCreate {
  const str = (v: unknown): string | undefined =>
    v === null || v === undefined || String(v).trim() === "" ? undefined : String(v);
  const num = (v: unknown): number | undefined => {
    if (v === null || v === undefined || String(v).trim() === "") return undefined;
    const n = Number(v);
    return Number.isFinite(n) ? n : undefined;
  };
  return {
    category: str(item.category) || "",
    name: str(item.name) || "",
    specification: str(item.specification),
    quantity: num(item.quantity),
    unit: str(item.unit),
    location: str(item.location),
    responsible_person: str(item.responsible_person),
    contact_phone: str(item.contact_phone),
    is_external: item.is_external === true || item.is_external === "true",
    external_address: str(item.external_address),
    external_distance_km: num(item.external_distance_km),
  };
}

/** 解析请求错误：优先透出后端 detail（如 504「AI 响应超时」），其次 e.message，最后兜底文案 */
function errorDetail(e: unknown, fallback: string): string {
  if (axios.isAxiosError(e) && e.response?.data?.detail) {
    return e.response.data.detail;
  }
  return e instanceof Error && e.message ? e.message : fallback;
}

export default function StepResources({
  enterpriseId,
  onDone,
  onPrev,
  imported,
  onAddImported,
  onRemoveImported,
}: Props) {
  const queryClient = useQueryClient();
  const [overview, setOverview] = useState("");
  const [candidates, setCandidates] = useState<CandidateItem[]>([]);
  const [accepted, setAccepted] = useState<CandidateItem[]>([]);
  const [acceptedLoading, setAcceptedLoading] = useState(!!enterpriseId);
  const [acceptedHydrated, setAcceptedHydrated] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [manualOpen, setManualOpen] = useState(false);
  const [importOpen, setImportOpen] = useState(false);
  const displayCandidates = useMemo(
    () => [...candidates, ...(imported || [])],
    [candidates, imported],
  );

  // 步骤回显：挂载时从后端加载已保存资源（内部+外部救援），初始化到已采纳区
  useEffect(() => {
    if (!enterpriseId || acceptedHydrated) return;
    let cancelled = false;
    listResources(enterpriseId, { page_size: 200 })
      .then(res => {
        if (cancelled) return;
        setAccepted(
          (res.data.items || []).map(r => ({
            _key: `res-${r.id}`,
            ...r,
          })),
        );
      })
      .catch(() => {
        if (!cancelled) message.warning("已保存资源加载失败，仅展示当前新增项");
      })
      .finally(() => {
        if (!cancelled) {
          setAcceptedLoading(false);
          setAcceptedHydrated(true);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [enterpriseId, acceptedHydrated]);

  const handleImported = (results: ImportResult[]) => {
    const result = results[0];
    if (!result) return;
    const items: CandidateItem[] = (result.candidates || []).map((raw, i) => ({
      ...raw,
      _key: raw._key || `imp-res-${Date.now()}-${i}`,
      source: raw.source || result.source,
    }));
    onAddImported?.("resources", items);
  };

  const generate = async () => {
    setGenerating(true);
    try {
      const resp = await generateResourcesAI(enterpriseId, [
        { question_id: "q0", question: "企业概况", answer: overview },
      ]);
      const items: CandidateItem[] = (resp || []).map((c, i) => ({
        _key: `r-${Date.now()}-${i}`,
        ...(c as unknown as Record<string, unknown>),
      }));
      setCandidates(items);
    } catch (e: unknown) {
      message.error(errorDetail(e, "生成失败"));
    } finally {
      setGenerating(false);
    }
  };

  const accept = async (item: CandidateItem) => {
    try {
      // 先 await 保存成功，再移动候选到已采纳区；失败保留候选，杜绝 UI/后端不一致
      const created = await batchCreateResources(enterpriseId, [toCreatePayload(item)]);
      // 用后端返回的新 id 记录，保证取消采纳时可正确删除
      const saved = created[0]
        ? { ...item, _key: `res-${created[0].id}`, id: created[0].id }
        : item;
      if (imported?.some(x => x._key === item._key)) {
        onRemoveImported?.("resources", item._key);
      } else {
        setCandidates(prev => prev.filter(x => x._key !== item._key));
      }
      setAccepted(prev => [...prev, saved]);
      message.success(`已保存：${String(item.name || "")}`);
      queryClient.invalidateQueries({ queryKey: ["completion", enterpriseId] });
    } catch (e: unknown) {
      message.error(errorDetail(e, "保存失败，请重试"));
    }
  };

  const acceptAll = async () => {
    const items = displayCandidates;
    if (items.length === 0) return;
    try {
      const created = await batchCreateResources(enterpriseId, items.map(toCreatePayload));
      const savedItems: CandidateItem[] = items.map((item, i) => {
        const saved = created[i];
        return saved ? { ...item, _key: `res-${saved.id}`, id: saved.id } : item;
      });
      setCandidates([]);
      items.forEach(x => {
        if (imported?.some(imp => imp._key === x._key)) onRemoveImported?.("resources", x._key);
      });
      setAccepted(prev => [...prev, ...savedItems]);
      message.success(`已全部采纳：${items.length} 条`);
      queryClient.invalidateQueries({ queryKey: ["completion", enterpriseId] });
    } catch (e: unknown) {
      message.error(errorDetail(e, "批量保存失败，请重试"));
    }
  };

  const unacceptAll = async () => {
    const items = accepted;
    if (items.length === 0) return;
    try {
      for (const item of items) {
        const id = String(item.id || "");
        if (id) await deleteResource(enterpriseId, id);
      }
      setAccepted([]);
      // 移回候选区，可重新编辑后再采纳
      setCandidates(prev => [...prev, ...items]);
      message.success(`已全部取消采纳：${items.length} 条`);
      queryClient.invalidateQueries({ queryKey: ["completion", enterpriseId] });
    } catch (e: unknown) {
      message.error(errorDetail(e, "删除失败，请重试"));
    }
  };

  return (
    <div style={{ maxWidth: 760 }}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
        }}
      >
        <div>
          <h3>应急资源</h3>
          <p style={{ color: "#666", fontSize: 13 }}>
            消防设施、急救物资、外部救援力量——预案「应急保障」章节的数据来源
          </p>
        </div>
        <Space>
          <Button onClick={() => setManualOpen(true)}>✍️ 手动填写</Button>
          <Button onClick={() => setImportOpen(true)}>📄 导入现有数据</Button>
        </Space>
      </div>
      <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
        <Input.TextArea
          rows={2}
          value={overview}
          onChange={e => setOverview(e.target.value)}
          placeholder="如：车间配备干粉灭火器、正压式空气呼吸器，厂区附近有消防站"
        />
        <Button type="primary" loading={generating} onClick={generate}>
          {generating ? "AI 生成中，通常需要 1-2 分钟，请耐心等待" : "AI 生成候选"}
        </Button>
      </div>
      <CandidatesReview
        accepted={accepted}
        candidates={displayCandidates}
        renderItem={(item: CandidateItem) => (
          <div>
            <b>{String(item.name || "")}</b>{" "}
            <span style={{ color: "#999", fontSize: 12 }}>
              {item.category ? `[${String(item.category)}]` : ""}
            </span>
            <div style={{ color: "#666", fontSize: 12 }}>
              {[
                item.specification ? `规格：${String(item.specification)}` : "",
                item.quantity !== undefined ? `数量：${String(item.quantity)}${item.unit ? String(item.unit) : ""}` : "",
                item.location ? `位置：${String(item.location)}` : "",
              ].filter(Boolean).join(" · ") || "信息待补充"}
            </div>
            {item.source && (
              <div style={{ color: "#999", fontSize: 11 }}>来源：{String(item.source)}</div>
            )}
          </div>
        )}
        onAccept={accept}
        onModify={() => message.info("修改功能后续接入")}
        onDelete={(item) => {
          if (imported?.some(x => x._key === item._key)) {
            onRemoveImported?.("resources", item._key);
          } else {
            setCandidates(prev => prev.filter(x => x._key !== item._key));
          }
        }}
        onGenerateMore={generate}
        generating={generating}
        onAcceptAll={acceptAll}
        onUnacceptAll={unacceptAll}
        acceptedLoading={acceptedLoading}
      />
      <div style={{ marginTop: 20, display: "flex", justifyContent: "space-between" }}>
        <Button onClick={onPrev}>上一步</Button>
        <Button type="primary" onClick={onDone}>标记完成，下一步 →</Button>
      </div>
      <Drawer
        title="✍️ 手动填写应急资源"
        open={manualOpen}
        onClose={() => {
          setManualOpen(false);
          queryClient.invalidateQueries({ queryKey: ["completion", enterpriseId] });
        }}
        width={760}
      >
        <EmergencyResourceForm enterpriseId={enterpriseId} />
      </Drawer>
      <ImportDrawer
        enterpriseId={enterpriseId}
        open={importOpen}
        mode="single"
        module="resources"
        onClose={() => setImportOpen(false)}
        onImported={handleImported}
      />
    </div>
  );
}
