import { useState } from "react";
import { Button, Input, message } from "antd";
import { useQueryClient } from "@tanstack/react-query";
import { generateResourcesAI, batchCreateResources } from "@/services/emergencyResourceService";
import type { EmergencyResourceCreate } from "@/types/emergencyResource";
import CandidatesReview from "./CandidatesReview";
import type { CandidateItem } from "@/types/onboarding";

interface Props {
  enterpriseId: string;
  onDone: () => void;
  onPrev: () => void;
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

export default function StepResources({ enterpriseId, onDone, onPrev }: Props) {
  const queryClient = useQueryClient();
  const [overview, setOverview] = useState("");
  const [candidates, setCandidates] = useState<CandidateItem[]>([]);
  const [accepted, setAccepted] = useState<CandidateItem[]>([]);
  const [generating, setGenerating] = useState(false);

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
      message.error((e as Error)?.message || "生成失败");
    } finally {
      setGenerating(false);
    }
  };

  const accept = async (item: CandidateItem) => {
    setCandidates(prev => prev.filter(x => x._key !== item._key));
    setAccepted(prev => [...prev, item]);
    try {
      await batchCreateResources(enterpriseId, [toCreatePayload(item)]);
      message.success(`已保存：${String(item.name || "")}`);
      queryClient.invalidateQueries({ queryKey: ["completion", enterpriseId] });
    } catch (e: unknown) {
      message.error((e as Error)?.message || "保存失败");
    }
  };

  return (
    <div style={{ maxWidth: 760 }}>
      <h3>应急资源</h3>
      <p style={{ color: "#666", fontSize: 13 }}>消防设施、急救物资、外部救援力量——预案「应急保障」章节的数据来源</p>
      <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
        <Input.TextArea
          rows={2}
          value={overview}
          onChange={e => setOverview(e.target.value)}
          placeholder="如：车间配备干粉灭火器、正压式空气呼吸器，厂区附近有消防站"
        />
        <Button type="primary" loading={generating} onClick={generate}>AI 生成候选</Button>
      </div>
      <CandidatesReview
        accepted={accepted}
        candidates={candidates}
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
          </div>
        )}
        onAccept={accept}
        onModify={() => message.info("修改功能后续接入")}
        onDelete={(item) => setCandidates(prev => prev.filter(x => x._key !== item._key))}
        onGenerateMore={generate}
        generating={generating}
      />
      <div style={{ marginTop: 20, display: "flex", justifyContent: "space-between" }}>
        <Button onClick={onPrev}>上一步</Button>
        <Button type="primary" onClick={onDone}>标记完成，下一步 →</Button>
      </div>
    </div>
  );
}
