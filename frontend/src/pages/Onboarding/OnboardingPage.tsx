import { useCallback, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Button, Layout } from "antd";
import { useQuery } from "@tanstack/react-query";
import type { ComponentType } from "react";
import { getEnterpriseCompletion } from "@/services/onboardingService";
import type { CandidateItem, ImportResult } from "@/types/onboarding";
import ImportDrawer from "./ImportDrawer";
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
  /** 资料包导入后按模块分发的候选（含来源文件） */
  imported?: CandidateItem[];
  /** 步骤内单文件导入：把新候选加入本步骤导入区 */
  onAddImported?: (stepKey: string, items: CandidateItem[]) => void;
  /** 步骤采纳/删除某条导入候选后通知页面移除（空则清除挂起标记） */
  onRemoveImported?: (stepKey: string, itemKey: string) => void;
}

interface StepDef {
  key: string;
  label: string;
  optional?: boolean;
  component: ComponentType<StepProps>;
}

const MODULE_KEY_MAP: Record<string, string> = {
  enterprise: "enterprise_info",
  org: "org_structure",
  risk: "risk_chemical",
  resources: "resources",
  surrounding: "surrounding",
  generate: "reports",
};

// 全局递增序号：batch 按「文件×模块」返回多个结果，同一次调用内 Date.now() 恒定，
// 仅用候选序号会跨结果碰撞；递增计数保证 _key 跨批次/跨结果唯一
let importSeq = 0;

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
  const [localDone, setLocalDone] = useState<Set<string>>(new Set());
  const [packageOpen, setPackageOpen] = useState(false);
  // 资料包分流结果：step key → 候选（不落库，标注来源文件）
  const [importedByStep, setImportedByStep] = useState<Record<string, CandidateItem[]>>({});

  const handlePackageImported = useCallback((results: ImportResult[]) => {
    const incoming: Record<string, CandidateItem[]> = {};
    results.forEach(result => {
      const stepKey = Object.entries(MODULE_KEY_MAP).find(([, v]) => v === result.module)?.[0];
      if (!stepKey) return;
      const items = (result.candidates || []).map(raw => ({
        ...raw,
        _key: raw._key || `imp-${stepKey}-${Date.now()}-${importSeq++}`,
        source: result.source,
      }));
      incoming[stepKey] = [...(incoming[stepKey] || []), ...items];
    });
    setImportedByStep(prev => {
      const next = { ...prev };
      Object.entries(incoming).forEach(([stepKey, items]) => {
        next[stepKey] = [...(next[stepKey] || []), ...items];
      });
      return next;
    });
    setPackageOpen(false);
  }, []);

  const addImported = useCallback((stepKey: string, items: CandidateItem[]) => {
    setImportedByStep(prev => {
      const next = { ...prev };
      next[stepKey] = [...(prev[stepKey] || []), ...items];
      return next;
    });
  }, []);

  const removeImported = useCallback((stepKey: string, itemKey: string) => {
    setImportedByStep(prev => {
      const items = prev[stepKey];
      if (!items) return prev;
      const nextItems = items.filter(x => x._key !== itemKey);
      const next = { ...prev };
      if (nextItems.length === 0) delete next[stepKey];
      else next[stepKey] = nextItems;
      return next;
    });
  }, []);

  const { data: completion, isLoading } = useQuery({
    queryKey: ["completion", enterpriseId],
    queryFn: () => getEnterpriseCompletion(enterpriseId!),
    enabled: !!enterpriseId,
  });

  // completed = 后端 completion.done 模块 ∪ 本地「标记完成」的步骤，两者保持一致
  const completed = useMemo(() => {
    const done = new Set(localDone);
    completion?.modules.forEach(m => {
      if (m.done) {
        const stepKey = Object.entries(MODULE_KEY_MAP).find(([, v]) => v === m.key)?.[0];
        if (stepKey) done.add(stepKey);
      }
    });
    return done;
  }, [completion, localDone]);

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
        <Button
          block
          style={{ marginBottom: 12 }}
          onClick={() => setPackageOpen(true)}
        >
          📦 导入企业资料包
        </Button>
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
            {(importedByStep[s.key] || []).length > 0 && (
              <span
                style={{
                  fontSize: 10,
                  background: "#e6f4ff",
                  borderRadius: 4,
                  padding: "0 4px",
                  marginLeft: 4,
                }}
              >
                资料包
              </span>
            )}
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
          🔒 进度自动保存 · 完成度 {isLoading ? "–" : `${completion?.percent ?? 0}%`}
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
          imported={importedByStep[STEPS[current].key]}
          onAddImported={addImported}
          onRemoveImported={removeImported}
          onDone={() => {
            setLocalDone(prev => {
              const next = new Set(prev);
              next.add(STEPS[current].key);
              return next;
            });
            if (STEPS[current].key === "generate") {
              // 生成步骤为可选：跳过即完成引导，直接回工作台，避免 current+1 越界
              navigate("/dashboard");
            } else if (current < STEPS.length - 1) {
              setCurrent(current + 1);
            }
          }}
          onPrev={() => current > 0 && setCurrent(current - 1)}
        />
      </Layout.Content>
      <ImportDrawer
        enterpriseId={enterpriseId}
        open={packageOpen}
        mode="package"
        onClose={() => setPackageOpen(false)}
        onImported={handlePackageImported}
      />
    </Layout>
  );
}
