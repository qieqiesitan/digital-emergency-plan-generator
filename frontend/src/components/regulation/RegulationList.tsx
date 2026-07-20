import { useState } from "react";
import {
  Table, Input, Select, Button, Space, Tag, Card, Row, Col,
  Statistic, Tooltip, Badge, Typography, Modal, message,
} from "antd";
import {
  PlusOutlined, SearchOutlined, StopOutlined, BookOutlined,
  CheckCircleOutlined, CloseCircleOutlined, FileTextOutlined,
  AuditOutlined, SafetyCertificateOutlined, FlagOutlined,
  EditOutlined, EyeOutlined, ClearOutlined, DeleteOutlined,
} from "@ant-design/icons";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchRegulations, fetchStats, deleteRegulation, updateRegulation, batchAbolish } from "@/services/regulationService";
import { RegulationForm } from "./RegulationForm";
import type { RegulationNode } from "@/types/regulation";

const { Text } = Typography;

interface Props {
  onAdd: () => void;
  onView: (id: string) => void;
  onAbolish: (r: RegulationNode) => void;
}

const TYPE_CONFIG: Record<string, { label: string; color: string; icon: React.ReactNode }> = {
  law: { label: "法律", color: "#1677ff", icon: <AuditOutlined /> },
  standard: { label: "标准", color: "#52c41a", icon: <SafetyCertificateOutlined /> },
  policy: { label: "政策", color: "#faad14", icon: <FlagOutlined /> },
  topic: { label: "主题", color: "#eb2f96", icon: <BookOutlined /> },
};

const STATUS_MAP: Record<string, { label: string; color: string }> = {
  effective: { label: "现行有效", color: "green" },
  abolished: { label: "已废止", color: "red" },
};

