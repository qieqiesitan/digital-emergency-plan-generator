import { useState } from "react";
import { useNavigate, useParams, Link } from "react-router-dom";
import { List, Tabs, Radio, Input, Button, Space, Progress, message } from "antd";
import { PlusOutlined, ArrowLeftOutlined } from "@ant-design/icons";
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
  const { enterprise_id } = useParams<{ enterprise_id: string }>();
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState<string>("all");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [deleteTarget, setDeleteTarget] = useState<{ id: string; name: string } | null>(null);

  const { data: enterprise } = useQuery({
    queryKey: ["enterprise", enterprise_id],
    queryFn: () => getEnterprise(enterprise_id!),
    enabled: !!enterprise_id,
  });

  const { data, isLoading } = useQuery({
    queryKey: ["plans", { enterprise_id, plan_type: typeFilter !== "all" ? typeFilter : undefined, status: statusFilter !== "all" ? statusFilter : undefined, search: search || undefined }],
    queryFn: () => listPlans({ enterprise_id: enterprise_id!, plan_type: typeFilter !== "all" ? typeFilter : undefined, status: statusFilter !== "all" ? statusFilter : undefined, search: search || undefined, page_size: 100 }),
    enabled: !!enterprise_id,
  });

  const deleteMutation = useMutation({
    mutationFn: deletePlan,
    onSuccess: () => { message.success("已删除"); queryClient.invalidateQueries({ queryKey: ["plans"] }); setDeleteTarget(null); },
    onError: () => message.error("删除失败"),
  });

  const plans = data?.data.items || [];
  const entName = enterprise?.name || "";

  return (
    <div>
      <PageHeader
        title={entName ? `${entName} - 预案列表` : "预案列表"}
        onBack={() => navigate("/plans")}
        extra={
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => navigate(`/plans/new?enterprise_id=${enterprise_id}`)}
          >
            新建预案
          </Button>
        }
      />

      <Space style={{ marginBottom: 16 }} wrap>
        <Tabs
          activeKey={typeFilter}
          onChange={setTypeFilter}
          items={[
            { key: "all", label: "全部" },
            { key: "comprehensive", label: "综合预案" },
            { key: "special", label: "专项预案" },
            { key: "onsite", label: "现场处置" },
          ]}
        />
        <Radio.Group value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
          <Radio.Button value="all">全部</Radio.Button>
          <Radio.Button value="draft">草稿</Radio.Button>
          <Radio.Button value="completed">已完成</Radio.Button>
        </Radio.Group>
        <Input.Search placeholder="搜索预案" allowClear style={{ width: 200 }} onSearch={setSearch} />
      </Space>

      <List
        loading={isLoading}
        dataSource={plans}
        renderItem={(item) => (
          <List.Item
            style={{ cursor: "pointer" }}
            onClick={() => navigate(`/plans/${item.id}/edit`)}
            actions={[
              <Button type="link" onClick={(e) => { e.stopPropagation(); navigate(`/plans/${item.id}/edit`); }}>编辑</Button>,
              <Button type="link" danger onClick={(e) => { e.stopPropagation(); setDeleteTarget({ id: item.id, name: item.title }); }}>删除</Button>,
            ]}
          >
            <List.Item.Meta
              title={
                <span>
                  <PlanTypeTag type={item.plan_type as PlanType} />
                  {item.accident_type && <span style={{ color: "gray", marginLeft: 8 }}>{item.accident_type}</span>}
                  {" "}{item.title}
                </span>
              }
              description={
                <Progress
                  percent={item.sections_count > 0 ? Math.round((item.completed_sections / item.sections_count) * 100) : 0}
                  size="small"
                  style={{ width: 200 }}
                  format={() => `${item.completed_sections}/${item.sections_count}`}
                />
              }
            />
            <Space>
              <PlanStatusTag status={item.status as PlanStatus} />
              <span style={{ color: "#999", fontSize: 12 }}>{fromNow(item.updated_at)}</span>
            </Space>
          </List.Item>
        )}
        locale={{ emptyText: "暂无预案，点击上方按钮新建" }}
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