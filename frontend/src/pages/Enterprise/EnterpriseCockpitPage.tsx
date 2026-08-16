import { useParams, useNavigate } from "react-router-dom";
import { Spin } from "antd";
import { useQuery } from "@tanstack/react-query";
import { getEnterprise } from "@/services/enterpriseService";
import { getCockpitSummary } from "@/services/cockpitService";
import type { CockpitSummary } from "@/types/cockpit";
import CockpitBackground from "@/components/enterprise/cockpit/CockpitBackground";
import CockpitHeader from "@/components/enterprise/cockpit/CockpitHeader";
import CockpitTicker from "@/components/enterprise/cockpit/CockpitTicker";
import RiskDonutPanel from "@/components/enterprise/cockpit/RiskDonutPanel";
import RiskRadarPanel from "@/components/enterprise/cockpit/RiskRadarPanel";
import CockpitTodoPanel from "@/components/enterprise/cockpit/CockpitTodoPanel";
import CockpitCompletionPanel from "@/components/enterprise/cockpit/CockpitCompletionPanel";
import CockpitActivityPanel from "@/components/enterprise/cockpit/CockpitActivityPanel";
import ModuleNav from "@/components/enterprise/cockpit/ModuleNav";
import "@/styles/cockpit.css";

function buildTickerItems(summary: CockpitSummary, resources: number, plans: number): string[] {
  const c = summary.risk_counts;
  return [
    `风险事件 ${c.total}`, `重大 ${c.major}`, `较大 ${c.larger}`, `一般 ${c.general}`, `低 ${c.low}`,
    `待整改隐患 ${summary.hazard_counts.open}`, `应急资源 ${resources}`, `预案 ${plans}`,
    `数据完成度 ${summary.completion.percent}%`,
  ];
}

export default function EnterpriseCockpitPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const enterpriseQ = useQuery({
    queryKey: ["enterprise", id],
    queryFn: () => getEnterprise(id!),
    enabled: !!id,
  });
  const summaryQ = useQuery({
    queryKey: ["cockpit-summary", id],
    queryFn: () => getCockpitSummary(id!),
    enabled: !!id,
  });

  if (enterpriseQ.isLoading || summaryQ.isLoading) {
    return <div style={{ display: "flex", justifyContent: "center", padding: 80 }}><Spin size="large" /></div>;
  }
  if (enterpriseQ.isError || !enterpriseQ.data || summaryQ.isError || !summaryQ.data) {
    return (
      <div className="cp-page" style={{ padding: 80 }}>
        <div className="cp-error">
          驾驶舱数据加载失败
          <button className="cp-btn" style={{ marginLeft: 12 }} onClick={() => { enterpriseQ.refetch(); summaryQ.refetch(); }}>
            重试
          </button>
        </div>
      </div>
    );
  }

  const ent = enterpriseQ.data;
  const summary = summaryQ.data;
  const ticker = buildTickerItems(summary, ent.resources_count ?? 0, ent.plans_count ?? 0);

  return (
    <div className="cp-page">
      <svg width="0" height="0" style={{ position: "absolute" }} aria-hidden>
        <defs>
          <linearGradient id="cp-grad" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stopColor="#4da8ff" />
            <stop offset="1" stopColor="#00d4ff" />
          </linearGradient>
        </defs>
      </svg>
      <CockpitBackground />
      <CockpitHeader
        name={ent.name}
        industry={ent.industry}
        majorCount={summary.risk_counts.major}
        onBack={() => navigate("/enterprises")}
        onEdit={() => navigate(`/enterprises/${id}/edit`)}
      />
      <CockpitTicker items={ticker} />
      <div className="cp-grid">
        <div className="cp-col">
          <RiskDonutPanel counts={summary.risk_counts} topRisks={summary.top_risks} />
        </div>
        <div className="cp-col">
          <RiskRadarPanel riskIndex={summary.risk_index} zoneRisks={summary.zone_risks} />
        </div>
        <div className="cp-col">
          <CockpitTodoPanel todos={summary.todos} />
          <CockpitCompletionPanel completion={summary.completion} />
          <CockpitActivityPanel activities={summary.recent_activities} />
        </div>
      </div>
      <ModuleNav enterpriseId={id!} />
    </div>
  );
}
