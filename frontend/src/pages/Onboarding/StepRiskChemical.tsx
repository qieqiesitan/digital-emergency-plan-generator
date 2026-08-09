import { useState } from "react";
import { Button, Input, message } from "antd";
import { useQueryClient } from "@tanstack/react-query";
import { generateChemicalsAI, batchCreateChemicals } from "@/services/hazardousChemicalService";
import type { HazardousChemicalCreate } from "@/types/hazardousChemical";
import CandidatesReview from "./CandidatesReview";
import type { CandidateItem } from "@/types/onboarding";

interface Props {
  enterpriseId: string;
  onDone: () => void;
  onPrev: () => void;
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

export default function StepRiskChemical({ enterpriseId, onDone, onPrev }: Props) {
  const queryClient = useQueryClient();
  const [overview, setOverview] = useState("");
  const [candidates, setCandidates] = useState<CandidateItem[]>([]);
  const [accepted, setAccepted] = useState<CandidateItem[]>([]);
  const [generating, setGenerating] = useState(false);

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
      message.error((e as Error)?.message || "生成失败");
    } finally {
      setGenerating(false);
    }
  };

  const accept = async (item: CandidateItem) => {
    try {
      // 先 await 保存成功，再移动候选到已采纳区；失败保留候选，杜绝 UI/后端不一致
      await batchCreateChemicals(enterpriseId, [toCreatePayload(item)]);
      setCandidates(prev => prev.filter(x => x._key !== item._key));
      setAccepted(prev => [...prev, item]);
      message.success(`已保存：${String(item.name || "")}`);
      queryClient.invalidateQueries({ queryKey: ["completion", enterpriseId] });
    } catch (e: unknown) {
      message.error((e as Error)?.message || "保存失败，请重试");
    }
  };

  return (
    <div style={{ maxWidth: 760 }}>
      <h3>风险与危化品</h3>
      <p style={{ color: "#666", fontSize: 13 }}>企业有什么风险、存了什么危化品——事故风险描述的核心数据</p>
      <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
        <Input.TextArea
          rows={2}
          value={overview}
          onChange={e => setOverview(e.target.value)}
          placeholder="如：主要生产/储存甲醇、乙醇，有储罐区"
        />
        <Button type="primary" loading={generating} onClick={generate}>AI 生成候选</Button>
      </div>
      <CandidatesReview
        accepted={accepted}
        candidates={candidates}
        renderItem={(item: CandidateItem) => (
          <div>
            <b>{String(item.name || "")}</b>{" "}
            <span style={{ color: "#999", fontSize: 12 }}>{item.cas_no ? `CAS ${String(item.cas_no)}` : ""}</span>
            <div style={{ color: "#666", fontSize: 12 }}>{item.location ? String(item.location) : "位置待补充"}</div>
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
