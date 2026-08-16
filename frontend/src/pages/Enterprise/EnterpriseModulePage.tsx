import { useParams } from "react-router-dom";
import { useNavigate } from "react-router-dom";
import { Spin, Button } from "antd";
import { EditOutlined } from "@ant-design/icons";
import { useQuery } from "@tanstack/react-query";
import { PageHeader } from "@/components/common/PageHeader";
import { getEnterprise } from "@/services/enterpriseService";
import type { Enterprise } from "@/types/enterprise";
import EnterpriseInfoCards from "@/components/enterprise/EnterpriseInfoCards";
import SurroundingInfoPanel from "@/components/enterprise/SurroundingInfoPanel";
import HazardousChemicalsTab from "@/pages/Enterprise/HazardousChemicalsTab";
import EmergencyResourceForm from "@/components/enterprise/EmergencyResourceForm";
import RiskAssessmentTab from "@/pages/Enterprise/RiskAssessmentTab";
import ResourceInvestigationTab from "@/pages/Enterprise/ResourceInvestigationTab";

type Ctx = { enterpriseId: string; enterprise: Enterprise };

const MODULE_MAP: Record<string, { title: string; en: string; render: (ctx: Ctx) => React.ReactNode }> = {
  info: {
    title: "基本信息", en: "ENTERPRISE ARCHIVE",
    render: ({ enterprise }) => (
      <>
        <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 8 }}>
          <EditButton />
        </div>
        <EnterpriseInfoCards enterprise={enterprise} readOnly />
      </>
    ),
  },
  surrounding: {
    title: "周边环境", en: "SURROUNDING",
    render: ({ enterpriseId, enterprise }) => (
      <SurroundingInfoPanel
        enterpriseId={enterpriseId}
        surroundingInfo={enterprise.surrounding_info || { nearby_units: [], sensitive_targets: [], traffic_info: "" }}
        onRefresh={() => undefined}
      />
    ),
  },
  chemicals: { title: "危险化学品", en: "CHEMICALS", render: ({ enterpriseId }) => <HazardousChemicalsTab enterpriseId={enterpriseId} /> },
  resources: { title: "应急资源", en: "EMERGENCY RESOURCES", render: ({ enterpriseId }) => <EmergencyResourceForm enterpriseId={enterpriseId} /> },
  assessment: { title: "风险评估报告", en: "RISK ASSESSMENT", render: ({ enterpriseId }) => <RiskAssessmentTab enterpriseId={enterpriseId} /> },
  investigation: { title: "应急资源调查报告", en: "RESOURCE INVESTIGATION", render: ({ enterpriseId }) => <ResourceInvestigationTab enterpriseId={enterpriseId} /> },
};

function EditButton() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  return <Button icon={<EditOutlined />} onClick={() => navigate(`/enterprises/${id}/edit`)}>编辑</Button>;
}

export default function EnterpriseModulePage() {
  const { id, moduleKey = "" } = useParams<{ id: string; moduleKey: string }>();
  const navigate = useNavigate();
  const mod = MODULE_MAP[moduleKey];
  const { data: enterprise, isLoading } = useQuery({
    queryKey: ["enterprise", id],
    queryFn: () => getEnterprise(id!),
    enabled: !!id,
  });

  if (!mod) return <div>模块不存在</div>;
  if (isLoading || !enterprise) return <Spin size="large" />;

  return (
    <div>
      <PageHeader
        title={mod.title}
        subtitle={mod.en}
        onBack={() => navigate(`/enterprises/${id}`)}
      />
      {mod.render({ enterpriseId: id!, enterprise })}
    </div>
  );
}
