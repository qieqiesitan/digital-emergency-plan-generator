import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  App as AntApp,
  Button,
  Form,
  Input,
  Modal,
  Popconfirm,
  Select,
  Space,
  Table,
  Tag,
  Typography,
} from "antd";
import type { TableColumnsType } from "antd";
import { DeleteOutlined, EditOutlined, PlusOutlined, ThunderboltOutlined } from "@ant-design/icons";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { PageHeader } from "@/components/common/PageHeader";
import {
  createUnit,
  deleteUnit,
  listCalculations,
  listUnits,
  updateUnit,
} from "@/services/majorHazardService";
import type { MajorHazardUnit, MajorHazardUnitPayload } from "@/types/majorHazard";
import { computeConclusionText, levelColor, UNIT_TYPE_LABEL } from "@/utils/majorHazardFormat";

const { Text } = Typography;

/**
 * 「结论」列：读该单元**最近一次快照**，不在打开列表时实时重算。
 *
 * 单元多了以后每次开列表都跑一遍计算会很慢，而且没必要——结论本来就是
 * "上一次固化时的结论"，不是"此刻的结论"。要更新结论得去计算页固化一次。
 */
function UnitConclusion({ unitId }: { unitId: string }) {
  const { data, isLoading } = useQuery({
    queryKey: ["major-hazard-calculations", unitId],
    queryFn: () => listCalculations(unitId),
    staleTime: 60_000,
  });

  if (isLoading) return <Text type="secondary">…</Text>;
  const latest = data?.[0];
  return (
    <Tag color={levelColor(latest?.level)}>{computeConclusionText(latest)}</Tag>
  );
}

/** 最近计算时间，同样读快照列表的第一条。 */
function UnitLastCalc({ unitId }: { unitId: string }) {
  const { data } = useQuery({
    queryKey: ["major-hazard-calculations", unitId],
    queryFn: () => listCalculations(unitId),
    staleTime: 60_000,
  });
  const latest = data?.[0];
  if (!latest?.calculated_at) return <Text type="secondary">—</Text>;
  return <Text>{new Date(latest.calculated_at).toLocaleString("zh-CN")}</Text>;
}

export default function MajorHazardListPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { message } = AntApp.useApp();
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<MajorHazardUnit | null>(null);
  const [form] = Form.useForm<MajorHazardUnitPayload>();

  const { data: units, isLoading } = useQuery({
    queryKey: ["major-hazard-units", id],
    queryFn: () => listUnits(id!),
    enabled: !!id,
  });

  const refresh = () => qc.invalidateQueries({ queryKey: ["major-hazard-units", id] });

  const openCreate = () => {
    setEditing(null);
    form.resetFields();
    setOpen(true);
  };

  const openEdit = (u: MajorHazardUnit) => {
    setEditing(u);
    form.setFieldsValue({
      name: u.name,
      unit_type: u.unit_type,
      address: u.address ?? undefined,
      department: u.department ?? undefined,
      responsible_person: u.responsible_person ?? undefined,
      responsible_phone: u.responsible_phone ?? undefined,
    } as MajorHazardUnitPayload);
    setOpen(true);
  };

  const submit = async () => {
    const values = await form.validateFields();
    try {
      if (editing) {
        await updateUnit(editing.id, values);
        message.success("已保存");
      } else {
        await createUnit(id!, values);
        message.success("已新增单元");
      }
      setOpen(false);
      refresh();
    } catch {
      // 全局拦截器已提示，这里不重复弹
    }
  };

  const columns: TableColumnsType<MajorHazardUnit> = [
    {
      title: "单元名称",
      dataIndex: "name",
      render: (v: string, r) => (
        <a onClick={() => navigate(`/enterprises/${id}/major-hazard/units/${r.id}`)}>{v}</a>
      ),
    },
    {
      title: "类型",
      dataIndex: "unit_type",
      width: 110,
      render: (v: string) => UNIT_TYPE_LABEL[v] ?? v,
    },
    {
      title: "责任部门 / 责任人",
      width: 200,
      render: (_, r) => (
        <Text>
          {r.department || "—"} / {r.responsible_person || "—"}
        </Text>
      ),
    },
    {
      title: "最近计算",
      width: 180,
      render: (_, r) => <UnitLastCalc unitId={r.id} />,
    },
    {
      title: "结论",
      width: 110,
      render: (_, r) => <UnitConclusion unitId={r.id} />,
    },
    {
      title: "操作",
      width: 240,
      render: (_, r) => (
        <Space size="small">
          <a onClick={() => navigate(`/enterprises/${id}/major-hazard/units/${r.id}`)}>详情</a>
          <a
            onClick={() =>
              navigate(`/enterprises/${id}/major-hazard/compute?unitId=${r.id}`)
            }
          >
            <ThunderboltOutlined /> 计算
          </a>
          <a onClick={() => openEdit(r)}>
            <EditOutlined /> 编辑
          </a>
          <Popconfirm
            title="删除该单元？"
            description="该单元下的品种与全部计算快照会一并删除，不可恢复。"
            okType="danger"
            onConfirm={async () => {
              await deleteUnit(r.id);
              message.success("已删除");
              refresh();
            }}
          >
            <a style={{ color: "#cf1322" }}>
              <DeleteOutlined /> 删除
            </a>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <>
      <PageHeader
        title="重大危险源"
        subtitle="按 GB 18218-2018 辨识单元并分级"
        extra={
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
            新增单元
          </Button>
        }
      />
      <Table<MajorHazardUnit>
        rowKey="id"
        loading={isLoading}
        dataSource={units ?? []}
        columns={columns}
        pagination={{ defaultPageSize: 10, showSizeChanger: true }}
        locale={{ emptyText: "尚无重大危险源单元，点击右上角新增" }}
      />

      <Modal
        open={open}
        title={editing ? "编辑单元" : "新增重大危险源单元"}
        onCancel={() => setOpen(false)}
        onOk={submit}
        destroyOnClose
      >
        <Form form={form} layout="vertical" initialValues={{ unit_type: "storage" }}>
          <Form.Item
            name="name"
            label="单元名称"
            rules={[{ required: true, message: "请填写单元名称" }]}
          >
            <Input placeholder="如：罐区A、锅炉房" />
          </Form.Item>
          <Form.Item
            name="unit_type"
            label="单元类型"
            rules={[{ required: true, message: "请选择单元类型" }]}
            extra="GB 18218 3.5/3.6：生产装置及设施属生产单元；储罐区、仓库属储存单元"
          >
            <Select
              options={[
                { value: "production", label: "生产单元" },
                { value: "storage", label: "储存单元" },
              ]}
            />
          </Form.Item>
          <Form.Item name="address" label="所在位置">
            <Input placeholder="如：厂区北侧" />
          </Form.Item>
          <Form.Item name="department" label="责任部门">
            <Input />
          </Form.Item>
          <Form.Item name="responsible_person" label="责任人">
            <Input />
          </Form.Item>
          <Form.Item name="responsible_phone" label="联系电话">
            <Input />
          </Form.Item>
        </Form>
      </Modal>
    </>
  );
}
