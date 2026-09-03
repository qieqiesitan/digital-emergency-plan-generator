import { useEffect, useState } from "react";
import {
  App as AntApp, Button, Drawer, Form, Input, Modal, Popconfirm, Space, Table, Tag,
} from "antd";
import { DeleteOutlined, EditOutlined, PlusOutlined, ImportOutlined } from "@ant-design/icons";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { PageHeader } from "@/components/common/PageHeader";
import {
  collectChemical, collectEnterprises, createLibraryItem, deleteLibraryItem,
  listEnterpriseChemicals, listLibrary, updateLibraryItem,
} from "@/services/chemicalLibraryService";
import type { ChemicalLibraryItem, ChemicalLibraryUpdate, CollectEnterpriseOption } from "@/types/chemicalLibrary";
import type { HazardousChemical } from "@/types/hazardousChemical";

const { TextArea } = Input;

const FORM_ITEMS: { key: string; label: string; textarea?: boolean; span?: 1 | 2 }[] = [
  { key: "name", label: "化学品名称" },
  { key: "alias", label: "别名（多个用；分隔）" },
  { key: "cas_no", label: "CAS号" },
  { key: "remark", label: "备注（如：剧毒）" },
  { key: "un_no", label: "UN号" },
  { key: "physical_state", label: "物理状态" },
  { key: "flash_point", label: "闪点" },
  { key: "explosion_limit", label: "爆炸极限" },
  { key: "ignition_temp", label: "引燃温度" },
  { key: "density", label: "密度" },
  { key: "boiling_point", label: "沸点" },
  { key: "health_hazard", label: "健康危害", textarea: true, span: 2 },
  { key: "fire_hazard", label: "火灾爆炸危险", textarea: true, span: 2 },
  { key: "leak_response", label: "泄漏应急处置", textarea: true, span: 2 },
  { key: "storage_transport", label: "储存与运输", textarea: true, span: 2 },
  { key: "first_aid", label: "急救措施", textarea: true, span: 2 },
  { key: "protective_measures", label: "防护措施", textarea: true, span: 2 },
];

function errMsg(e: unknown): string {
  if (e instanceof Error) return e.message;
  const d = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
  return d || "未知错误";
}