export function RegulationList({ onAdd, onView, onAbolish }: Props) {
  const [editingRegulation, setEditingRegulation] = useState<RegulationNode | null>(null);
  const queryClient = useQueryClient();
  const [kw, setKw] = useState("");
  const [st, setSt] = useState<string>("all");
  const [nt, setNt] = useState<string>("all");
  const [pg, setPg] = useState(1);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);

  const { data, isLoading } = useQuery({
    queryKey: ["regulations", kw, st, nt, pg],
    queryFn: () => fetchRegulations({ keyword: kw, status: st, node_type: nt, page: pg, page_size: 15 }),
  });

  const { data: sts } = useQuery({
    queryKey: ["regulationStats"],
    queryFn: fetchStats,
  });

  const batchMut = useMutation({
    mutationFn: () => batchAbolish(selectedIds),
    onSuccess: (d) => {
      message.success(`已废止 ${d.abolished} 条`);
      setSelectedIds([]);
      queryClient.invalidateQueries({ queryKey: ["regulations"] });
    },
    onError: () => message.error("批量废止失败"),
  });

  const statCards = [
    { title: "法规总数", value: sts?.total || 0, icon: <BookOutlined />, color: "#1677ff", bg: "#e6f4ff" },
    { title: "现行有效", value: sts?.effective || 0, icon: <CheckCircleOutlined />, color: "#52c41a", bg: "#f6ffed" },
    { title: "已废止", value: sts?.abolished || 0, icon: <CloseCircleOutlined />, color: "#ff4d4f", bg: "#fff2f0" },
    { title: "已索引条文", value: sts?.indexed_articles || 0, icon: <FileTextOutlined />, color: "#722ed1", bg: "#f9f0ff" },
  ];

  const items = data?.items || [];

  return (
    <div>
      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        {statCards.map((c) => (
          <Col xs={12} sm={6} key={c.title}>
            <Card
              size="small"
              style={{
                borderRadius: 12,
                border: `1px solid ${c.color}20`,
                background: `linear-gradient(135deg, ${c.bg} 0%, #fff 100%)`,
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                <div
                  style={{
                    width: 44, height: 44, borderRadius: 12,
                    background: c.color, color: "#fff",
                    display: "flex", alignItems: "center", justifyContent: "center",
                    fontSize: 20,
                  }}
                >
                  {c.icon}
                </div>
                <div>
                  <div style={{ fontSize: 12, color: "#8c8c8c" }}>{c.title}</div>
                  <div style={{ fontSize: 24, fontWeight: 700, color: c.color, lineHeight: 1.2 }}>
                    {c.value}
                  </div>
                </div>
              </div>
            </Card>
          </Col>
        ))}
      </Row>

      <Card size="small" style={{ marginBottom: 16, borderRadius: 12 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 12 }}>
          <Space wrap size="middle">
            <Input
              placeholder="搜索法规名称、编号..."
              prefix={<SearchOutlined style={{ color: "#bfbfbf" }} />}
              value={kw}
              onChange={(e) => { setKw(e.target.value); setPg(1); }}
              style={{ width: 260, borderRadius: 8 }}
              allowClear
            />
            <Select value={st} onChange={(v) => { setSt(v); setPg(1); }} style={{ width: 120 }}>
              <Select.Option value="all">全部状态</Select.Option>
              <Select.Option value="effective">现行有效</Select.Option>
              <Select.Option value="abolished">已废止</Select.Option>
            </Select>
            <Select value={nt} onChange={(v) => { setNt(v); setPg(1); }} style={{ width: 120 }}>
              <Select.Option value="all">全部类型</Select.Option>
              <Select.Option value="law">法律</Select.Option>
              <Select.Option value="standard">标准</Select.Option>
              <Select.Option value="policy">政策</Select.Option>
            </Select>
          </Space>
          <Space>
            {selectedIds.length > 0 && (
              <Button danger onClick={() => batchMut.mutate()}>
                批量废止 ({selectedIds.length})
              </Button>
            )}
            <Button type="primary" icon={<PlusOutlined />} onClick={onAdd} style={{ borderRadius: 8 }}>
              新增法规
            </Button>
          </Space>
        </div>
      </Card>

      <Card style={{ borderRadius: 12 }}>
        <Table
          rowSelection={{
            selectedRowKeys: selectedIds,
            onChange: (keys) => setSelectedIds(keys as string[]),
            getCheckboxProps: (r: RegulationNode) => ({ disabled: r.status !== "effective" }),
          }}
          columns={[
            {
              title: "法规编号/名称",
              key: "info",
              width: 320,
              ellipsis: true,
              render: (_: unknown, r: RegulationNode) => (
                <div>
                  <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 2 }}>
                    <Badge status={r.status === "effective" ? "success" : "error"} style={{ marginRight: 6 }} />
                    {(r?.full_name || r?.code || r?.label || r?.id || "").slice(0, 48)}
                  </div>
                  <Text type="secondary" style={{ fontSize: 12 }}>{r.code !== r.full_name ? r.code : r.issuing_body || ""}</Text>
                </div>
              ),
            },
            {
              title: "类型", dataIndex: "node_type", key: "type", width: 90,
              render: (v: string) => {
                const cfg = TYPE_CONFIG[v];
                return cfg ? <Tag color={cfg.color} icon={cfg.icon}>{cfg.label}</Tag> : <Tag>{v}</Tag>;
              },
            },
            {
              title: "发布机关", dataIndex: "issuing_body", key: "body", width: 180, ellipsis: true,
              render: (v: string) => v ? <Text style={{ fontSize: 12 }}>{v}</Text> : <Text type="secondary">—</Text>,
            },
            {
              title: "施行日期", dataIndex: "effective_date", key: "date", width: 110, align: "center" as const,
              render: (v: string) => v ? <Text style={{ fontSize: 12 }}>{v}</Text> : <Text type="secondary">—</Text>,
            },
            {
              title: "条文", dataIndex: "article_count", key: "arts", width: 70, align: "center" as const,
              render: (v: number) => <Tag style={{ borderRadius: 10 }}>{v}</Tag>,
            },
            {
              title: "状态", dataIndex: "status", key: "status", width: 100, align: "center" as const,
              render: (v: string) => {
                const cfg = STATUS_MAP[v];
                return cfg ? <Tag color={cfg.color}>{cfg.label}</Tag> : <Tag>{v}</Tag>;
              },
            },
            {
              title: "操作", key: "act", width: 220, align: "center" as const,
              render: (_: unknown, r: RegulationNode) => (
                <Space size="small">
                  <Button type="link" size="small" icon={<EyeOutlined />} onClick={() => onView(r.id)}>详情</Button>
                  {r.status !== "abolished" && (
                    <Button type="link" size="small" danger icon={<StopOutlined />} onClick={() => onAbolish(r)}>废止</Button>
                  )}
                  <Button type="link" size="small" icon={<EditOutlined />}
                    onClick={() => setEditingRegulation(r)}>编辑</Button>
                  <Button type="link" size="small" danger icon={<DeleteOutlined />}
                    onClick={() => {
                      Modal.confirm({
                        title: "确认删除",
                        content: `确定删除 "${r.code || r.full_name}" 吗？此操作不可撤销。`,
                        okText: "删除", okType: "danger", cancelText: "取消",
                        onOk: async () => {
                          try { await deleteRegulation(r.id); message.success("已删除"); queryClient.invalidateQueries({ queryKey: ["regulations"] }); }
                          catch { message.error("删除失败"); }
                        },
                      });
                    }}>删除</Button>
                </Space>
              ),
            },
          ]}
          dataSource={items}
          rowKey="id"
          loading={isLoading}
          pagination={{
            current: pg, total: data?.total || 0, pageSize: 15, onChange: setPg,
            showTotal: (t) => `共 ${t} 条法规`, showSizeChanger: false,
          }}
          size="middle"
        />
      </Card>

      {editingRegulation && (
        <RegulationForm
          open={!!editingRegulation}
          onClose={() => setEditingRegulation(null)}
          regulation={editingRegulation}
          onSaved={() => {
            setEditingRegulation(null);
            queryClient.invalidateQueries({ queryKey: ["regulations"] });
          }}
        />
      )}
    </div>
  );
}
