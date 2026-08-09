import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "antd";
import { PLAN_TYPE_LABELS } from "@/utils/constants";

interface Props {
  enterpriseId: string;
  onDone: () => void;
  onPrev: () => void;
}

const PLAN_TYPES = ["comprehensive", "special", "onsite"] as const;
type PlanType = (typeof PLAN_TYPES)[number];

export default function StepGenerate({ enterpriseId, onPrev }: Props) {
  const navigate = useNavigate();
  const [type, setType] = useState<PlanType>("comprehensive");
  return (
    <div style={{ maxWidth: 760 }}>
      <h3>生成并导出预案（可选）</h3>
      <p style={{ color: "#666", fontSize: 13 }}>
        数据已就绪，可以生成第一份预案；也可以稍后从工作台随时开始
      </p>
      <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
        {PLAN_TYPES.map(t => (
          <Button
            key={t}
            type={type === t ? "primary" : "default"}
            onClick={() => setType(t)}
            style={{ flex: 1, height: 64 }}
          >
            {PLAN_TYPE_LABELS[t]}
          </Button>
        ))}
      </div>
      <div style={{ display: "flex", justifyContent: "space-between" }}>
        <Button onClick={onPrev}>上一步</Button>
        <Button
          type="primary"
          onClick={() => navigate(`/plans/new?type=${type}&enterprise_id=${enterpriseId}`)}
        >
          现在生成预案
        </Button>
      </div>
    </div>
  );
}