export default function ChemicalLibraryManagePage() {
  const { message } = AntApp.useApp();
  const queryClient = useQueryClient();
  const [keyword, setKeyword] = useState("");
  const [page, setPage] = useState(1);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [editing, setEditing] = useState<ChemicalLibraryItem | null>(null);
  const [collectOpen, setCollectOpen] = useState(false);
  const [entOptions, setEntOptions] = useState<CollectEnterpriseOption[]>([]);
  const [entKeyword, setEntKeyword] = useState("");
  const [selectedEnt, setSelectedEnt] = useState<string | null>(null);
  const [entChemicals, setEntChemicals] = useState<HazardousChemical[]>([]);
  const [chemLoading, setChemLoading] = useState(false);
  const [collectingId, setCollectingId] = useState<string | null>(null);
  const [form] = Form.useForm();

  const { data, isLoading } = useQuery({
    queryKey: ["chemical-library", keyword, page],
    queryFn: () => listLibrary(keyword || undefined, { page, page_size: 20 }),
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["chemical-library"] });
  };

  const openCreate = () => {
    setEditing(null);
    form.resetFields();
    setDrawerOpen(true);
  };

  const openEdit = (record: ChemicalLibraryItem) => {
    setEditing(record);
    form.setFieldsValue(record);
    setDrawerOpen(true);
  };

  const handleSave = async () => {
    const values = await form.validateFields();
    try {
      if (editing) {
        await updateLibraryItem(editing.id, values as ChemicalLibraryUpdate);
        message.success("已更新");
      } else {
        await createLibraryItem(values);
        message.success("已创建");
      }
      setDrawerOpen(false);
      invalidate();
    } catch (e) {
      message.error(errMsg(e));
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await deleteLibraryItem(id);
      message.success("已删除（企业已添加的数据不受影响）");
      invalidate();
    } catch (e) {
      message.error(errMsg(e));
    }
  };

  // ── 收录 ──
  useEffect(() => {
    if (!collectOpen) return;
    collectEnterprises("").then(setEntOptions).catch(() => setEntOptions([]));
  }, [collectOpen]);

  const searchEnt = async (kw: string) => {
    setEntKeyword(kw);
    try {
      const rows = await collectEnterprises(kw);
      setEntOptions(rows);
    } catch {
      message.error("企业搜索失败");
    }
  };

  const pickEnt = async (entId: string) => {
    setSelectedEnt(entId);
    setChemLoading(true);
    try {
      const rows = await listEnterpriseChemicals(entId);
      setEntChemicals(rows);
    } catch (e) {
      message.error(errMsg(e));
      setEntChemicals([]);
    } finally {
      setChemLoading(false);
    }
  };

  const doCollect = async (chem: HazardousChemical) => {
    if (!selectedEnt) return;
    setCollectingId(chem.id);
    try {
      await collectChemical(selectedEnt, chem.id);
      message.success(`已收录「${chem.name}」`);
      invalidate();
      await pickEnt(selectedEnt);
    } catch (e) {
      message.error(errMsg(e));
    } finally {
      setCollectingId(null);
    }
  };

  const columns = [
    {
      title: "化学品名称",
      dataIndex: "name",
      key: "name",
      width: 220,
      render: (v: string, record: ChemicalLibraryItem) => (
        <Space size={4}>
          <span>{v}</span>
          {record.remark === "剧毒" && <Tag color="red">剧毒</Tag>}
        </Space>
      ),
    },
    {
      title: "别名",
      dataIndex: "alias",
      key: "alias",
      width: 220,
      ellipsis: true,
      render: (v: string | null) => v || "-",
    },
    { title: "CAS号", dataIndex: "cas_no", key: "cas_no", width: 130, render: (v: string | null) => v || "-" },
    { title: "UN号", dataIndex: "un_no", key: "un_no", width: 90, render: (v: string | null) => v || "-" },
    { title: "物理状态", dataIndex: "physical_state", key: "physical_state", width: 100, render: (v: string | null) => v || "-" },
    { title: "闪点", dataIndex: "flash_point", key: "flash_point", width: 100, render: (v: string | null) => v || "-" },
    {
      title: "操作",
      key: "actions",
      width: 140,
      render: (_: unknown, record: ChemicalLibraryItem) => (
        <Space>
          <Button type="link" size="small" icon={<EditOutlined />} onClick={() => openEdit(record)} />
          <Popconfirm
            title="仅删除库条目，企业已添加的数据不受影响。确定删除？"
            onConfirm={() => handleDelete(record.id)}
          >
            <Button type="link" size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <PageHeader
        title="化学品库管理"
        subtitle="系统级危化品 MSDS 公共库：企业添加时可从库中选择并自动预填。"
      />
      <Space style={{ marginBottom: 16 }}>
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>新增条目</Button>
        <Button icon={<ImportOutlined />} onClick={() => setCollectOpen(true)}>从企业台账收录</Button>
        <Input.Search
          placeholder="按名称 / 别名 / CAS / UN 搜索"
          allowClear
          enterButton
          onSearch={(v) => { setKeyword(v.trim()); setPage(1); }}
          style={{ width: 300 }}
        />
      </Space>
      <Table
        rowKey="id"
        size="small"
        loading={isLoading}
        columns={columns}
        dataSource={data?.data.items || []}
        pagination={{
          current: page,
          pageSize: 20,
          total: data?.data.total || 0,
          onChange: setPage,
          showTotal: (t) => `共 ${t} 条`,
        }}
        scroll={{ x: 1200 }}
      />

      <Drawer
        title={editing ? "编辑库条目" : "新增库条目"}
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        width={720}
        destroyOnHidden
        extra={
          <Space>
            <Button onClick={() => setDrawerOpen(false)}>取消</Button>
            <Button type="primary" onClick={handleSave}>保存</Button>
          </Space>
        }
      >
        <Form form={form} layout="vertical">
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0 24px" }}>
            {FORM_ITEMS.map((f) => (
              <Form.Item
                key={f.key}
                name={f.key}
                label={f.label}
                rules={f.key === "name" ? [{ required: true, message: "请输入化学品名称" }] : []}
                style={f.span === 2 ? { gridColumn: "1 / -1" } : undefined}
              >
                {f.textarea ? <TextArea rows={3} /> : <Input />}
              </Form.Item>
            ))}
          </div>
        </Form>
      </Drawer>

      <Modal
        title="从企业台账收录到公共库"
        open={collectOpen}
        onCancel={() => setCollectOpen(false)}
        footer={null}
        width={860}
      >
        <Input.Search
          placeholder="搜索企业"
          allowClear
          value={entKeyword}
          onChange={(e) => setEntKeyword(e.target.value)}
          onSearch={searchEnt}
          style={{ marginBottom: 12 }}
        />
        <Space wrap style={{ marginBottom: 12 }}>
          {entOptions.map((o) => (
            <Tag
              key={o.id}
              color={selectedEnt === o.id ? "blue" : undefined}
              style={{ cursor: "pointer" }}
              onClick={() => pickEnt(o.id)}
            >
              {o.name}
            </Tag>
          ))}
        </Space>
        {selectedEnt && (
          <Table
            rowKey="id"
            size="small"
            loading={chemLoading}
            dataSource={entChemicals}
            pagination={false}
            columns={[
              { title: "化学品名称", dataIndex: "name", key: "name" },
              { title: "CAS号", dataIndex: "cas_no", key: "cas_no", render: (v: string | null) => v || "-" },
              { title: "存放位置", dataIndex: "location", key: "location", render: (v: string | null) => v || "-" },
              {
                title: "操作",
                key: "act",
                width: 100,
                render: (_: unknown, c: HazardousChemical) => (
                  <Button
                    type="link"
                    size="small"
                    loading={collectingId === c.id}
                    onClick={() => doCollect(c)}
                  >
                    收录
                  </Button>
                ),
              },
            ]}
          />
        )}
      </Modal>
    </div>
  );
}
