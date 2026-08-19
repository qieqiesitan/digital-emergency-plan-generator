import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Card, Row, Col, Statistic, List, Typography, Button, Skeleton, Empty, Modal, Input, Select, Tag, Progress, Space } from "antd";
import {
  BankOutlined,
  FileTextOutlined,
  CheckCircleOutlined,
  WarningOutlined,
  PlusOutlined,
  RightOutlined,
} from "@ant-design/icons";
import { useQuery } from "@tanstack/react-query";
import { getDashboard } from "@/services/dashboardService";
import { listEnterprises } from "@/services/enterpriseService";
import { PlanTypeTag } from "@/components/plan/PlanTypeTag";
import { PlanStatusTag } from "@/components/plan/PlanStatusTag";
import { fromNow } from "@/utils/formatters";
import type { PlanType } from "@/types/plan";
import type { Enterprise } from "@/types/enterprise";

const { Title } = Typography;

const QUICK_CREATE_ITEMS = [
  { type: "comprehensive" as PlanType, label: "综合应急预案", desc: "企业整体应急框架" },
  { type: "special" as PlanType, label: "专项应急预案", desc: "针对特定事故类型" },
  { type: "onsite" as PlanType, label: "现场处置方案", desc: "一线操作卡片" },
];

export default function DashboardPage() {
  const navigate = useNavigate();
  const [modalOpen, setModalOpen] = useState(false);
  const [selectedType, setSelectedType] = useState<PlanType | null>(null);
  const [modalSearch, setModalSearch] = useState("");
  const [modalIndustry, setModalIndustry] = useState<string | undefined>(undefined);

  const { data, isLoading } = useQuery({
    queryKey: ["dashboard"],
    queryFn: getDashboard,
  });

  const { data: enterprisePage, isLoading: enterprisesLoading } = useQuery({
    queryKey: ["enterprises", "quick-create"],
    queryFn: () => listEnterprises({ page: 1, page_size: 100 }),
  });

  const enterprises = useMemo(() => enterprisePage?.data?.items ?? [], [enterprisePage]);

  const industries = useMemo(
    () => [...new Set(enterprises.map(e => e.industry).filter(Boolean))].sort(),
    [enterprises],
  );

  const filteredEnterprises = useMemo(() => {
    const keyword = modalSearch.trim().toLowerCase();
    return enterprises.filter(e => {
      if (modalIndustry && e.industry !== modalIndustry) return false;
      if (!keyword) return true;
      return [e.name, e.industry, e.address].some(v => (v || "").toLowerCase().includes(keyword));
    });
  }, [enterprises, modalSearch, modalIndustry]);

  if (isLoading) {
    return <Skeleton active paragraph={{ rows: 8 }} />;
  }

  if (!data || data.stats.enterprise_count === 0) {
    return (
      <Empty description="还没有企业数据">
        <Button type="primary" icon={<PlusOutlined />} onClick={() => navigate("/enterprises/new")}>
          创建第一个企业
        </Button>
      </Empty>
    );
  }

  const stats = data.stats;

  const handleSelectEnterprise = (enterpriseId: string) => {
    setModalOpen(false);
    navigate(`/plans/new?type=${selectedType}&enterprise_id=${enterpriseId}`);
  };

  const openQuickCreate = (type: PlanType) => {
    setSelectedType(type);
    setModalSearch("");
    setModalIndustry(undefined);
    setModalOpen(true);
  };

  return (
    <div>
      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={12} sm={6}>
          <Card hoverable onClick={() => navigate("/enterprises")}>
            <Statistic title="企业数" value={stats.enterprise_count} prefix={<BankOutlined />} />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card hoverable onClick={() => navigate("/plans")}>
            <Statistic title="预案总数" value={stats.plan_count} prefix={<FileTextOutlined />} />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card>
            <Statistic
              title="已完成"
              value={stats.completed_plan_count}
              suffix={`/ ${stats.plan_count}`}
              prefix={<CheckCircleOutlined />}
              valueStyle={{ color: "#52c41a" }}
            />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card>
            <Statistic title="风险事件数" value={stats.risk_event_count} prefix={<WarningOutlined />} />
          </Card>
        </Col>
      </Row>

      <Title level={5} style={{ marginBottom: 16 }}>快捷新建预案</Title>
      <Row gutter={[16, 16]} style={{ marginBottom: 32 }}>
        {QUICK_CREATE_ITEMS.map((item) => (
          <Col xs={24} sm={8} key={item.type}>
            <Card hoverable onClick={() => openQuickCreate(item.type)}>
              <PlanTypeTag type={item.type} />
              <div style={{ marginTop: 8, fontWeight: 500 }}>{item.label}</div>
              <div style={{ color: "#999", fontSize: 13 }}>{item.desc}</div>
            </Card>
          </Col>
        ))}
      </Row>

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <Title level={5} style={{ margin: 0 }}>企业概览</Title>
        <Button type="link" onClick={() => navigate("/enterprises")}>进入企业管理 →</Button>
      </div>
      {enterprises.length === 0 ? (
        <Empty description="暂无企业">
          <Button type="primary" icon={<PlusOutlined />} onClick={() => navigate("/enterprises/new")}>
            创建第一个企业
          </Button>
        </Empty>
      ) : (
        <Row gutter={[16, 16]} style={{ marginBottom: 32 }}>
          {enterprises.map((ent) => (
            <Col xs={24} sm={12} lg={8} key={ent.id}>
              <Card
                hoverable
                onClick={() => navigate(`/enterprises/${ent.id}`)}
                styles={{ body: { padding: 16 } }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                  <div style={{ fontWeight: 600, fontSize: 15 }}>{ent.name}</div>
                  {ent.industry && <Tag color="blue">{ent.industry}</Tag>}
                </div>
                <div style={{ color: "#999", fontSize: 12, margin: "6px 0 12px", minHeight: 32 }}>
                  {ent.address || "未设置地址"}
                </div>
                <div style={{ marginBottom: 8 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, color: "#666", marginBottom: 2 }}>
                    <span>数据完成度</span>
                    <span>{ent.completion?.percent ?? 0}%</span>
                  </div>
                  <Progress percent={ent.completion?.percent ?? 0} showInfo={false} size="small" strokeColor="#1677ff" />
                </div>
                <div style={{ display: "flex", gap: 12, fontSize: 12, color: "#666", marginBottom: 12 }}>
                  <span>预案 {ent.plans_count ?? 0}</span>
                  <span>风险事件 {ent.risk_events_count ?? 0}</span>
                  <span>应急资源 {ent.resources_count ?? 0}</span>
                </div>
                <Space wrap>
                  <Button size="small" type="primary" ghost onClick={(e) => { e.stopPropagation(); navigate(`/enterprises/${ent.id}`); }}>
                    进入驾驶舱
                  </Button>
                  <Button size="small" onClick={(e) => { e.stopPropagation(); navigate(`/plans/new?enterprise_id=${ent.id}`); }}>
                    新建预案
                  </Button>
                  <Button size="small" onClick={(e) => { e.stopPropagation(); navigate(`/enterprises/${ent.id}/edit`); }}>
                    编辑信息
                  </Button>
                </Space>
              </Card>
            </Col>
          ))}
        </Row>
      )}

      <Title level={5} style={{ marginBottom: 16 }}>最近编辑</Title>
      <List
        dataSource={data.recent_plans}
        renderItem={(item) => (
          <List.Item
            style={{ cursor: "pointer" }}
            onClick={() => navigate(`/plans/${item.id}/edit`)}
            extra={<PlanStatusTag status={item.status as "draft" | "generating" | "completed"} />}
          >
            <List.Item.Meta
              title={
                <span>
                  <PlanTypeTag type={item.plan_type as PlanType} />
                  {" "}{item.title}
                </span>
              }
              description={`${item.enterprise_name} · ${item.completed_sections}/${item.total_sections} 章节 · ${fromNow(item.updated_at)}`}
            />
          </List.Item>
        )}
        locale={{ emptyText: "暂无预案" }}
      />

      <Modal
        title={`选择企业 — 新建${QUICK_CREATE_ITEMS.find(i => i.type === selectedType)?.label ?? "预案"}`}
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        footer={null}
        width={480}
        destroyOnClose
      >
        <Space style={{ width: "100%", marginBottom: 12 }} wrap>
          <Input
            allowClear
            placeholder="搜索企业名称/行业/地址"
            value={modalSearch}
            onChange={e => setModalSearch(e.target.value)}
            style={{ width: 220 }}
          />
          <Select
            allowClear
            placeholder="行业筛选"
            style={{ width: 150 }}
            value={modalIndustry}
            options={industries.map(i => ({ label: i, value: i }))}
            onChange={setModalIndustry}
          />
        </Space>
        {enterprisesLoading ? (
          <Skeleton active paragraph={{ rows: 4 }} />
        ) : enterprises.length === 0 ? (
          <Empty description="暂无企业" />
        ) : (
          <List
            dataSource={filteredEnterprises}
            locale={{ emptyText: <Empty description="无匹配企业" /> }}
            renderItem={(enterprise: Enterprise) => (
              <List.Item
                style={{ cursor: "pointer", padding: "12px 8px" }}
                onClick={() => handleSelectEnterprise(enterprise.id)}
              >
                <List.Item.Meta
                  title={
                    <span>
                      <BankOutlined style={{ marginRight: 8 }} />
                      {enterprise.name}
                    </span>
                  }
                  description={enterprise.industry || "未设置行业"}
                />
                <RightOutlined style={{ color: "#bbb" }} />
              </List.Item>
            )}
          />
        )}
      </Modal>
    </div>
  );
}
