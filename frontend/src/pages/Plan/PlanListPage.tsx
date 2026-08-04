import { useState, useCallback } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Table, Tabs, Radio, Input, Button, Space, Progress, message } from "antd";
import { PlusOutlined, BankOutlined } from "@ant-design/icons";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { listPlans, deletePlan } from "@/services/planService";
import { getEnterprise } from "@/services/enterpriseService";
import { PageHeader } from "@/components/common/PageHeader";
import { PlanTypeTag } from "@/components/plan/PlanTypeTag";
import { PlanStatusTag } from "@/components/plan/PlanStatusTag";
import { ConfirmDeleteModal } from "@/components/common/ConfirmDeleteModal";
import { fromNow } from "@/utils/formatters";
import type { PlanType, PlanStatus } from "@/types/plan";

export default function PlanListPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { enterprise_id } = useParams<{ enterprise_id?: string }>();

  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState<string>("all");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [page, setPage] = useState(1);
  const pageSize = 20;
  const [deleteTarget, setDeleteTarget] = useState<{ id: string; name: string } | null>(null);

  // enterprise info (only when scoped to one enterprise)
  const { data: enterprise } = useQuery({
    queryKey: ["enterprise", enterprise_id],
    queryFn: () => getEnterprise(enterprise_id!),
    enabled: !!enterprise_id,
  });

  // plan list — server-side filters + pagination
  const { data, isLoading } = useQuery({
    queryKey: ["plans", {
      enterprise_id: enterprise_id || undefined,
      plan_type: typeFilter !== "all" ? typeFilter : undefined,
      status: statusFilter !== "all" ? statusFilter : undefined,
      search: search || undefined,
      page,
      page_size: pageSize,
    }],
    queryFn: () => listPlans({
      enterprise_id: enterprise_id || undefined,
      plan_type: typeFilter !== "all" ? typeFilter : undefined,
      status: statusFilter !== "all" ? statusFilter : undefined,
      search: search || undefined,
      page,
      page_size: pageSize,
    }),
  });

  const deleteMutation = useMutation({
    mutationFn: deletePlan,
    onSuccess: () => {
      message.success("已删除");
      queryClient.invalidateQueries({ queryKey: ["plans"] });
      setDeleteTarget(null);
    },
    onError: () => message.error("删除失败"),
  });

  // reset to page 1 on any filter change
  const handleSearch = useCallback((value: string) => { setSearch(value); setPage(1); }, []);
  const handleTypeChange = useCallback((key: string) => { setTypeFilter(key); setPage(1); }, []);
  const handleStatusChange = useCallback((v: string) => { setStatusFilter(v); setPage(1); }, []);

  const plans = data?.data.items || [];
  const total = data?.data.total || 0;
  const isGlobal = !enterprise_id;
  const entName = enterprise?.name || "";

  const columns = [
    {
      title: "预案标题",
      dataIndex: "title",
      render: (text: string, record: Record<string, unknown>) => (
        <span>
          <PlanTypeTag type={(record.plan_type as string) as PlanType} />
          {record.accident_type ? (
            <span style={{ color: "gray", marginLeft: 8 }}>{record.accident_type as string}</span>
          ) : null}
          {" "}{text}
        </span>
      ),
    },
    ...(isGlobal
      ? [{
          title: "所属企业",
          dataIndex: "enterprise_name",
          width: 160,
        }]
      : []),
    {
      title: "完成度",
      key: "progress",
      width: 160,
      render: (_: unknown, record: Record<string, unknown>) => {
        const sec = (record.sections_count as number) || 0;
        const comp = (record.completed_sections as number) || 0;
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
      width: 90,
      render: (s: string) => <PlanStatusTag status={s as PlanStatus} />,
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
      width: 140,
      render: (_: unknown, record: Record<string, unknown>) => (
        <Space>
          <Button type="link" size="small" onClick={(e) => { e.stopPropagation(); navigate(`/plans/${record.id as string}/edit`); }}>
            编辑
          </Button>
          <Button type="link" size="small" danger onClick={(e) => { e.stopPropagation(); setDeleteTarget({ id: record.id as string, name: record.title as string }); }}>
            删除
          </Button>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <PageHeader
        title={
          isGlobal
            ? "全部预案"
            : (entName ? `${entName} - 预案列表` : "预案列表")
        }
        onBack={enterprise_id ? () => navigate("/plans") : undefined}
        extra={
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => navigate(
              enterprise_id
                ? `/plans/new?enterprise_id=${enterprise_id}`
                : "/plans/new"
            )}
          >
            新建预案
          </Button>
        }
      />

      <Space style={{ marginBottom: 16 }} wrap>
        <Tabs
          activeKey={typeFilter}
          onChange={handleTypeChange}
          items={[
            { key: "all", label: "全部" },
            { key: "comprehensive", label: "综合预案" },
            { key: "special", label: "专项预案" },
            { key: "onsite", label: "现场处置" },
          ]}
        />
        <Radio.Group value={statusFilter} onChange={(e) => handleStatusChange(e.target.value)}>
          <Radio.Button value="all">全部</Radio.Button>
          <Radio.Button value="draft">草稿</Radio.Button>
          <Radio.Button value="completed">已完成</Radio.Button>
        </Radio.Group>
        <Input.Search
          placeholder={isGlobal ? "搜索预案标题" : "搜索预案"}
          allowClear
          style={{ width: 240 }}
          onSearch={handleSearch}
        />
      </Space>

      <Table
        columns={columns}
        dataSource={plans as any}
        rowKey="id"
        loading={isLoading}
        pagination={{
          current: page,
          pageSize,
          total,
          showTotal: (t: number) => `共 ${t} 条`,
          showSizeChanger: false,
          onChange: (p: number) => setPage(p),
        }}
        onRow={(record) => ({
          style: { cursor: "pointer" },
          onClick: () => navigate(`/plans/${record.id}/edit`),
        })}
        locale={{ emptyText: "暂无预案" }}
      />

      <ConfirmDeleteModal
        open={!!deleteTarget}
        title={deleteTarget?.name || ""}
        onConfirm={() => deleteTarget && deleteMutation.mutate(deleteTarget.id)}
        onCancel={() => setDeleteTarget(null)}
        loading={deleteMutation.isPending}
      />
    </div>
  );
}
