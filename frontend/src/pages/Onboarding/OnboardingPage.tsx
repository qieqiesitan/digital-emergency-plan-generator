import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Button, Layout } from "antd";
import { useQuery } from "@tanstack/react-query";
import type { ComponentType } from "react";
import { getEnterpriseCompletion } from "@/services/onboardingService";
import StepEnterprise from "./StepEnterprise";
import StepOrg from "./StepOrg";
import StepRiskChemical from "./StepRiskChemical";
import StepResources from "./StepResources";
import StepSurrounding from "./StepSurrounding";
import StepGenerate from "./StepGenerate";

interface StepProps {
  enterpriseId: string;
  onDone: () => void;
  onPrev: () => void;
}

interface StepDef {
  key: string;
  label: string;
  optional?: boolean;
  component: ComponentType<StepProps>;
}

const STEPS: StepDef[] = [
  { key: "enterprise", label: "企业信息", component: StepEnterprise },
  { key: "org", label: "组织架构", component: StepOrg },
  { key: "risk", label: "风险与危化品", component: StepRiskChemical },
  { key: "resources", label: "应急资源", component: StepResources },
  { key: "surrounding", label: "周边环境", component: StepSurrounding },
  { key: "generate", label: "生成并导出预案", optional: true, component: StepGenerate },
];

export default function OnboardingPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const enterpriseId = searchParams.get("enterprise_id");
  const [current, setCurrent] = useState(0);
  const [completed, setCompleted] = useState<Set<string>>(new Set());

  const { data: completion } = useQuery({
    queryKey: ["completion", enterpriseId],
    queryFn: () => getEnterpriseCompletion(enterpriseId!),
    enabled: !!enterpriseId,
  });

  if (!enterpriseId) {
    return <div style={{ padding: 48 }}>请先选择企业（缺少 enterprise_id 参数）</div>;
  }

  const Step = STEPS[current].component;

  return (
    <Layout style={{ minHeight: "100vh", background: "#fff" }}>
      <Layout.Sider
        width={220}
        theme="light"
        style={{ borderRight: "1px solid #f0f0f0", padding: 16 }}
      >
        <div style={{ fontWeight: 600, marginBottom: 12 }}>完成企业数据</div>
        {STEPS.map((s, i) => (
          <div
            key={s.key}
            onClick={() => setCurrent(i)}
            style={{
              padding: "6px 10px",
              borderRadius: 6,
              cursor: "pointer",
              marginBottom: 2,
              background: i === current ? "#e6f4ff" : "transparent",
              fontWeight: i === current ? 600 : 400,
              color: completed.has(s.key) ? "#52c41a" : s.optional ? "#fa8c16" : "#333",
            }}
          >
            {completed.has(s.key) ? "✓ " : i === current ? "▶ " : ""}
            {i + 1} {s.label}
            {s.optional && (
              <span
                style={{
                  fontSize: 10,
                  background: "#fff7e6",
                  borderRadius: 4,
                  padding: "0 4px",
                  marginLeft: 4,
                }}
              >
                可选
              </span>
            )}
          </div>
        ))}
        <div style={{ marginTop: 16, fontSize: 12, color: "#999" }}>
          🔒 进度自动保存 · 完成度 {completion?.percent ?? 0}%
          <div style={{ marginTop: 8 }}>
            <Button size="small" onClick={() => navigate("/dashboard")}>
              稍后继续
            </Button>
          </div>
        </div>
      </Layout.Sider>
      <Layout.Content style={{ padding: 24 }}>
        <Step
          enterpriseId={enterpriseId}
          onDone={() => {
            const next = new Set(completed);
            next.add(STEPS[current].key);
            setCompleted(next);
            if (current < STEPS.length - 1) setCurrent(current + 1);
          }}
          onPrev={() => current > 0 && setCurrent(current - 1)}
        />
      </Layout.Content>
    </Layout>
  );
}
