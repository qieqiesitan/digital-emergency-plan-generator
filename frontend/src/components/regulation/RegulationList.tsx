import { useState } from "react";
import { Table, Input, Select, Button, Space, Tag, message, Popconfirm } from "antd";
import { PlusOutlined, SearchOutlined, StopOutlined } from "@ant-design/icons";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchRegulations, abolishRegulation } from "@/services/regulationService";
import type { RegulationNode } from "@/types/regulation";

interface Props {
  onAdd: () => void;
  onView: (id: string) => void;
  onAbolish: (record: RegulationNode) => void;
}

export function RegulationList({ onAdd, onView, onAbolish }: Props) {
  const queryClient = useQueryClient();
  const [keyword, setKeyword] = useState("");
  const [status, setStatus] = useState<string>("all");
  const [nodeType, setNodeType] = useState<string>("all");
  const [page, setPage] = useState(1);

  const { data, isLoading } = useQuery({
    queryKey: ["regulations", keyword, status, nodeType, page],
    queryFn: () => fetchRegulations({ keyword, status, node_type: nodeType, page, page_size: 20 }),
  });

  const statusColors: Record<string, string> = { effective: "green", abolished: "red", revised: "orange" };
  const typeLabels: Record<string, string> = { law: "法律", standard: "标准", policy: "政策", topic: "主题" };

  const columns = [
    { title: "编号", dataIndex: "code", key: "code", width: 160, ellipsis: true },
    { title: "名称", dataIndex: "full_name", key: "full_name", ellipsis: true },
    { title: "类型", dataIndex: "node_type", key: "node_type", width: 80, render: (t: string) => typeLabels[t] || t },
    { title: "版本", dataIndex: "version", key: "version", width: 100 },
    { title: "状态", dataIndex: "status", key: "status", width: 80, render: (s: string) => <Tag color={statusColors[s]}>{s === "effective" ? "有效" : s === "abolished" ? "废止" : s}</Tag> },
    { title: "操作", key: "actions", width: 200, render: (_: unknown, record: RegulationNode) => (
        <Space>
          <Button type="link" size="small" onClick={() => onView(record.id)}>查看</Button>
          {record.status !== "abolished" && <Button type="link" size="small" danger onClick={() => onAbolish(record)} icon={<StopOutlined />}>废止</Button>}
        </Space>
      ),
    },
  ];

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 16 }}>
        <Space>
          <Input placeholder="搜索法规..." prefix={<SearchOutlined />} value={keyword}
            onChange={e => { setKeyword(e.target.value); setPage(1); }} style={{ width: 200 }} allowClear />
          <Select value={status} onChange={v => { setStatus(v); setPage(1); }} style={{ width: 100 }}>
            <Select.Option value="all">全部状态</Select.Option>
            <Select.Option value="effective">有效</Select.Option>
            <Select.Option value="abolished">废止</Select.Option>
          </Select>
          <Select value={nodeType} onChange={v => { setNodeType(v); setPage(1); }} style={{ width: 100 }}>
            <Select.Option value="all">全部类型</Select.Option>
            <Select.Option value="law">法律</Select.Option>
            <Select.Option value="standard">标准</Select.Option>
            <Select.Option value="policy">政策</Select.Option>
          </Select>
        </Space>
        <Button type="primary" icon={<PlusOutlined />} onClick={onAdd}>新增法规</Button>
      </div>
      <Table columns={columns} dataSource={data?.items || []} rowKey="id" loading={isLoading}
        pagination={{ current: page, total: data?.total || 0, pageSize: 20, onChange: setPage, showTotal: t => `共 ${t} 条` }}
        size="middle" />
    </div>
  );
}