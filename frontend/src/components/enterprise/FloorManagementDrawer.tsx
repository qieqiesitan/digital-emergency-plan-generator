import { useCallback, useState } from "react";
import { App, Button, Drawer, Input, List, Modal, Popconfirm, Space, Tag, Typography } from "antd";
import { DeleteOutlined, EditOutlined, PlusOutlined } from "@ant-design/icons";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  listEnterpriseFloors,
  createEnterpriseFloor,
  updateEnterpriseFloor,
  deleteEnterpriseFloor,
} from "@/services/riskMappingWorkbenchService";
import type { EnterpriseFloor } from "@/types/riskMappingWorkbench";

interface Props {
  enterpriseId: string;
  open: boolean;
  onClose: () => void;
  onChanged?: () => void;
}

const apiErrorMessage = (e: unknown, fallback: string) => {
  const err = e as { response?: { data?: { detail?: unknown } } };
  const detail = err?.response?.data?.detail;
  if (typeof detail === "string") return detail;
  const msg = (detail as { message?: string } | undefined)?.message;
  return msg || fallback;
};

export default function FloorManagementDrawer({ enterpriseId, open, onClose, onChanged }: Props) {
  const { message } = App.useApp();
  const queryClient = useQueryClient();
  const { data: floors = [] } = useQuery({
    queryKey: ["enterprise-floors", enterpriseId],
    queryFn: () => listEnterpriseFloors(enterpriseId),
    enabled: open,
  });
  const [modalOpen, setModalOpen] = useState(false);
  const [editId, setEditId] = useState<string | null>(null);
  const [name, setName] = useState("");

  const refresh = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ["enterprise-floors", enterpriseId] });
    queryClient.invalidateQueries({ queryKey: ["risk-floors", enterpriseId] });
    onChanged?.();
  }, [queryClient, enterpriseId, onChanged]);

  const openCreate = () => {
    setEditId(null);
    setName("");
    setModalOpen(true);
  };

  const openRename = (f: EnterpriseFloor) => {
    setEditId(f.id);
    setName(f.name);
    setModalOpen(true);
  };

  const submit = async () => {
    if (!name.trim()) return;
    try {
      if (editId) {
        await updateEnterpriseFloor(enterpriseId, editId, { name: name.trim() });
      } else {
        await createEnterpriseFloor(enterpriseId, { name: name.trim(), sort_order: floors.length });
      }
      setModalOpen(false);
      setName("");
      setEditId(null);
      refresh();
    } catch (e) {
      message.error(apiErrorMessage(e, "保存楼层失败"));
    }
  };

  const setDefault = async (f: EnterpriseFloor) => {
    if (f.is_default) return;
    try {
      await updateEnterpriseFloor(enterpriseId, f.id, { is_default: true });
      refresh();
    } catch (e) {
      message.error(apiErrorMessage(e, "设置默认楼层失败"));
    }
  };

  const removeFloor = (f: EnterpriseFloor) => {
    const zoneCount = f.zone_count ?? 0;
    const pointCount = f.risk_point_count ?? 0;
    const cascades = zoneCount > 0 || pointCount > 0;
    Modal.confirm({
      title: `确认删除楼层「${f.name}」？`,
      content: cascades
        ? `该楼层下有 ${zoneCount} 个分区、${pointCount} 个风险点，删除将一并级联删除其全部对象、单元、事件与管控措施，且无法恢复。`
        : "删除后无法恢复。",
      okText: "确认删除",
      okButtonProps: { danger: true },
      cancelText: "取消",
      onOk: async () => {
        try {
          await deleteEnterpriseFloor(enterpriseId, f.id);
          refresh();
        } catch (e) {
          message.error(apiErrorMessage(e, "删除楼层失败"));
        }
      },
    });
  };

  return (
    <>
      <Drawer title="楼层管理" open={open} onClose={onClose} width={420}>
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreate} block style={{ marginBottom: 12 }}>
          添加楼层
        </Button>
        <List
          dataSource={floors}
          renderItem={(f) => (
            <List.Item
              actions={[
                !f.is_default ? (
                  <Button key="default" type="link" size="small" onClick={() => setDefault(f)}>
                    设为默认
                  </Button>
                ) : null,
                <Button key="rename" type="link" size="small" icon={<EditOutlined />} onClick={() => openRename(f)}>
                  重命名
                </Button>,
                <Popconfirm
                  key="delete"
                  title={`删除楼层「${f.name}」？`}
                  description="删除前将展示楼层下的分区/风险点数量并二次确认。"
                  onConfirm={() => removeFloor(f)}
                >
                  <Button type="link" size="small" danger icon={<DeleteOutlined />}>
                    删除
                  </Button>
                </Popconfirm>,
              ]}
            >
              <List.Item.Meta
                title={
                  <Space>
                    <span>{f.name}</span>
                    {f.is_default && <Tag color="blue">默认</Tag>}
                  </Space>
                }
                description={`${f.zone_count ?? 0} 分区 · ${f.risk_point_count ?? 0} 风险点`}
              />
            </List.Item>
          )}
        />
        <Typography.Text type="secondary" style={{ display: "block", marginTop: 12 }}>
          平面图上传与分区绘制请在「四色分布图工作台」进行。
        </Typography.Text>
      </Drawer>

      <Modal
        title={editId ? "重命名楼层" : "添加楼层"}
        open={modalOpen}
        onOk={submit}
        onCancel={() => setModalOpen(false)}
        okText="保存"
        cancelText="取消"
      >
        <Input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="请输入楼层名称，如：三层"
          maxLength={50}
          onPressEnter={submit}
          autoFocus
        />
      </Modal>
    </>
  );
}
