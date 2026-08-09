import { useNavigate } from "react-router-dom";
import { Button, Progress } from "antd";
import { useQuery } from "@tanstack/react-query";
import { useCurrentEnterprise } from "@/contexts/EnterpriseContext";
import { getEnterpriseCompletion } from "@/services/onboardingService";

export default function CompletionCard() {
  const navigate = useNavigate();
  const { currentEnterpriseId } = useCurrentEnterprise();
  const { data } = useQuery({
    queryKey: ["completion", currentEnterpriseId],
    queryFn: () => getEnterpriseCompletion(currentEnterpriseId!),
    enabled: !!currentEnterpriseId,
  });
  if (!data) return null;
  const undone = (data.modules || []).filter(m => !m.done);
  return (
    <div style={{ border: "1px solid #1677ff", borderRadius: 8, padding: 16, background: "#f0f7ff", marginBottom: 24 }}>
      <div style={{ fontWeight: 600, marginBottom: 8 }}>📋 企业数据完成度 {data.percent}%</div>
      <Progress percent={data.percent} showInfo={false} strokeColor="#1677ff" />
      <div style={{ fontSize: 13, color: "#555", margin: "8px 0" }}>
        {undone.length === 0
          ? "已完成全部数据模块，可以生成预案了"
          : `未完成：${undone.map(m => m.label).join("、")}`}
      </div>
      <Button
        type="primary"
        onClick={() => navigate(undone.length === 0 ? `/plans/new?enterprise_id=${currentEnterpriseId}` : `/onboarding?enterprise_id=${currentEnterpriseId}`)}
      >
        {undone.length === 0 ? "去生成预案" : "继续补数据"}
      </Button>
    </div>
  );
}
