import { useState, useEffect } from "react";
import { Button, Table, Modal, Form, Input, Space, message, Popconfirm, Tag } from "antd";
import { PlusOutlined, EditOutlined, DeleteOutlined } from "@ant-design/icons";
import AppIcon from "@/components/common/AppIcon";
import {
  listChemicals,
  createChemical,
  updateChemical,
  deleteChemical,
} from "@/services/hazardousChemicalService";
import HazardousChemicalAIGenerateModal from "@/components/enterprise/HazardousChemicalAIGenerateModal";
import ChemicalLibraryPickerModal from "@/components/enterprise/ChemicalLibraryPickerModal";
import { libraryItemToPrefill } from "@/utils/chemicalLibraryPrefill";
import type { ChemicalLibraryItem } from "@/types/chemicalLibrary";
import type { HazardousChemical, HazardousChemicalCreate, HazardousChemicalUpdate } from "@/types/hazardousChemical";

interface Props {
  enterpriseId: string;
}

const FIELD_LABELS: Record<string, string> = {
  name: "化学品名称",
  cas_no: "CAS号",
  un_no: "UN号",
  physical_state: "物理状态",
  flash_point: "闪点",
  explosion_limit: "爆炸极限",
  ignition_temp: "引燃温度",
  density: "密度",
  boiling_point: "沸点",
  health_hazard: "健康危害",
  fire_hazard: "火灾爆炸危险",
  leak_response: "泄漏应急处置",
  storage_transport: "储存与运输",
  first_aid: "急救措施",
  protective_measures: "防护措施",
  location: "存放位置",
  max_storage: "最大储存量",
};

const columns = (
  onEdit: (record: HazardousChemical) => void,
  onDelete: (id: string) => void
) => [
  { title: "化学品名称", dataIndex: "name", key: "name", width: 140 },
  { title: "CAS号", dataIndex: "cas_no", key: "cas_no", width: 110, render: (v: string | null) => v || "-" },
  { title: "UN号", dataIndex: "un_no", key: "un_no", width: 80, render: (v: string | null) => v || "-" },
  { title: "物理状态", dataIndex: "physical_state", key: "physical_state", width: 90, render: (v: string | null) => v || "-" },
  { title: "闪点", dataIndex: "flash_point", key: "flash_point", width: 80, render: (v: string | null) => v || "-" },
  { title: "密度", dataIndex: "density", key: "density", width: 80, render: (v: string | null) => v || "-" },
  {
    title: "来源",
    dataIndex: "library_id",
    key: "library_id",
    width: 90,
    render: (v: string | null) => (v ? <Tag color="blue">标准库</Tag> : "-"),
  },
  {
    title: "操作",
    key: "actions",
    width: 120,
    render: (_: unknown, record: HazardousChemical) => (
      <Space>
        <Button type="link" size="small" icon={<EditOutlined />} onClick={() => onEdit(record)} />
        <Popconfirm
          title="确定删除该化学品记录？"
          onConfirm={() => onDelete(record.id)}
        >
          <Button type="link" size="small" danger icon={<DeleteOutlined />} />
        </Popconfirm>
      </Space>
    ),
  },
];

