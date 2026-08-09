import { useEffect, useMemo, useState } from "react";
import { Button, Drawer, Input, Space, message } from "antd";
import { useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import {
  generateChemicalsAI,
  batchCreateChemicals,
  listChemicals,
  deleteChemical,
} from "@/services/hazardousChemicalService";
import type { HazardousChemicalCreate } from "@/types/hazardousChemical";
import HazardousChemicalsTab from "@/pages/Enterprise/HazardousChemicalsTab";
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

/** 候选 dict 收窄为 HazardousChemicalCreate（全部显式字符串转换 + name 必填校验） */
function toCreatePayload(item: CandidateItem): HazardousChemicalCreate {
  const str = (v: unknown): string | undefined =>
    v === null || v === undefined || String(v).trim() === "" ? undefined : String(v);
  const name = str(item.name) || "";
  if (!name) throw new Error("候选缺少化学品名称");
  return {
    name,
    cas_no: str(item.cas_no),
    un_no: str(item.un_no),
    physical_state: str(item.physical_state),
    flash_point: str(item.flash_point),
    explosion_limit: str(item.explosion_limit),
    ignition_temp: str(item.ignition_temp),
    density: str(item.density),
    boiling_point: str(item.boiling_point),
    health_hazard: str(item.health_hazard),
    fire_hazard: str(item.fire_hazard),
    leak_response: str(item.leak_response),
    storage_transport: str(item.storage_transport),
    first_aid: str(item.first_aid),
    protective_measures: str(item.protective_measures),
    location: str(item.location),
    max_storage: str(item.max_storage),
  };
}

/** 解析请求错误：优先透出后端 detail（如 504「AI 响应超时」），其次 e.message，最后兜底文案 */
function errorDetail(e: unknown, fallback: string): string {
  if (axios.isAxiosError(e) && e.response?.data?.detail) {
    return e.response.data.detail;
  }
  return e instanceof Error && e.message ? e.message : fallback;
}

export default function StepRiskChemical({
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

  // 步骤回显：挂载时从后端加载已保存危化品，初始化到已采纳区（卸载重进后不丢失）
  useEffect(() => {
    if (!enterpriseId || acceptedHydrated) return;
    let cancelled = false;
    listChemicals(enterpriseId, { page_size: 200 })
      .then(res => {
        if (cancelled) return;
        setAccepted(
          (res.data.items || []).map(c => ({
            _key: `chem-${c.id}`,
            ...c,
          })),
        );
      })
      .catch(() => {
        if (!cancelled) message.warning("已保存危化品加载失败，仅展示当前新增项");
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
      _key: raw._key || `imp-risk-${Date.now()}-${i}`,
      source: raw.source || result.source,
    }));
    onAddImported?.("risk", items);
  };

  const generate = async () => {
    setGenerating(true);
    try {
      const resp = await generateChemicalsAI(enterpriseId, [
        { question_id: "q0", question: "企业概况", answer: overview },
      ]);
      const items: CandidateItem[] = (resp || []).map((c, i) => ({
        _key: `c-${Date.now()}-${i}`,
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
      const created = await batchCreateChemicals(enterpriseId, [toCreatePayload(item)]);
      // 用后端返回的新 id 记录，保证取消采纳时可正确删除
      const saved = created[0]
        ? { ...item, _key: `chem-${created[0].id}`, id: created[0].id }
        : item;
      if (imported?.some(x => x._key === item._key)) {
        onRemoveImported?.("risk", item._key);
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
      const created = await batchCreateChemicals(enterpriseId, items.map(toCreatePayload));
      const savedItems: CandidateItem[] = items.map((item, i) => {
        const saved = created[i];
        return saved ? { ...item, _key: `chem-${saved.id}`, id: saved.id } : item;
      });
      setCandidates([]);
      items.forEach(x => {
        if (imported?.some(imp => imp._key === x._key)) onRemoveImported?.("risk", x._key);
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
        if (id) await deleteChemical(enterpriseId, id);
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
          <h3>风险与危化品</h3>
          <p style={{ color: "#666", fontSize: 13 }}>
            企业有什么风险、存了什么危化品——事故风险描述的核心数据
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
          placeholder="如：主要生产/储存甲醇、乙醇，有储罐区"
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
            <span style={{ color: "#999", fontSize: 12 }}>{item.cas_no ? `CAS ${String(item.cas_no)}` : ""}</span>
            <div style={{ color: "#666", fontSize: 12 }}>{item.location ? String(item.location) : "位置待补充"}</div>
            {item.source && (
              <div style={{ color: "#999", fontSize: 11 }}>来源：{String(item.source)}</div>
            )}
          </div>
        )}
        onAccept={accept}
        onModify={() => message.info("修改功能后续接入")}
        onDelete={(item) => {
          if (imported?.some(x => x._key === item._key)) {
            onRemoveImported?.("risk", item._key);
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
        title="✍️ 手动填写危化品"
        open={manualOpen}
        onClose={() => {
          setManualOpen(false);
          queryClient.invalidateQueries({ queryKey: ["completion", enterpriseId] });
        }}
        width={760}
      >
        <HazardousChemicalsTab enterpriseId={enterpriseId} />
      </Drawer>
      <ImportDrawer
        enterpriseId={enterpriseId}
        open={importOpen}
        mode="single"
        module="risk_chemical"
        onClose={() => setImportOpen(false)}
        onImported={handleImported}
      />
    </div>
  );
}
