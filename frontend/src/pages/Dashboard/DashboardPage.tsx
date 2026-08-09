import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Card, Row, Col, Statistic, List, Typography, Button, Skeleton, Empty, Modal } from "antd";
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
import CompletionCard from "./CompletionCard";

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

  const { data, isLoading } = useQuery({
    queryKey: ["dashboard"],
    queryFn: getDashboard,
  });

  const { data: enterprisePage, isLoading: enterprisesLoading } = useQuery({
    queryKey: ["enterprises", "quick-create"],
    queryFn: () => listEnterprises({ page: 1, page_size: 100 }),
  });

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
  const enterprises = enterprisePage?.data?.items ?? [];

  const handleQuickCreate = (type: PlanType) => {
    setSelectedType(type);
    setModalOpen(true);
  };

  const handleSelectEnterprise = (enterpriseId: string) => {
    setModalOpen(false);
    navigate(`/plans/new?type=${selectedType}&enterprise_id=${enterpriseId}`);
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

      <CompletionCard />

      <Title level={5} style={{ marginBottom: 16 }}>快捷新建</Title>
      <Row gutter={[16, 16]} style={{ marginBottom: 32 }}>
        {QUICK_CREATE_ITEMS.map((item) => (
          <Col xs={24} sm={8} key={item.type}>
            <Card hoverable onClick={() => handleQuickCreate(item.type)}>
              <PlanTypeTag type={item.type} />
              <div style={{ marginTop: 8, fontWeight: 500 }}>{item.label}</div>
              <div style={{ color: "#999", fontSize: 13 }}>{item.desc}</div>
            </Card>
          </Col>
        ))}
      </Row>

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
        title="选择企业"
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        footer={null}
        width={480}
        destroyOnClose
      >
        {enterprisesLoading ? (
          <Skeleton active paragraph={{ rows: 4 }} />
        ) : enterprises.length === 0 ? (
          <Empty description="暂无企业" />
        ) : (
          <List
            dataSource={enterprises}
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
