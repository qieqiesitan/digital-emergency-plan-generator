import { useState, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { Card, Col, Row, Input, Select, Button, Space, Spin, Empty } from "antd";
import {
  BankOutlined,
  PlusOutlined,
  SafetyCertificateOutlined,
  ThunderboltOutlined,
  ToolOutlined,
  SearchOutlined,
  UnorderedListOutlined,
} from "@ant-design/icons";
import { useQuery } from "@tanstack/react-query";
import { getEnterprisePlanSummary } from "@/services/planService";
import { PageHeader } from "@/components/common/PageHeader";
import { fromNow } from "@/utils/formatters";
import { PLAN_TYPE_LABELS, PRESET_INDUSTRIES } from "@/utils/constants";

const TYPE_ICONS: Record<string, React.ReactNode> = {
  comprehensive: <SafetyCertificateOutlined />,
  special: <ThunderboltOutlined />,
  onsite: <ToolOutlined />,
};

const TYPE_COLORS: Record<string, string> = {
  comprehensive: "#1677ff",
  special: "#fa8c16",
  onsite: "#52c41a",
};

export default function PlanCardsPage() {
  const navigate = useNavigate();
  const [search, setSearch] = useState("");
  const [industry, setIndustry] = useState<string | undefined>();

  const { data: summaries, isLoading } = useQuery({
    queryKey: ["plan-enterprise-summary"],
    queryFn: getEnterprisePlanSummary,
  });

  const allItems = summaries || [];

  // client-side filter: enterprise name + industry
  const filtered = useMemo(() => {
    return allItems.filter((item) => {
      const matchSearch = !search
        || item.enterprise_name.toLowerCase().includes(search.toLowerCase());
      const matchIndustry = !industry
        || ((item as unknown as Record<string, unknown>).industry as string) === industry;
      return matchSearch && matchIndustry;
    });
  }, [allItems, search, industry]);

  return (
    <div>
      <PageHeader
        title="预案总览"
        extra={
          <Space>
            <Button
              icon={<UnorderedListOutlined />}
              onClick={() => navigate("/plans/all")}
            >
              全部预案列表
            </Button>
            <Button type="primary" icon={<PlusOutlined />} onClick={() => navigate("/plans/new")}>
              新建预案
            </Button>
          </Space>
        }
      />

      <Space style={{ marginBottom: 16 }}>
        <Input
          prefix={<SearchOutlined />}
          placeholder="搜索企业名称"
          allowClear
          style={{ width: 240 }}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <Select
          placeholder="行业筛选"
          allowClear
          style={{ width: 160 }}
          value={industry}
          onChange={setIndustry}
          options={[...PRESET_INDUSTRIES].map((i) => ({ value: i, label: i }))}
        />
      </Space>

      {isLoading ? (
        <div style={{ textAlign: "center", padding: 80 }}>
          <Spin size="large" />
        </div>
      ) : filtered.length === 0 ? (
        <Empty description={
          allItems.length === 0
            ? "暂无企业，请先创建企业"
            : "未找到匹配企业"
        } />
      ) : (
        <Row gutter={[16, 16]}>
          {filtered.map((item) => (
            <Col key={item.enterprise_id} xs={24} sm={12} lg={8} xl={6}>
              <Card
                hoverable
                onClick={() => navigate(`/enterprises/${item.enterprise_id}/plans`)}
                actions={[
                  <Button
                    type="link"
                    icon={<PlusOutlined />}
                    onClick={(e) => {
                      e.stopPropagation();
                      navigate(`/plans/new?enterprise_id=${item.enterprise_id}`);
                    }}
                  >
                    新建预案
                  </Button>,
                ]}
              >
                <Card.Meta
                  avatar={<BankOutlined style={{ fontSize: 28, color: "#1677ff" }} />}
                  title={item.enterprise_name}
                  description={
                    item.last_updated
                      ? `最近更新: ${fromNow(item.last_updated)}`
                      : "暂无预案"
                  }
                />
                <div style={{ marginTop: 16, display: "flex", justifyContent: "space-between" }}>
                  {["comprehensive", "special", "onsite"].map((type) => {
                    const countKey = `${type}_count` as keyof typeof item;
                    const count = Number(item[countKey]) || 0;
                    return (
                      <div key={type} style={{ textAlign: "center" }}>
                        <span style={{ color: TYPE_COLORS[type], fontSize: 18 }}>
                          {TYPE_ICONS[type]}
                        </span>
                        <div style={{ fontSize: 20, fontWeight: 600, color: TYPE_COLORS[type] }}>
                          {count}
                        </div>
                        <div style={{ fontSize: 12, color: "#999" }}>
                          {(PLAN_TYPE_LABELS as Record<string, string>)[type]}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </Card>
            </Col>
          ))}
        </Row>
      )}
    </div>
  );
}
