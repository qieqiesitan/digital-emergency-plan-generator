import { useState, useEffect, useMemo } from "react";
import { Modal, Steps, Button, List, Tag, Input, Alert, Spin, Space, message } from "antd";
import {
  CheckCircleOutlined,
  CloseOutlined,
  EditOutlined,
  ExclamationCircleOutlined,
} from "@ant-design/icons";
import { useMutation } from "@tanstack/react-query";
import {
  getMigrationPreview,
  aiMigratePreview,
  executeMigration,
} from "@/services/riskManagementService";
import type {
  MigrationExecutePayload,
  MigrationExecuteResponse,
  MigrationPreviewItem,
  MigrationPreviewResponse,
} from "@/types/riskManagement";

interface Props {
  open: boolean;
  onClose: () => void;
  onRefresh: () => void;
  enterpriseId: string;
}

type Step = 0 | 1;

type ItemStatus = "adopted" | "modified" | "skipped";

interface MigrationItem extends MigrationPreviewItem {
  _key: number;
  status: ItemStatus;
}

interface EditForm {
  zone: string;
  object: string;
  event: string;
}

function mapPreviewData(raw: MigrationPreviewResponse): MigrationItem[] {
  return raw.items.map((item, i) => ({
    ...item,
    _key: i,
    status: "adopted" as ItemStatus,
  }));
}

