import { useState } from "react";
import { Table, Button, Select, Input, InputNumber, Switch, Modal, Space, message } from "antd";
import { PlusOutlined, EditOutlined, DeleteOutlined, DownloadOutlined } from "@ant-design/icons";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import AppIcon from "@/components/common/AppIcon";
import { listResources, createResource, updateResource, deleteResource } from "@/services/emergencyResourceService";
import { PRESET_INTERNAL_RESOURCE_CATEGORIES, PRESET_EXTERNAL_RESOURCE_CATEGORIES } from "@/utils/constants";
import ResourceImportModal from "./ResourceImportModal";
import ResourceAIGenerateModal from "./ResourceAIGenerateModal";
import type { EmergencyResource, EmergencyResourceCreate } from "@/types/emergencyResource";

export default function EmergencyResourceForm({ enterpriseId }: { enterpriseId: string }) {
  const queryClient = useQueryClient();
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<EmergencyResource | null>(null);
  const [form, setForm] = useState<EmergencyResourceCreate & { _ext?: boolean }>({ category: "", name: "", is_external: false });
  const [filterExt, setFilterExt] = useState<string>("all");
  const [importModalOpen, setImportModalOpen] = useState(false);
  const [aiModalOpen, setAiModalOpen] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ["resources", enterpriseId],
    queryFn: () => listResources(enterpriseId, { page_size: 200 }),
  });

  const createMut = useMutation({
    mutationFn: (d: EmergencyResourceCreate) => createResource(enterpriseId, d),
    onSuccess: () => { message.success("创建成功"); queryClient.invalidateQueries({ queryKey: ["resources", enterpriseId] }); setModalOpen(false); resetForm(); },
    onError: () => message.error("创建失败"),
  });

  const updateMut = useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<EmergencyResourceCreate> }) => updateResource(enterpriseId, id, data),
    onSuccess: () => { message.success("更新成功"); queryClient.invalidateQueries({ queryKey: ["resources", enterpriseId] }); setModalOpen(false); resetForm(); },
    onError: () => message.error("更新失败"),
  });

  const deleteMut = useMutation({
    mutationFn: (id: string) => deleteResource(enterpriseId, id),
    onSuccess: () => { message.success("删除成功"); queryClient.invalidateQueries({ queryKey: ["resources", enterpriseId] }); },
    onError: () => message.error("删除失败"),
  });

  const resetForm = () => { setEditing(null); setForm({ category: "", name: "", is_external: false }); };

  const allItems = data?.data?.items || [];
  const items = filterExt === "all" ? allItems : filterExt === "internal" ? allItems.filter((i) => !i.is_external) : allItems.filter((i) => i.is_external);

  const columns = [
    { title: "类别", dataIndex: "category" },
    { title: "名称", dataIndex: "name" },
    { title: "规格型号", dataIndex: "specification", render: (v: string) => v || "-" },
    { title: "数量", dataIndex: "quantity" },
    ...(filterExt !== "external" ? [{ title: "存放位置", dataIndex: "location", render: (v: string) => v || "-" }] : []),
    ...(filterExt === "external" ? [{ title: "地址", dataIndex: "external_address", render: (v: string) => v || "-" }] : []),
    { title: "联系电话", dataIndex: "contact_phone", render: (v: string) => v || "-" },
    {
      title: "操作",
      render: (_: unknown, record: EmergencyResource) => (
        <Space>
          <Button type="link" size="small" icon={<EditOutlined />}
            onClick={() => { setEditing(record); setForm({ category: record.category, name: record.name, specification: record.specification, quantity: record.quantity, unit: record.unit, location: record.location, responsible_person: record.responsible_person, contact_phone: record.contact_phone, is_external: record.is_external, external_address: record.external_address, external_distance_km: record.external_distance_km }); setModalOpen(true); }} />
          <Button type="link" size="small" danger icon={<DeleteOutlined />}
            onClick={() => { Modal.confirm({ title: "确认删除？", content: "删除后不可恢复", onOk: () => deleteMut.mutate(record.id) }); }} />
        </Space>
      ),
    },
  ];

  const cats = form.is_external ? PRESET_EXTERNAL_RESOURCE_CATEGORIES : PRESET_INTERNAL_RESOURCE_CATEGORIES;

  return (
    <div>
      <Space style={{ marginBottom: 16 }} wrap>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => { resetForm(); setModalOpen(true); }}>
          添加资源
        </Button>
        <Button icon={<DownloadOutlined />} onClick={() => setImportModalOpen(true)}>
          导入Excel
        </Button>
        <Button icon={<AppIcon name="ai" size={14} />} onClick={() => setAiModalOpen(true)}>
          AI智能生成
        </Button>
        <Select value={filterExt} onChange={setFilterExt} style={{ width: 120 }}
          options={[{ value: "all", label: "全部" }, { value: "internal", label: "内部" }, { value: "external", label: "外部" }]} />
      </Space>
      <Table dataSource={items} rowKey="id" columns={columns} loading={isLoading} pagination={false} size="small" />

      <Modal title={editing ? "编辑资源" : "新增资源"} open={modalOpen}
        onCancel={() => setModalOpen(false)} width={600}
        onOk={() => {
          if (!form.category || !form.name) return;
          const { _ext, ...data } = form;
          if (editing) updateMut.mutate({ id: editing.id, data });
          else createMut.mutate(data);
        }}
        confirmLoading={createMut.isPending || updateMut.isPending}
      >
        <div style={{ display: "flex", flexDirection: "column", gap: 12, paddingTop: 16 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span>外部资源：</span>
            <Switch checked={form.is_external} onChange={(v) => setForm((f) => ({ ...f, is_external: v, category: "" }))} />
          </div>
          <Select placeholder="选择类别" value={form.category || undefined}
            onChange={(v) => setForm((f) => ({ ...f, category: v }))}
            options={[...cats].map((c) => ({ value: c, label: c }))}
            style={{ width: "100%" }} />
          <Input placeholder="资源名称" value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} />
          {!form.is_external && <>
            <Input placeholder="规格型号" value={form.specification || ""} onChange={(e) => setForm((f) => ({ ...f, specification: e.target.value }))} />
            <Input placeholder="存放位置" value={form.location || ""} onChange={(e) => setForm((f) => ({ ...f, location: e.target.value }))} />
          </>}
          <InputNumber placeholder="数量" value={form.quantity || 1} onChange={(v) => setForm((f) => ({ ...f, quantity: v || 1 }))} style={{ width: "100%" }} />
          {form.is_external && <>
            <Input placeholder="地址" value={form.external_address || ""} onChange={(e) => setForm((f) => ({ ...f, external_address: e.target.value }))} />
            <InputNumber placeholder="距离（公里）" value={form.external_distance_km || undefined} onChange={(v) => setForm((f) => ({ ...f, external_distance_km: v }))} style={{ width: "100%" }} />
          </>}
          <Input placeholder="联系电话" value={form.contact_phone || ""} onChange={(e) => setForm((f) => ({ ...f, contact_phone: e.target.value }))} />
        </div>
      </Modal>

      <ResourceImportModal
        enterpriseId={enterpriseId}
        visible={importModalOpen}
        onClose={() => setImportModalOpen(false)}
        onImported={() => {
          setImportModalOpen(false);
          queryClient.invalidateQueries({ queryKey: ["resources", enterpriseId] });
            queryClient.invalidateQueries({ queryKey: ["enterprise", enterpriseId] });
          }}
      />

      <ResourceAIGenerateModal
        enterpriseId={enterpriseId}
        visible={aiModalOpen}
        onClose={() => setAiModalOpen(false)}
        onImported={() => {
          setAiModalOpen(false);
          queryClient.invalidateQueries({ queryKey: ["resources", enterpriseId] });
            queryClient.invalidateQueries({ queryKey: ["enterprise", enterpriseId] });
          }}
      />
    </div>
  );
}
