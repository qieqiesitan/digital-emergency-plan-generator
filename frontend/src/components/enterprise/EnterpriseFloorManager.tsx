import { useState } from "react";
import { Button, Input, Modal, Popconfirm, Select, Space, Upload, message } from "antd";
import { DeleteOutlined, EditOutlined, PlusOutlined, UploadOutlined } from "@ant-design/icons";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  listEnterpriseFloors,
  createEnterpriseFloor,
  updateEnterpriseFloor,
  deleteEnterpriseFloor,
  deleteEnterpriseFloorPlan,
  uploadEnterpriseFloorPlan,
} from "@/services/riskMappingWorkbenchService";
import { useRiskMappingWorkbenchStore } from "@/store/riskMappingWorkbenchStore";

const apiErrorMessage = (e: unknown, fallback: string) => {
  const err = e as { response?: { data?: { detail?: unknown } } };
  const detail = err?.response?.data?.detail;
  if (typeof detail === "string") return detail;
  const msg = (detail as { message?: string } | undefined)?.message;
  return msg || fallback;
};

export default function EnterpriseFloorManager({ enterpriseId }: { enterpriseId: string }) {
  const queryClient = useQueryClient();
  const currentFloorId = useRiskMappingWorkbenchStore(s => s.currentFloorId);
  const dirty = useRiskMappingWorkbenchStore(s => s.dirty);
  const setState = useRiskMappingWorkbenchStore.setState;
  const { data: floors = [] } = useQuery({
    queryKey: ["risk-floors", enterpriseId],
    queryFn: () => listEnterpriseFloors(enterpriseId),
  });
  const [modalOpen, setModalOpen] = useState(false);
  const [editId, setEditId] = useState<string | null>(null);
  const [name, setName] = useState("");

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["risk-floors", enterpriseId] });
    queryClient.invalidateQueries({ queryKey: ["risk-workbench", enterpriseId] });
    // 风险分级管控页使用独立楼层键，双向联动保证两边数据一致
    queryClient.invalidateQueries({ queryKey: ["enterprise-floors", enterpriseId] });
  };

  const switchFloor = (floorId: string) => {
    setState({ currentFloorId: floorId, dirty: false, deletedZoneIds: [], deletedRiskPointIds: [] });
    queryClient.invalidateQueries({ queryKey: ["risk-workbench", enterpriseId] });
  };

  const submit = async () => {
    if (!name.trim()) return;
    const doSubmit = async () => {
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
    if (dirty) {
      Modal.confirm({
        title: editId ? "编辑楼层并放弃未保存的改动" : "新建楼层并刷新当前数据",
        content: editId
          ? "当前楼层存在未保存的改动，编辑楼层后将刷新工作台数据，未保存改动将丢失。是否继续？"
          : "当前楼层存在未保存的改动，新建楼层后将刷新工作台数据，未保存改动将丢失。是否继续？",
        okText: "继续",
        okButtonProps: { danger: true },
        cancelText: "取消",
        onOk: () => doSubmit(),
      });
      return;
    }
    await doSubmit();
  };

  const doRemoveFloor = async (floorId: string) => {
    try {
      const remaining = floors.filter(f => f.id !== floorId);
      if (remaining.length === 0) {
        message.warning("企业至少需要保留一个楼层");
        return;
      }
      const current = floors.find(f => f.id === floorId);
      if (current?.is_default) {
        const nextDefault = remaining.find(f => !f.is_default) ?? remaining[0];
        await updateEnterpriseFloor(enterpriseId, nextDefault.id, { is_default: true });
      }
      await deleteEnterpriseFloor(enterpriseId, floorId);
      if (currentFloorId === floorId) {
        setState({ currentFloorId: remaining[0]?.id ?? "", dirty: false, deletedZoneIds: [], deletedRiskPointIds: [] });
      }
      refresh();
    } catch (e) {
      message.error(apiErrorMessage(e, "删除楼层失败（楼层下存在分区或风险点时不可删除）"));
    }
  };

  const doDeletePlan = async () => {
    const activeFloorId = useRiskMappingWorkbenchStore.getState().currentFloorId;
    const current = floors.find(f => f.id === activeFloorId);
    if (!current) return;
    if (!current.floor_plan_url) {
      message.info("当前楼层无平面图");
      return;
    }
    try {
      await deleteEnterpriseFloorPlan(enterpriseId, current.id);
      message.success("平面图已删除");
      refresh();
    } catch (e) {
      message.error(apiErrorMessage(e, "删除平面图失败"));
    }
  };

  const removeFloor = async (floorId: string) => {
    if (useRiskMappingWorkbenchStore.getState().dirty) {
      Modal.confirm({
        title: "删除楼层并放弃未保存的改动",
        content: "当前楼层存在未保存的改动，删除楼层后这些改动将一并丢失，且无法撤销。是否继续删除？",
        okText: "删除楼层",
        okButtonProps: { danger: true },
        cancelText: "取消",
        onOk: () => doRemoveFloor(floorId),
      });
      return;
    }
    await doRemoveFloor(floorId);
  };

  return (
    <Space wrap>
      <Select
        style={{ width: 160 }}
        placeholder="选择楼层"
        value={currentFloorId || undefined}
        options={floors.map(f => ({ label: f.name, value: f.id }))}
        onChange={id => {
          if (id === currentFloorId) return;
          if (useRiskMappingWorkbenchStore.getState().dirty) {
            Modal.confirm({
              title: "切换楼层",
              content: "当前楼层存在未保存的改动，切换后将丢失这些改动，且无法撤销。是否继续切换？",
              okText: "切换并放弃改动",
              okButtonProps: { danger: true },
              cancelText: "取消",
              onOk: () => switchFloor(id),
            });
            return;
          }
          switchFloor(id);
        }}
      />
      <Button
        icon={<PlusOutlined />}
        onClick={() => {
          setEditId(null);
          setName("");
          setModalOpen(true);
        }}
      >
        新建楼层
      </Button>
      <Button
        icon={<EditOutlined />}
        disabled={!currentFloorId}
        onClick={() => {
          const floor = floors.find(f => f.id === currentFloorId);
          if (!floor) return;
          setEditId(floor.id);
          setName(floor.name);
          setModalOpen(true);
        }}
      >
        编辑楼层
      </Button>
      <Popconfirm
        title="删除当前楼层"
        description="删除后无法恢复；楼层下存在分区或风险点时将被拒绝。"
        disabled={!currentFloorId || floors.length <= 1}
        onConfirm={() => removeFloor(currentFloorId)}
      >
        <Button danger icon={<DeleteOutlined />} disabled={!currentFloorId || floors.length <= 1}>
          删除楼层
        </Button>
      </Popconfirm>
      <Upload
        accept="image/png,image/jpeg,image/webp"
        showUploadList={false}
        customRequest={async ({ file, onSuccess, onError }) => {
          const activeFloorId = useRiskMappingWorkbenchStore.getState().currentFloorId;
          const current = floors.find(f => f.id === activeFloorId) || floors[0];
          if (!current) {
            onError?.(new Error("请先选择楼层"));
            return;
          }
          const perform = async () => {
            try {
              await uploadEnterpriseFloorPlan(enterpriseId, current.id, file as File);
              message.success("平面图上传成功");
              refresh();
              onSuccess?.(null);
            } catch (e) {
              onError?.(e as Error);
            }
          };
          if (dirty) {
            Modal.confirm({
              title: "上传平面图并放弃未保存的改动",
              content: "当前楼层存在未保存的改动，上传平面图后将刷新楼层数据，未保存改动将丢失。是否继续上传？",
              okText: "继续上传",
              okButtonProps: { danger: true },
              cancelText: "取消",
              onOk: () => perform(),
            });
            return;
          }
          await perform();
        }}
      >
        <Button icon={<UploadOutlined />}>上传当前楼层平面图</Button>
      </Upload>
      <Popconfirm
        title="删除当前楼层平面图？"
        description="仅清除底图，不影响已绘制的分区和风险点数据。"
        disabled={!currentFloorId || !(floors.find(f => f.id === currentFloorId)?.floor_plan_url)}
        onConfirm={doDeletePlan}
      >
        <Button
          danger
          icon={<DeleteOutlined />}
          disabled={!currentFloorId || !(floors.find(f => f.id === currentFloorId)?.floor_plan_url)}
        >
          删除平面图
        </Button>
      </Popconfirm>
      <Modal
        title={editId ? "编辑楼层" : "新建楼层"}
        open={modalOpen}
        onOk={submit}
        onCancel={() => setModalOpen(false)}
      >
        <Input value={name} onChange={e => setName(e.target.value)} placeholder="楼层名称，如一层" />
      </Modal>
    </Space>
  );
}