export default function RiskMigrationWizard({
  open,
  onClose,
  onRefresh,
  enterpriseId,
}: Props) {
  const [step, setStep] = useState<Step>(0);
  const [items, setItems] = useState<MigrationItem[]>([]);
  const [editingKey, setEditingKey] = useState<number | null>(null);
  const [editForm, setEditForm] = useState<EditForm>({ zone: "", object: "", event: "" });
  const [loadingPreview, setLoadingPreview] = useState(false);

  useEffect(() => {
    if (open) {
      setStep(0);
      setItems([]);
      setEditingKey(null);
      loadPreview();
    }
  }, [open, enterpriseId]);

  const loadPreview = async () => {
    setLoadingPreview(true);
    try {
      const preview = await getMigrationPreview(enterpriseId);
      if (!preview || preview.items.length === 0) {
        message.warning("未检测到可迁移的旧版风险源数据");
        setItems([]);
        return;
      }
      setItems(mapPreviewData(preview));
      try {
        const aiPreview = await aiMigratePreview(enterpriseId);
        if (aiPreview?.items?.length) setItems(mapPreviewData(aiPreview));
      } catch {
        message.info("AI 建议不可用，已使用默认映射");
      }
    } catch (e: any) {
      message.error("加载迁移预览失败: " + (e?.message || "请重试"));
      setItems([]);
    } finally {
      setLoadingPreview(false);
    }
  };

  const handleAdopt = (key: number) => {
    setItems((prev) =>
      prev.map((it) => (it._key === key ? { ...it, status: "adopted" as ItemStatus } : it)),
    );
  };

  const handleSkip = (key: number) => {
    setItems((prev) =>
      prev.map((it) => (it._key === key ? { ...it, status: "skipped" as ItemStatus } : it)),
    );
  };

  const startEdit = (item: MigrationItem) => {
    setEditingKey(item._key);
    setEditForm({ zone: item.suggested_zone, object: item.suggested_object, event: item.suggested_event });
  };

  const saveEdit = () => {
    if (editingKey == null) return;
    setItems((prev) =>
      prev.map((it) =>
        it._key === editingKey
          ? {
              ...it,
              suggested_zone: editForm.zone || it.suggested_zone,
              suggested_object: editForm.object || it.suggested_object,
              suggested_event: editForm.event || it.suggested_event,
              status: "modified" as ItemStatus,
            }
          : it,
      ),
    );
    setEditingKey(null);
  };

  const cancelEdit = () => {
    setEditingKey(null);
  };

  const adoptedItems = useMemo(() => items.filter((it) => it.status !== "skipped"), [items]);

  const summary = useMemo(() => {
    const zoneSet = new Set<string>();
    const objectSet = new Set<string>();
    let eventCount = 0;
    adoptedItems.forEach((it) => {
      zoneSet.add(it.suggested_zone);
      objectSet.add(it.suggested_zone + "||" + it.suggested_object);
      eventCount++;
    });
    return { zones: zoneSet.size, objects: objectSet.size, events: eventCount };
  }, [adoptedItems]);

  const migrateMut = useMutation({
    mutationFn: async () => {
      const toMigrate = items.filter((it) => it.status !== "skipped");
      if (toMigrate.length === 0) {
        throw new Error("没有可迁移的项目");
      }
      const mappings: MigrationExecutePayload[] = toMigrate.map((it) => ({
        source_id: it.source_id,
        zone_name: it.suggested_zone,
        object_name: it.suggested_object,
        accident_type: it.suggested_event,
        method_params: it.suggested_params,
      }));
      return executeMigration(enterpriseId, mappings);
    },
    onSuccess: (data: MigrationExecuteResponse) => {
      message.success("成功迁移 " + data.migrated + " 条数据");
      onRefresh();
      onClose();
    },
    onError: (e: Error) => {
      message.error("迁移失败: " + (e?.message || "未知错误"));
    },
  });

  const handleNext = () => {
    if (adoptedItems.length === 0) {
      message.warning("请至少保留一个迁移项目");
      return;
    }
    setStep(1);
  };

  const footer = (() => {
    if (loadingPreview) return null;
    if (step === 0) {
      return [
        <Button key="cancel" onClick={onClose}>
          {"取消"}
        </Button>,
        <Button key="next" type="primary" onClick={handleNext} disabled={items.length === 0}>
          {"下一步"}
        </Button>,
      ];
    }
    return [
      <Button key="back" onClick={() => setStep(0)}>
        {"返回修改"}
      </Button>,
      <Button key="cancel" onClick={onClose}>
        {"取消"}
      </Button>,
      <Button
        key="migrate"
        type="primary"
        loading={migrateMut.isPending}
        onClick={() => migrateMut.mutate()}
      >
        {"确认迁移"}
      </Button>,
    ];
  })();

  const stepItems = [
    { title: "确认映射关系" },
    { title: "确认并执行迁移" },
  ];

  return (
    <Modal
      title="旧版风险源迁移向导"
      open={open}
      onCancel={onClose}
      width={800}
      footer={footer}
      destroyOnHidden
    >
      <Steps current={step} items={stepItems} style={{ marginBottom: 24 }} />

      {loadingPreview && (
        <div style={{ textAlign: "center", padding: "60px 0" }}>
          <Spin size="large" />
          <p style={{ marginTop: 20, color: "#8c8c8c", fontSize: 14 }}>
            {"AI 正在分析旧版风险源数据，生成迁移建议…"}
          </p>
        </div>
      )}

      {!loadingPreview && items.length === 0 && step === 0 && (
        <div style={{ textAlign: "center", padding: 40, color: "#999" }}>
          {"未检测到可迁移的旧版风险源数据"}
        </div>
      )}

      {!loadingPreview && step === 0 && items.length > 0 && (
        <div>
          <Alert
            type="info"
            showIcon
            message={"以下是旧版风险源及 AI 建议的映射关系，请确认或修改后继续"}
            style={{ marginBottom: 16 }}
          />

          <div style={{ maxHeight: 440, overflow: "auto" }}>
            <List
              dataSource={items}
              renderItem={(item) => {
                const isEditing = editingKey === item._key;
                const isSkipped = item.status === "skipped";
                const isModified = item.status === "modified";

                return (
                  <div
                    style={{
                      padding: "12px 0",
                      borderBottom: "1px solid #f0f0f0",
                      opacity: isSkipped ? 0.5 : 1,
                    }}
                  >
                    <div
                      style={{
                        display: "flex",
                        alignItems: "flex-start",
                        justifyContent: "space-between",
                        gap: 16,
                      }}
                    >
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ fontWeight: 500, marginBottom: 4 }}>
                          {item.source_name}
                          {item.source_categories.length > 0 && (
                            <span style={{ marginLeft: 8 }}>
                              {item.source_categories.map((cat) => (
                                <Tag key={cat} color="orange" style={{ marginRight: 4 }}>
                                  {cat}
                                </Tag>
                              ))}
                            </span>
                          )}
                        </div>
                        <div style={{ fontSize: 12, color: "#999", marginBottom: 8 }}>
                          {"位置: "}{item.source_location}
                        </div>

                        {isEditing ? (
                          <div
                            style={{
                              display: "flex",
                              gap: 8,
                              flexWrap: "wrap",
                              padding: "8px 12px",
                              background: "#fafafa",
                              borderRadius: 6,
                            }}
                          >
                            <div>
                              <div style={{ fontSize: 12, color: "#999", marginBottom: 2 }}>
                                {"分区"}
                              </div>
                              <Input
                                size="small"
                                value={editForm.zone}
                                onChange={(e) =>
                                  setEditForm((f) => ({ ...f, zone: e.target.value }))
                                }
                                style={{ width: 140 }}
                              />
                            </div>
                            <div>
                              <div style={{ fontSize: 12, color: "#999", marginBottom: 2 }}>
                                {"对象"}
                              </div>
                              <Input
                                size="small"
                                value={editForm.object}
                                onChange={(e) =>
                                  setEditForm((f) => ({ ...f, object: e.target.value }))
                                }
                                style={{ width: 140 }}
                              />
                            </div>
                            <div>
                              <div style={{ fontSize: 12, color: "#999", marginBottom: 2 }}>
                                {"事件"}
                              </div>
                              <Input
                                size="small"
                                value={editForm.event}
                                onChange={(e) =>
                                  setEditForm((f) => ({ ...f, event: e.target.value }))
                                }
                                style={{ width: 160 }}
                              />
                            </div>
                            <div style={{ display: "flex", alignItems: "flex-end", gap: 4 }}>
                              <Button size="small" type="link" onClick={saveEdit}>
                                {"保存"}
                              </Button>
                              <Button size="small" type="link" onClick={cancelEdit}>
                                {"取消"}
                              </Button>
                            </div>
                          </div>
                        ) : (
                          <div style={{ fontSize: 13 }}>
                            <span style={{ color: "#8c8c8c" }}>
                              {"映射: "}
                            </span>
                            <Tag color="blue">{item.suggested_zone}</Tag>
                            <span style={{ color: "#d9d9d9", margin: "0 2px" }}>{"→"}</span>
                            <Tag color="green">{item.suggested_object}</Tag>
                            <span style={{ color: "#d9d9d9", margin: "0 2px" }}>{"→"}</span>
                            <Tag color="purple">{item.suggested_event}</Tag>
                            {isModified && (
                              <Tag color="orange" style={{ marginLeft: 8 }}>
                                {"已修改"}
                              </Tag>
                            )}
                          </div>
                        )}
                      </div>

                      {!isEditing && (
                        <Space style={{ flexShrink: 0 }}>
                          <Button
                            size="small"
                            type={item.status === "adopted" && !isModified ? "primary" : "default"}
                            icon={<CheckCircleOutlined />}
                            onClick={() => handleAdopt(item._key)}
                          >
                            {"采纳"}
                          </Button>
                          <Button
                            size="small"
                            icon={<EditOutlined />}
                            onClick={() => startEdit(item)}
                          >
                            {"修改"}
                          </Button>
                          <Button
                            size="small"
                            type={isSkipped ? "primary" : "default"}
                            danger={!isSkipped}
                            icon={<CloseOutlined />}
                            onClick={() => handleSkip(item._key)}
                          >
                            {isSkipped ? "已跳过" : "跳过"}
                          </Button>
                        </Space>
                      )}
                    </div>
                  </div>
                );
              }}
            />
          </div>
        </div>
      )}

      {step === 1 && (
        <div>
          <Alert
            type="warning"
            showIcon
            icon={<ExclamationCircleOutlined />}
            message={"迁移操作将创建新的风险层级结构，不会删除原有数据"}
            style={{ marginBottom: 20 }}
          />

          <div
            style={{
              padding: "20px 24px",
              background: "#f6ffed",
              border: "1px solid #b7eb8f",
              borderRadius: 8,
              marginBottom: 20,
            }}
          >
            <div style={{ fontSize: 15, fontWeight: 500, marginBottom: 12 }}>
              {"迁移概览"}
            </div>
            <div style={{ fontSize: 18, fontWeight: 600, color: "#389e0d" }}>
              {"将创建 "}{summary.zones}{" 分区 · "}{summary.objects}{" 对象 · "}{summary.events}{" 事件"}
            </div>
          </div>

          <div style={{ fontWeight: 500, marginBottom: 8 }}>
            {"迁移项目明细 ("}{adoptedItems.length}{" 条)"}
          </div>

          <div style={{ maxHeight: 280, overflow: "auto" }}>
            <List
              size="small"
              dataSource={adoptedItems}
              renderItem={(item) => (
                <List.Item>
                  <span style={{ fontWeight: 500 }}>{item.source_name}</span>
                  <span style={{ color: "#8c8c8c", margin: "0 8px" }}>{"→"}</span>
                  <Tag color="blue">{item.suggested_zone}</Tag>
                  <Tag color="green">{item.suggested_object}</Tag>
                  <Tag color="purple">{item.suggested_event}</Tag>
                  {item.status === "modified" && (
                    <Tag color="orange" style={{ marginLeft: 8 }}>
                      {"已修改"}
                    </Tag>
                  )}
                </List.Item>
              )}
            />
          </div>
        </div>
      )}
    </Modal>
  );
}