export default function HazardousChemicalsTab({ enterpriseId }: Props) {
  const [data, setData] = useState<HazardousChemical[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [aiModalOpen, setAiModalOpen] = useState(false);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [editing, setEditing] = useState<HazardousChemical | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [form] = Form.useForm();

  const fetchData = async () => {
    setLoading(true);
    try {
      // 页面 catch 自带 toast，跳过全局统一 toast 避免双弹（F4 skip 机制）
      const res = await listChemicals(enterpriseId, { page_size: 200 }, { skipGlobalError: true });
      setData(res.data.items || []);
    } catch (err: any) {
      message.error(err?.response?.data?.detail || "加载失败");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [enterpriseId]);

  const handleAdd = () => {
    setPickerOpen(true);
  };

  const handlePick = (item: ChemicalLibraryItem) => {
    setEditing(null);
    form.resetFields();
    form.setFieldsValue(libraryItemToPrefill(item));
    setPickerOpen(false);
    setModalOpen(true);
  };

  const handleManualAdd = () => {
    setEditing(null);
    form.resetFields();
    setPickerOpen(false);
    setModalOpen(true);
  };

  const handleEdit = (record: HazardousChemical) => {
    setEditing(record);
    form.setFieldsValue(record);
    setModalOpen(true);
  };

  const handleDelete = async (id: string) => {
    try {
      // 页面 catch 自带 toast，跳过全局统一 toast 避免双弹（F4 skip 机制）
      await deleteChemical(enterpriseId, id, { skipGlobalError: true });
      message.success("已删除");
      fetchData();
    } catch (err: any) {
      message.error(err?.response?.data?.detail || "删除失败");
    }
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      setSubmitting(true);
      if (editing) {
        // 页面 catch 自带 toast，跳过全局统一 toast 避免双弹（F4 skip 机制）
        await updateChemical(enterpriseId, editing.id, values as HazardousChemicalUpdate, { skipGlobalError: true });
        message.success("已更新");
      } else {
        // 页面 catch 自带 toast，跳过全局统一 toast 避免双弹（F4 skip 机制）
        await createChemical(enterpriseId, values as HazardousChemicalCreate, { skipGlobalError: true });
        message.success("已添加");
      }
      setModalOpen(false);
      fetchData();
    } catch (err: any) {
      if (err?.errorFields) return;
      message.error(err?.response?.data?.detail || "操作失败");
    } finally {
      setSubmitting(false);
    }
  };

  const formItems = Object.entries(FIELD_LABELS).map(([key, label]) => {
    const isTextArea = [
      "health_hazard", "fire_hazard", "leak_response",
      "storage_transport", "first_aid", "protective_measures",
    ].includes(key);

    return (
      <Form.Item
        key={key}
        name={key}
        label={label}
        rules={key === "name" ? [{ required: true, message: "请输入化学品名称" }] : []}
      >
        {isTextArea ? <Input.TextArea rows={2} /> : <Input />}
      </Form.Item>
    );
  });

  return (
    <div>
      <div style={{ marginBottom: 16 }}>
        <Space>
          <Button type="primary" icon={<PlusOutlined />} onClick={handleAdd}>
            添加危险化学品
          </Button>
          <Button icon={<AppIcon name="ai" size={14} />} onClick={() => setAiModalOpen(true)}>
            AI智能生成
          </Button>
        </Space>
      </div>

      <Table
        dataSource={data}
        rowKey="id"
        columns={columns(handleEdit, handleDelete)}
        loading={loading}
        pagination={{ pageSize: 20 }}
        scroll={{ x: 800 }}
        size="small"
      />

      <Modal
        title={editing ? "编辑危险化学品" : "添加危险化学品"}
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        onOk={handleSubmit}
        confirmLoading={submitting}
        width={700}
        destroyOnHidden
      >
        <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0 24px" }}>
            {formItems}
          </div>
          {/* 隐藏字段：承载库选择来源标记，保证 validateFields 返回 library_id 并随保存落库；
              手动添加时 resetFields 清空、无该键；编辑时由 record.library_id 自动回填。 */}
          <Form.Item name="library_id" hidden>
            <Input />
          </Form.Item>
        </Form>
      </Modal>

      <HazardousChemicalAIGenerateModal
        enterpriseId={enterpriseId}
        visible={aiModalOpen}
        onClose={() => setAiModalOpen(false)}
        onImported={() => {
          setAiModalOpen(false);
          fetchData();
        }}
      />

      <ChemicalLibraryPickerModal
        open={pickerOpen}
        onSelect={handlePick}
        onManual={handleManualAdd}
        onClose={() => setPickerOpen(false)}
      />
    </div>
  );
}
