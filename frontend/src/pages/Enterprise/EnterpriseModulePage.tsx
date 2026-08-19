import { useNavigate, useParams } from "react-router-dom";
import { Spin, Button, Card, Progress, Tag, Statistic, Row, Col, Space } from "antd";
import { EditOutlined } from "@ant-design/icons";
import { useQuery } from "@tanstack/react-query";
import { PageHeader } from "@/components/common/PageHeader";
import { getEnterprise } from "@/services/enterpriseService";
import { getEnterpriseCompletion } from "@/services/onboardingService";
import type { Enterprise } from "@/types/enterprise";
import EnterpriseInfoCards from "@/components/enterprise/EnterpriseInfoCards";
import SurroundingInfoPanel from "@/components/enterprise/SurroundingInfoPanel";
import HazardousChemicalsTab from "@/pages/Enterprise/HazardousChemicalsTab";
import EmergencyResourceForm from "@/components/enterprise/EmergencyResourceForm";
import RiskAssessmentTab from "@/pages/Enterprise/RiskAssessmentTab";
import ResourceInvestigationTab from "@/pages/Enterprise/ResourceInvestigationTab";

type Ctx = { enterpriseId: string; enterprise?: Enterprise };

const MODULE_MAP: Record<string, { title: string; en: string; render: (ctx: Ctx) => React.ReactNode }> = {
  info: {
    title: "基本信息", en: "ENTERPRISE ARCHIVE",
    render: ({ enterprise }) =>
      enterprise ? (
        <>
          <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 8 }}>
            <EditButton />
          </div>
          <EnterpriseInfoCards enterprise={enterprise} readOnly />
          <EnterpriseInfoOverview enterprise={enterprise} />
        </>
      ) : (
        <div>企业信息加载失败</div>
      ),
  },
  surrounding: {
    title: "周边环境", en: "SURROUNDING",
    render: ({ enterpriseId, enterprise }) => (
      <SurroundingInfoPanel
        enterpriseId={enterpriseId}
        surroundingInfo={enterprise?.surrounding_info || { nearby_units: [], sensitive_targets: [], traffic_info: "" }}
        onRefresh={() => undefined}
      />
    ),
  },
  chemicals: { title: "危险化学品", en: "CHEMICALS", render: ({ enterpriseId }) => <HazardousChemicalsTab enterpriseId={enterpriseId} /> },
  resources: { title: "应急资源", en: "EMERGENCY RESOURCES", render: ({ enterpriseId }) => <EmergencyResourceForm enterpriseId={enterpriseId} /> },
  assessment: { title: "风险评估报告", en: "RISK ASSESSMENT", render: ({ enterpriseId }) => <RiskAssessmentTab enterpriseId={enterpriseId} /> },
  investigation: { title: "应急资源调查报告", en: "RESOURCE INVESTIGATION", render: ({ enterpriseId }) => <ResourceInvestigationTab enterpriseId={enterpriseId} /> },
};

/** 基本信息页扩容：数据完成度模块清单 + 业务统计 + GIS/平面图预览。 */
function EnterpriseInfoOverview({ enterprise }: { enterprise: Enterprise }) {
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();
  const { data: completion } = useQuery({
    queryKey: ["completion", id],
    queryFn: () => getEnterpriseCompletion(id!),
    enabled: !!id,
  });

  return (
    <div style={{ marginTop: 16 }}>
      {completion && (
        <Card title="数据完成度" size="small" style={{ marginBottom: 16 }}>
          <Progress percent={completion.percent} />
          <Space wrap style={{ marginTop: 8 }}>
            {completion.modules.map((m: { key: string; label: string; done: boolean }) => (
              <Tag key={m.key} color={m.done ? "green" : "orange"}>
                {m.label} {m.done ? "✓" : "待补充"}
              </Tag>
            ))}
          </Space>
        </Card>
      )}
      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={12} sm={6}>
          <Card hoverable size="small" onClick={() => navigate(`/enterprises/${id}/plans`)}>
            <Statistic title="应急预案" value={enterprise.plans_count ?? 0} />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card hoverable size="small" onClick={() => navigate(`/enterprises/${id}/risk-management`)}>
            <Statistic title="风险事件" value={enterprise.risk_events_count ?? 0} />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card hoverable size="small" onClick={() => navigate(`/enterprises/${id}/modules/resources`)}>
            <Statistic title="应急资源" value={enterprise.resources_count ?? 0} />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card hoverable size="small" onClick={() => navigate(`/enterprises/${id}/risk-management`)}>
            <Statistic title="风险源" value={enterprise.risk_sources_count ?? 0} />
          </Card>
        </Col>
      </Row>
      {enterprise.gis_lat != null && enterprise.gis_lng != null && (
        <Card title="GIS 定位" size="small" style={{ marginBottom: 16 }}>
          纬度 {enterprise.gis_lat.toFixed(6)} · 经度 {enterprise.gis_lng.toFixed(6)}
        </Card>
      )}
      {enterprise.floor_plan_url && (
        <Card title="厂区平面图" size="small" style={{ marginBottom: 16 }}>
          <img
            src={enterprise.floor_plan_url}
            alt="厂区平面图"
            style={{ maxWidth: 360, maxHeight: 200, border: "1px solid #d9d9d9", borderRadius: 4 }}
          />
        </Card>
      )}
    </div>
  );
}

function EditButton() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  return <Button icon={<EditOutlined />} onClick={() => navigate(`/enterprises/${id}/edit`)}>编辑</Button>;
}

export default function EnterpriseModulePage() {
  const { id, moduleKey = "" } = useParams<{ id: string; moduleKey: string }>();
  const navigate = useNavigate();
  const mod = MODULE_MAP[moduleKey];
  const needsEnterprise = moduleKey === "info" || moduleKey === "surrounding";
  const enterpriseQ = useQuery({
    queryKey: ["enterprise", id],
    queryFn: () => getEnterprise(id!),
    enabled: !!id && needsEnterprise,
  });

  if (!mod) {
    return (
      <div>
        模块不存在
        <Button type="link" onClick={() => navigate(`/enterprises/${id}`)}>返回企业驾驶舱</Button>
      </div>
    );
  }
  if (needsEnterprise && enterpriseQ.isLoading) return <Spin size="large" />;
  if (needsEnterprise && (enterpriseQ.isError || !enterpriseQ.data)) {
    return (
      <div>
        企业信息加载失败
        <Button type="link" onClick={() => enterpriseQ.refetch()}>重试</Button>
      </div>
    );
  }

  return (
    <div>
      <PageHeader
        title={mod.title}
        subtitle={mod.en}
        onBack={() => navigate(`/enterprises/${id}`)}
      />
      {mod.render({ enterpriseId: id!, enterprise: enterpriseQ.data })}
    </div>
  );
}
