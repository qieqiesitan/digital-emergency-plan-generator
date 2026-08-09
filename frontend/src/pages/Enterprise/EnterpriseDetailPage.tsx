import { useState } from "react";
import { useParams, useNavigate, useSearchParams } from "react-router-dom";
import { Tabs, Button, Spin, Table, Collapse, Image, Badge, Descriptions } from "antd";
import type { TabsProps } from "antd";
import { EditOutlined } from "@ant-design/icons";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { getEnterprise } from "@/services/enterpriseService";
import { getRiskAssessment } from "@/services/riskAssessmentService";
import { getResourceInvestigation } from "@/services/resourceInvestigationService";
import { listEnterpriseFloors } from "@/services/riskMappingWorkbenchService";
import { PageHeader } from "@/components/common/PageHeader";
import EnterpriseInfoCards from "@/components/enterprise/EnterpriseInfoCards";
import OrgStructureEditor from "@/components/enterprise/OrgStructureEditor";
import EmergencyResourceForm from "@/components/enterprise/EmergencyResourceForm";
import SurroundingInfoPanel from "@/components/enterprise/SurroundingInfoPanel";
import RiskAssessmentTab from "@/pages/Enterprise/RiskAssessmentTab";
import ResourceInvestigationTab from "@/pages/Enterprise/ResourceInvestigationTab";
import HazardousChemicalsTab from "@/pages/Enterprise/HazardousChemicalsTab";
import RiskManagementTab from "./RiskManagementTab";
import type { OrgGroup, OrgMember, SurroundingInfo } from "@/types/enterprise";

const ROLE_LABELS: Record<string, string> = { chief: "总指挥", deputy: "副总指挥", leader: "组长", member: "成员" };

type ReportStatus = "none" | "draft" | "completed";

const REPORT_BADGES: Record<ReportStatus, { text: string; color: string }> = {
  none: { text: "未生成", color: "orange" },
  draft: { text: "待合并", color: "orange" },
  completed: { text: "已完成", color: "green" },
};

function toBadgeStatus(
  status: "draft" | "generating" | "completed" | undefined,
  isError: boolean,
): ReportStatus {
  if (isError || !status) return "none";
  // 后端 GET 仅返回 completed/draft；generating 为不可达过渡态，按待合并展示
  return status === "generating" ? "draft" : status;
}

function reportBadge(label: string, status: ReportStatus) {
  const { text, color } = REPORT_BADGES[status];
  return (
    <span style={{ whiteSpace: "nowrap" }}>
      {label} <Badge color={color} text={text} />
    </span>
  );
}

type OrgMemberRow = OrgMember & { _key?: string };

function memberRowKey(r: OrgMemberRow): string {
  if (!r._key) r._key = crypto.randomUUID?.() || `k-${Math.random()}`;
  return r._key;
}

export default function EnterpriseDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const queryClient = useQueryClient();

  const [orgEditorVisible, setOrgEditorVisible] = useState(false);

  const { data: enterprise, isLoading } = useQuery({
    queryKey: ["enterprise", id],
    queryFn: () => getEnterprise(id!),
    enabled: !!id,
  });

  const { data: floors } = useQuery({
    queryKey: ["enterprise-floors", id],
    queryFn: () => listEnterpriseFloors(id!),
    enabled: !!id,
  });

  const { isError: raIsError, data: raReport } = useQuery({
    queryKey: ["enterprise", id, "risk-assessment"],
    queryFn: () => getRiskAssessment(id!),
    enabled: !!id,
    retry: false,
    refetchOnWindowFocus: true,
  });
  const { isError: riIsError, data: riReport } = useQuery({
    queryKey: ["enterprise", id, "resource-investigation"],
    queryFn: () => getResourceInvestigation(id!),
    enabled: !!id,
    retry: false,
    refetchOnWindowFocus: true,
  });

  const raStatus = toBadgeStatus(raReport?.status, raIsError);
  const riStatus = toBadgeStatus(riReport?.status, riIsError);

  if (isLoading) return <Spin size="large" />;
  if (!enterprise) return <div>企业不存在</div>;

  const orgGroups: OrgGroup[] = enterprise.org_structure || [];
  // 优先使用默认楼层平面图，接口未就绪/无默认楼层时回退企业字段
  const defaultFloor = floors?.find(f => f.is_default);
  const floorPlanUrl = defaultFloor?.floor_plan_url ?? enterprise.floor_plan_url;
  const surroundingInfo: SurroundingInfo = enterprise.surrounding_info || {
    nearby_units: [],
    sensitive_targets: [],
    traffic_info: "",
  };

  // antd 6.4 的 Tabs items 不支持 type: "group"，用「禁用 tab + 分组标题样式 + 虚线分隔」等价呈现分组
  const groupItem = (label: string) => ({
    key: `group-${label}`,
    disabled: true,
    label: (
      <span
        style={{
          display: "inline-block",
          color: "#999",
          fontSize: 12,
          fontWeight: 600,
          letterSpacing: 1,
          borderTop: "1px dashed #e5e5e5",
          paddingTop: 6,
          marginTop: 6,
        }}
      >
        {label}
      </span>
    ),
  });

  const tabItems: TabsProps["items"] = [
    groupItem("数据录入"),
    {
      key: "info",
      label: "基本信息",
      children: (
        <>
          <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 8 }}>
            <Button icon={<EditOutlined />} onClick={() => navigate(`/enterprises/${id}/edit`)}>
              编辑
            </Button>
          </div>
          <EnterpriseInfoCards enterprise={enterprise} readOnly />
          {enterprise.gis_lat != null && enterprise.gis_lng != null && (
            <Descriptions column={2} bordered size="small" title="GIS 定位" style={{ marginTop: 16 }}>
              <Descriptions.Item label="GIS 坐标" span={2}>
                {enterprise.gis_lat.toFixed(6)}, {enterprise.gis_lng.toFixed(6)}
              </Descriptions.Item>
            </Descriptions>
          )}
          {enterprise.floor_plan_url && (
            <div style={{ marginTop: 16 }}>
              <div style={{ fontWeight: 500, marginBottom: 8 }}>厂区平面图</div>
              <Image src={enterprise.floor_plan_url} width={400} />
            </div>
          )}
        </>
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
                rowKey={memberRowKey}
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
      key: "chemicals",
      label: "危险化学品",
      children: <HazardousChemicalsTab enterpriseId={id!} />,
    },
    {
      key: "risk-management",
      label: "风险分级管控",
      children: <RiskManagementTab enterpriseId={id!} floorPlanUrl={floorPlanUrl} />,
    },
    groupItem("报告生成"),
    {
      key: "risk-assessment",
      label: reportBadge("风险评估", raStatus),
      children: <RiskAssessmentTab enterpriseId={id!} />,
    },
    {
      key: "resource-investigation",
      label: reportBadge("应急资源调查", riStatus),
      children: <ResourceInvestigationTab enterpriseId={id!} />,
    },
  ];

  const requestedTab = searchParams.get("tab");

  return (
    <div>
      <PageHeader title={enterprise.name} onBack={() => navigate("/enterprises")} />
      <Tabs
        items={tabItems}
        activeKey={tabItems.some(t => t.key === requestedTab && !t.disabled) ? requestedTab! : "info"}
        onChange={key => setSearchParams({ tab: key }, { replace: true })}
      />
    </div>
  );
}
