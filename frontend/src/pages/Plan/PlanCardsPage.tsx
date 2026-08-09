import { useState, useMemo, useRef, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Card, Col, Row, Input, Select, Button, Space, Spin, Empty } from "antd";
import { Segmented, Table, Progress } from "antd";
import type { TableColumnsType } from "antd";
import {
  BankOutlined,
  PlusOutlined,
  SafetyCertificateOutlined,
  ThunderboltOutlined,
  ToolOutlined,
  SearchOutlined,
} from "@ant-design/icons";
import { useQuery } from "@tanstack/react-query";
import { getEnterprisePlanSummary, listPlans } from "@/services/planService";
import { PageHeader } from "@/components/common/PageHeader";
import { fromNow } from "@/utils/formatters";
import { PLAN_TYPE_LABELS, PRESET_INDUSTRIES } from "@/utils/constants";
import { PlanTypeTag } from "@/components/plan/PlanTypeTag";
import { PlanStatusTag } from "@/components/plan/PlanStatusTag";
import type { PlanProject, PlanStatus } from "@/types/plan";

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

function PlanListTable({
  listSearch,
  listPage,
  onPageChange,
}: {
  listSearch: string;
  listPage: number;
  onPageChange: (page: number) => void;
}) {
  const navigate = useNavigate();
  const listQuery = useQuery({
    queryKey: ["plans", "list", listPage, listSearch],
    queryFn: () => listPlans({ page: listPage, page_size: 20, search: listSearch || undefined }),
  });

  const plans = listQuery.data?.data.items || [];

  const columns: TableColumnsType<PlanProject> = [
    { title: "预案标题", dataIndex: "title", ellipsis: true },
    { title: "所属企业", dataIndex: "enterprise_name", width: 180, ellipsis: true },
    {
      title: "类型",
      dataIndex: "plan_type",
      width: 130,
      render: (type: PlanProject["plan_type"]) => <PlanTypeTag type={type} />,
    },
    {
      title: "完成度",
      key: "progress",
      width: 150,
      render: (_: unknown, record: PlanProject) => {
        const sec = record.sections_count || 0;
        const comp = record.completed_sections || 0;
        return (
          <Progress
            percent={sec > 0 ? Math.round((comp / sec) * 100) : 0}
            size="small"
            format={() => `${comp}/${sec}`}
          />
        );
      },
    },
    {
      title: "状态",
      dataIndex: "status",
      width: 100,
      render: (v: string) => <PlanStatusTag status={v as PlanStatus} />,
    },
    {
      title: "更新时间",
      dataIndex: "updated_at",
      width: 130,
      render: (t: string) => <span style={{ color: "#999", fontSize: 12 }}>{fromNow(t)}</span>,
    },
    {
      title: "操作",
      key: "actions",
      width: 90,
      render: (_: unknown, record: PlanProject) => (
        <Button
          type="link"
          size="small"
          onClick={(e) => {
            e.stopPropagation();
            navigate(`/plans/${record.id}/edit`);
          }}
        >
          编辑
        </Button>
      ),
    },
  ];

  return (
    <Table<PlanProject>
      columns={columns}
      dataSource={plans}
      rowKey="id"
      loading={listQuery.isLoading}
      pagination={{
        current: listPage,
        pageSize: 20,
        total: listQuery.data?.data.total || 0,
        showSizeChanger: false,
        showTotal: (t: number) => `共 ${t} 条`,
        onChange: onPageChange,
      }}
      onRow={(record) => ({
        style: { cursor: "pointer" },
        onClick: () => navigate(`/plans/${record.id}/edit`),
      })}
      locale={{ emptyText: "暂无预案" }}
    />
  );
}

export default function PlanCardsPage() {
  const navigate = useNavigate();
  const [view, setView] = useState<"cards" | "list">("cards");
  const [search, setSearch] = useState("");
  const [listSearch, setListSearch] = useState("");
  const [debouncedListSearch, setDebouncedListSearch] = useState("");
  const listSearchTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [listPage, setListPage] = useState(1);
  const [industry, setIndustry] = useState<string | undefined>();

  // 列表视图搜索防抖：停顿 300ms 后再发请求，避免每击键请求
  useEffect(() => {
    if (listSearchTimerRef.current) {
      clearTimeout(listSearchTimerRef.current);
    }
    listSearchTimerRef.current = setTimeout(() => {
      setDebouncedListSearch(listSearch);
    }, 300);
    return () => {
      if (listSearchTimerRef.current) {
        clearTimeout(listSearchTimerRef.current);
      }
    };
  }, [listSearch]);

  const { data: summaries, isLoading } = useQuery({
    queryKey: ["plan-enterprise-summary"],
    queryFn: getEnterprisePlanSummary,
  });

  const allItems = useMemo(() => summaries || [], [summaries]);

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
            <Button type="primary" icon={<PlusOutlined />} onClick={() => navigate("/plans/new")}>
              新建预案
            </Button>
          </Space>
        }
      />

      <Space style={{ marginBottom: 16 }}>
        <Segmented
          options={[
            { label: "卡片视图", value: "cards" },
            { label: "列表视图", value: "list" },
          ]}
          value={view}
          onChange={(v) => setView(v as "cards" | "list")}
        />
        <Input
          prefix={<SearchOutlined />}
          placeholder={view === "list" ? "搜索预案标题" : "搜索企业名称"}
          allowClear
          style={{ width: 240 }}
          value={view === "list" ? listSearch : search}
          onChange={(e) => {
            if (view === "list") {
              setListSearch(e.target.value);
              setListPage(1);
            } else {
              setSearch(e.target.value);
            }
          }}
        />
        {view === "cards" && (
          <Select
            placeholder="行业筛选"
            allowClear
            style={{ width: 160 }}
            value={industry}
            onChange={setIndustry}
            options={[...PRESET_INDUSTRIES].map((i) => ({ value: i, label: i }))}
          />
        )}
      </Space>

      {view === "list" ? (
        <PlanListTable
          listSearch={debouncedListSearch}
          listPage={listPage}
          onPageChange={setListPage}
        />
      ) : isLoading ? (
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
