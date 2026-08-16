import { useState } from "react";
import { Table, Button, Select, Input, Radio, Modal, Space, message, Tag } from "antd";
import { PlusOutlined, EditOutlined, DeleteOutlined, EnvironmentOutlined, DownloadOutlined } from "@ant-design/icons";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import AppIcon from "@/components/common/AppIcon";
import { listRiskSources, createRiskSource, updateRiskSource, deleteRiskSource } from "@/services/riskSourceService";
import { RiskLevelTag } from "./RiskLevelTag";
import { PRESET_RISK_CATEGORIES } from "@/utils/constants";
import FloorPlanPicker from "./FloorPlanPicker";
import RiskSourceImportModal from "./RiskSourceImportModal";
import RiskSourceAIGenerateModal from "./RiskSourceAIGenerateModal";
import type { RiskSource, RiskSourceCreate } from "@/types/riskSource";

interface Props {
  enterpriseId: string;
  floorPlanUrl?: string | null;
}

export default function RiskSourceForm({ enterpriseId, floorPlanUrl }: Props) {
  const queryClient = useQueryClient();
  const [modalOpen, setModalOpen] = useState(false);
  const [floorPlanOpen, setFloorPlanOpen] = useState(false);
  const [importModalOpen, setImportModalOpen] = useState(false);
  const [aiModalOpen, setAiModalOpen] = useState(false);
  const [editing, setEditing] = useState<RiskSource | null>(null);
  const [form, setForm] = useState<RiskSourceCreate & { _desc?: string }>({ categories: [], name: "" });

  const { data, isLoading } = useQuery({
    queryKey: ["riskSources", enterpriseId],
    queryFn: () => listRiskSources(enterpriseId, { page_size: 200 }),
  });

  const createMut = useMutation({
    mutationFn: (d: RiskSourceCreate) => createRiskSource(enterpriseId, d),
    onSuccess: () => { message.success("创建成功"); queryClient.invalidateQueries({ queryKey: ["riskSources", enterpriseId] }); setModalOpen(false); resetForm(); },
    onError: () => message.error("创建失败"),
  });

  const updateMut = useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<RiskSourceCreate> }) => updateRiskSource(enterpriseId, id, data),
    onSuccess: () => { message.success("更新成功"); queryClient.invalidateQueries({ queryKey: ["riskSources", enterpriseId] }); setModalOpen(false); resetForm(); },
    onError: () => message.error("更新失败"),
  });

  const deleteMut = useMutation({
    mutationFn: (id: string) => deleteRiskSource(enterpriseId, id),
    onSuccess: () => { message.success("删除成功"); queryClient.invalidateQueries({ queryKey: ["riskSources", enterpriseId] }); },
    onError: () => message.error("删除失败"),
  });

  const resetForm = () => { setEditing(null); setForm({ categories: [], name: "" }); };

  const items = data?.data?.items || [];

  const columns = [
    {
      title: "风险类别",
      dataIndex: "categories",
      render: (cats: string[]) => (
        <Space size={4} wrap>
          {cats?.map((c) => <Tag key={c} color="orange">{c}</Tag>)}
        </Space>
      ),
    },
    { title: "风险名称", dataIndex: "name" },
    {
      title: "位置",
      dataIndex: "location",
      render: (v: string, record: RiskSource) => {
        const hasCoord = record.location_x != null && record.location_y != null;
        return (
          <span>
            {hasCoord && <EnvironmentOutlined style={{ color: "#ff4d4f", marginRight: 4 }} />}
            {v || (hasCoord ? `(${record.location_x!.toFixed(0)}%, ${record.location_y!.toFixed(0)}%)` : "-")}
          </span>
        );
      },
    },
    { title: "风险等级", dataIndex: "risk_level", render: (v: string) => <RiskLevelTag level={v as any} /> },
    { title: "控制措施", dataIndex: "control_measures", render: (v: string) => v ? (v.length > 30 ? v.slice(0, 30) + "..." : v) : "-" },
    {
      title: "操作",
      render: (_: unknown, record: RiskSource) => (
        <Space>
          <Button type="link" size="small" icon={<EditOutlined />}
            onClick={() => {
              setEditing(record);
              setForm({
                categories: record.categories || [],
                name: record.name,
                location: record.location,
                location_x: record.location_x,
                location_y: record.location_y,
                description: record.description,
                likelihood: record.likelihood,
                severity: record.severity,
                control_measures: record.control_measures,
                _desc: record.location || "",
              });
              setModalOpen(true);
            }}
          />
          <Button type="link" size="small" danger icon={<DeleteOutlined />}
            onClick={() => { Modal.confirm({ title: "确认删除？", content: "删除后不可恢复", onOk: () => deleteMut.mutate(record.id) }); }} />
        </Space>
      ),
    },
  ];

  return (
    <div>
      <div style={{ marginBottom: 16 }}>
        <Space>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => { resetForm(); setModalOpen(true); }}>
            添加风险源
          </Button>
          <Button icon={<DownloadOutlined />} onClick={() => setImportModalOpen(true)}>
            导入Excel
          </Button>
          <Button icon={<AppIcon name="ai" size={14} />} onClick={() => setAiModalOpen(true)}>
            AI智能生成
          </Button>
        </Space>
      </div>
      <Table dataSource={items} rowKey="id" columns={columns} loading={isLoading} pagination={false} size="small" />

      <Modal title={editing ? "编辑风险源" : "新增风险源"} open={modalOpen}
        onCancel={() => setModalOpen(false)} width={600}
        onOk={() => {
          if (!form.categories.length || !form.name) return;
          const { _desc, ...data } = form;
          if (editing) updateMut.mutate({ id: editing.id, data });
          else createMut.mutate(data);
        }}
        confirmLoading={createMut.isPending || updateMut.isPending}
      >
        <div style={{ display: "flex", flexDirection: "column", gap: 12, paddingTop: 16 }}>
          <Select
            mode="multiple"
            placeholder="选择风险类别（可多选）"
            value={form.categories}
            onChange={(v) => setForm((f) => ({ ...f, categories: v }))}
            options={PRESET_RISK_CATEGORIES.map((c) => ({ value: c, label: c }))}
            style={{ width: "100%" }}
          />
          <Input placeholder="风险名称" value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} />

          <div style={{ display: "flex", gap: 8 }}>
            <Button
              icon={<EnvironmentOutlined />}
              onClick={() => setFloorPlanOpen(true)}
              disabled={!floorPlanUrl}
            >
              {floorPlanUrl ? "在平面图上点选位置" : "未上传平面图"}
            </Button>
            <Input
              placeholder="或手动输入位置描述"
              value={form._desc ?? form.location ?? ""}
              onChange={(e) => setForm((f) => ({ ...f, _desc: e.target.value, location: e.target.value }))}
              style={{ flex: 1 }}
            />
          </div>

          <Input.TextArea placeholder="风险描述" value={form.description || ""} rows={2} onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))} />
          <div>
            <span>可能性：</span>
            <Radio.Group value={form.likelihood || "中"} onChange={(e) => setForm((f) => ({ ...f, likelihood: e.target.value }))}>
              <Radio.Button value="高">高</Radio.Button>
              <Radio.Button value="中">中</Radio.Button>
              <Radio.Button value="低">低</Radio.Button>
            </Radio.Group>
          </div>
          <div>
            <span>严重性：</span>
            <Radio.Group value={form.severity || "中"} onChange={(e) => setForm((f) => ({ ...f, severity: e.target.value }))}>
              <Radio.Button value="高">高</Radio.Button>
              <Radio.Button value="中">中</Radio.Button>
              <Radio.Button value="低">低</Radio.Button>
            </Radio.Group>
          </div>
          <Input.TextArea placeholder="控制措施" value={form.control_measures || ""} rows={2} onChange={(e) => setForm((f) => ({ ...f, control_measures: e.target.value }))} />
        </div>
      </Modal>

      <FloorPlanPicker
        imageUrl={floorPlanUrl || null}
        visible={floorPlanOpen}
        value={{
          x: form.location_x ?? null,
          y: form.location_y ?? null,
          description: form._desc ?? form.location ?? "",
        }}
        onChange={(val) => {
          setForm((f) => ({
            ...f,
            location_x: val.x,
            location_y: val.y,
            location: val.description,
            _desc: val.description,
          }));
        }}
        onClose={() => setFloorPlanOpen(false)}
      />

      <RiskSourceImportModal
        enterpriseId={enterpriseId}
        visible={importModalOpen}
        onClose={() => setImportModalOpen(false)}
        onImported={() => {
          setImportModalOpen(false);
          queryClient.invalidateQueries({ queryKey: ["riskSources", enterpriseId] });
            queryClient.invalidateQueries({ queryKey: ["enterprise", enterpriseId] });
        }}
      />

      <RiskSourceAIGenerateModal
        enterpriseId={enterpriseId}
        visible={aiModalOpen}
        onClose={() => setAiModalOpen(false)}
        onImported={() => {
          setAiModalOpen(false);
          queryClient.invalidateQueries({ queryKey: ["riskSources", enterpriseId] });
            queryClient.invalidateQueries({ queryKey: ["enterprise", enterpriseId] });
        }}
      />
    </div>
  );
}
