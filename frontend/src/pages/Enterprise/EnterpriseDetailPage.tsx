import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Tabs, Card, Descriptions, Button, Spin, Table, Collapse, Space, message, Image, Badge } from "antd";
import { EditOutlined, PlusOutlined } from "@ant-design/icons";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { getEnterprise } from "@/services/enterpriseService";
import { PageHeader } from "@/components/common/PageHeader";
import { RiskLevelTag } from "@/components/enterprise/RiskLevelTag";
import { formatDate } from "@/utils/formatters";
import { PRESET_EMERGENCY_GROUPS } from "@/utils/constants";
import OrgStructureEditor from "@/components/enterprise/OrgStructureEditor";
import RiskSourceForm from "@/components/enterprise/RiskSourceForm";
import EmergencyResourceForm from "@/components/enterprise/EmergencyResourceForm";
import SurroundingInfoPanel from "@/components/enterprise/SurroundingInfoPanel";
import RiskAssessmentTab from "@/pages/Enterprise/RiskAssessmentTab";
import ResourceInvestigationTab from "@/pages/Enterprise/ResourceInvestigationTab";
import HazardousChemicalsTab
import RiskManagementTab from './RiskManagementTab' from "@/pages/Enterprise/HazardousChemicalsTab";
import type { OrgGroup, SurroundingInfo } from "@/types/enterprise";
import type { RiskSource } from "@/types/riskSource";
import type { EmergencyResource } from "@/types/emergencyResource";

const ROLE_LABELS: Record<string, string> = { chief: "总指挥", deputy: "副总指挥", leader: "组长", member: "成员" };

