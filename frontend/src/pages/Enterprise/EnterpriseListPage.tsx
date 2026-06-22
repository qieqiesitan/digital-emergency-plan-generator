import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Table, Input, Select, Button, Space, message } from "antd";
import { PlusOutlined } from "@ant-design/icons";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { listEnterprises, deleteEnterprise } from "@/services/enterpriseService";
import { PageHeader } from "@/components/common/PageHeader";
import { ConfirmDeleteModal } from "@/components/common/ConfirmDeleteModal";
import { formatDate } from "@/utils/formatters";
import { PRESET_INDUSTRIES } from "@/utils/constants";

export default function EnterpriseListPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [industry, setIndustry] = useState<string | undefined>();
  const [page, setPage] = useState(1);
  const [deleteTarget, setDeleteTarget] = useState<{ id: string; name: string } | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["enterprises", { page, search, industry }],
    queryFn: () => listEnterprises({ page, page_size: 20, search: search || undefined, industry }),
  });

  const deleteMutation = useMutation({
    mutationFn: deleteEnterprise,
    onSuccess: () => {
      message.success("已删除");
      queryClient.invalidateQueries({ queryKey: ["enterprises"] });
      setDeleteTarget(null);
    },
    onError: () => message.error("删除失败"),
  });

  const columns = [
    {
      title: "企业名称",
      dataIndex: "name",
      render: (text: string, record: { id: string }) => (
        <a onClick={() => navigate(`/enterprises/${record.id}`)}>{text}</a>
      ),
    },
    { title: "行业", dataIndex: "industry" },
    { title: "员工数", dataIndex: "employee_count", render: (v: number | null) => v ?? "-" },
    { title: "风险源数", dataIndex: "risk_sources_count" },
    { title: "预案数", dataIndex: "plans_count" },
    { title: "更新时间", dataIndex: "updated_at", render: formatDate },
    {
      title: "操作",
      key: "actions",
      render: (_: unknown, record: { id: string; name: string }) => (
        <Space>
          <a onClick={() => navigate(`/enterprises/${record.id}/edit`)}>编辑</a>
          <a style={{ color: "#ff4d4f" }} onClick={() => setDeleteTarget({ id: record.id, name: record.name })}>
            删除
          </a>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <PageHeader
        title="企业管理"
        extra={<Button type="primary" icon={<PlusOutlined />} onClick={() => navigate("/enterprises/new")}>新建企业</Button>}
      />

      <Space style={{ marginBottom: 16 }}>
        <Input.Search
          placeholder="搜索企业名称"
          allowClear
          style={{ width: 240 }}
          onSearch={(v) => { setSearch(v); setPage(1); }}
        />
        <Select
          placeholder="行业筛选"
          allowClear
          style={{ width: 160 }}
          value={industry}
          onChange={(v) => { setIndustry(v); setPage(1); }}
          options={[...PRESET_INDUSTRIES].map((i) => ({ value: i, label: i }))}
        />
      </Space>

      <Table
        columns={columns}
        dataSource={data?.data.items || []}
        rowKey="id"
        loading={isLoading}
        pagination={{
          current: page,
          pageSize: 20,
          total: data?.data.total || 0,
          onChange: setPage,
        }}
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