export default function EnterpriseDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [orgEditorVisible, setOrgEditorVisible] = useState(false);

  const { data: enterprise, isLoading } = useQuery({
    queryKey: ["enterprise", id],
    queryFn: () => getEnterprise(id!),
    enabled: !!id,
  });

  if (isLoading) return <Spin size="large" />;
  if (!enterprise) return <div>企业不存在</div>;

  const orgGroups: OrgGroup[] = enterprise.org_structure || [];
  const surroundingInfo: SurroundingInfo = enterprise.surrounding_info || {
    nearby_units: [],
    sensitive_targets: [],
    traffic_info: "",
  };

  const tabItems = [
    {
      key: "info",
      label: "基本信息",
      children: (
        <Card extra={<Button icon={<EditOutlined />} onClick={() => navigate(`/enterprises/${id}/edit`)}>编辑</Button>}>
          <Descriptions column={2} bordered size="small" title="法定基本资料">
            <Descriptions.Item label="企业名称">{enterprise.name}</Descriptions.Item>
            <Descriptions.Item label="统一社会信用代码">{enterprise.credit_code || "-"}</Descriptions.Item>
            <Descriptions.Item label="法定代表人">{enterprise.legal_representative || "-"}</Descriptions.Item>
            <Descriptions.Item label="经济类型">{enterprise.economic_type || "-"}</Descriptions.Item>
            <Descriptions.Item label="成立日期">{enterprise.established_date || "-"}</Descriptions.Item>
            <Descriptions.Item label="注册资本（万元）">{enterprise.registered_capital ?? "-"}</Descriptions.Item>
            <Descriptions.Item label="经营范围" span={2}>{enterprise.business_scope || "-"}</Descriptions.Item>
          </Descriptions>

          <Descriptions column={2} bordered size="small" title="联系与场地信息" style={{ marginTop: 16 }}>
            <Descriptions.Item label="地址">{enterprise.address || "-"}</Descriptions.Item>
            <Descriptions.Item label="行业">{enterprise.industry || "-"}</Descriptions.Item>
            <Descriptions.Item label="联系电话">{enterprise.phone || "-"}</Descriptions.Item>
            <Descriptions.Item label="传真">{enterprise.fax || "-"}</Descriptions.Item>
            <Descriptions.Item label="邮政编码">{enterprise.postal_code || "-"}</Descriptions.Item>
            <Descriptions.Item label="员工人数">{enterprise.employee_count ?? "-"}</Descriptions.Item>
            <Descriptions.Item label="占地面积（㎡）">{enterprise.land_area ?? "-"}</Descriptions.Item>
            <Descriptions.Item label="建筑面积（㎡）">{enterprise.building_area ?? "-"}</Descriptions.Item>
            <Descriptions.Item label="建筑/厂区概况" span={2}>{enterprise.building_overview || "-"}</Descriptions.Item>
          </Descriptions>

          <Descriptions column={2} bordered size="small" title="安全管理与合规" style={{ marginTop: 16 }}>
            <Descriptions.Item label="安全负责人">{enterprise.safety_officer || "-"}</Descriptions.Item>
            <Descriptions.Item label="安全负责人电话">{enterprise.safety_officer_phone || "-"}</Descriptions.Item>
            <Descriptions.Item label="安全管理人员数">{enterprise.safety_staff_count ?? "-"}</Descriptions.Item>
            <Descriptions.Item label="安全标准化等级">{enterprise.safety_standardization || "-"}</Descriptions.Item>
            <Descriptions.Item label="消防验收">{enterprise.fire_approval || "-"}</Descriptions.Item>
            <Descriptions.Item label="消防验收日期">{enterprise.fire_approval_date || "-"}</Descriptions.Item>
            <Descriptions.Item label="上次备案日期">{enterprise.last_plan_filing_date || "-"}</Descriptions.Item>
            <Descriptions.Item label="上次备案部门">{enterprise.last_plan_filing_authority || "-"}</Descriptions.Item>
          </Descriptions>

          <Descriptions column={2} bordered size="small" title="生产与物料信息" style={{ marginTop: 16 }}>
            <Descriptions.Item label="主要产品" span={2}>{enterprise.main_products || "-"}</Descriptions.Item>
            <Descriptions.Item label="年生产能力" span={2}>{enterprise.annual_capacity || "-"}</Descriptions.Item>
            <Descriptions.Item label="危险化学品" span={2}>{enterprise.hazardous_chemicals || "-"}</Descriptions.Item>
            <Descriptions.Item label="特种设备" span={2}>{enterprise.special_equipment || "-"}</Descriptions.Item>
          </Descriptions>

          {enterprise.gis_lat != null && enterprise.gis_lng != null && (
            <Descriptions column={2} bordered size="small" title="GIS 定位" style={{ marginTop: 16 }}>
              <Descriptions.Item label="GIS 坐标" span={2}>
                {enterprise.gis_lat.toFixed(6)}, {enterprise.gis_lng.toFixed(6)}
              </Descriptions.Item>
            </Descriptions>
          )}
          <Descriptions column={2} bordered size="small" title="系统信息" style={{ marginTop: 16 }}>
            <Descriptions.Item label="创建时间">{formatDate(enterprise.created_at)}</Descriptions.Item>
            <Descriptions.Item label="更新时间">{formatDate(enterprise.updated_at)}</Descriptions.Item>
          </Descriptions>
          {enterprise.floor_plan_url && (
            <div style={{ marginTop: 16 }}>
              <div style={{ fontWeight: 500, marginBottom: 8 }}>厂区平面图</div>
              <Image src={enterprise.floor_plan_url} width={400} />
            </div>
          )}
        </Card>
      ),
    },
    {
      key: "org",
      label: <span>组织架构 <Badge count={orgGroups.length} style={{ marginLeft: 4 }} /></span>,
      children: (
        <div>
          <div style={{ marginBottom: 16 }}>
            <Button
              type="primary"
              icon={<EditOutlined />}
              onClick={() => setOrgEditorVisible(true)}
            >
              编辑组织架构
            </Button>
          </div>
          <Collapse items={orgGroups.map((g) => ({
            key: g.group_key,
            label: `${g.group_name} (${g.members.length}人)`,
            children: (
              <Table
                dataSource={g.members}
                rowKey={(r: any) => (r as any)._key || ((r as any)._key = crypto.randomUUID?.() || `k-${Math.random()}`)}
                pagination={false}
                columns={[
                  { title: "角色", dataIndex: "role", render: (v: string) => ROLE_LABELS[v] || v },
                  { title: "姓名", dataIndex: "name" },
                  { title: "公司职位", dataIndex: "position" },
                  { title: "电话", dataIndex: "phone" },
                ]}
              />
            ),
          }))} />
          <OrgStructureEditor
            enterpriseId={id!}
            orgStructure={orgGroups}
            visible={orgEditorVisible}
            onClose={() => {
              setOrgEditorVisible(false);
              queryClient.invalidateQueries({ queryKey: ["enterprise", id] });
            }}
          />
        </div>
      ),
    },
    {
      key: "risk-sources",
      label: <span>风险源 <Badge count={enterprise.risk_sources_count} style={{ marginLeft: 4 }} /></span>,
      children: <RiskSourceForm enterpriseId={id!} floorPlanUrl={enterprise.floor_plan_url} />,
    },
    {
      key: "resources",
      label: <span>应急资源 <Badge count={enterprise.resources_count} style={{ marginLeft: 4 }} /></span>,
      children: <EmergencyResourceForm enterpriseId={id!} />,
    },
    {
      key: "surrounding",
      label: "周边环境",
      children: (
        <SurroundingInfoPanel
          enterpriseId={id!}
          surroundingInfo={surroundingInfo}
          onRefresh={() => queryClient.invalidateQueries({ queryKey: ["enterprise", id] })}
        />
      ),
    },
    {
      key: "risk-assessment",
      label: "风险评估",
      children: <RiskAssessmentTab enterpriseId={id!} />,
    },
    {
      key: "resource-investigation",
      label: "应急资源调查",
      children: <ResourceInvestigationTab enterpriseId={id!} />,
    },
    {
      key: "chemicals",
      label: "危险化学品",
      children: <HazardousChemicalsTab enterpriseId={id!} />,
    },
  ];

  return (
    <div>
      <PageHeader title={enterprise.name} onBack={() => navigate("/enterprises")} />
      <Tabs items={tabItems} />
    </div>
  );
}

