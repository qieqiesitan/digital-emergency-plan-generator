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
  aiMigratePreview,
  createZone,
  createObject,
  createEvent,
} from "@/services/riskManagementService";

interface Props {
  open: boolean;
  onClose: () => void;
  onRefresh: () => void;
  enterpriseId: string;
}

type Step = 0 | 1;

type ItemStatus = "adopted" | "modified" | "skipped";

interface MigrationItem {
  _key: number;
  source_id: string;
  source_name: string;
  source_location: string;
  source_categories: string[];
  suggested_zone: string;
  suggested_object: string;
  suggested_event: string;
  status: ItemStatus;
}

interface EditForm {
  zone: string;
  object: string;
  event: string;
}

function mapPreviewData(raw: Record<string, unknown>[]): MigrationItem[] {
  return raw.map((item, i) => ({
    _key: i,
    source_id: (item.source_id as string) || (item.id as string) || "",
    source_name: (item.source_name as string) || (item.name as string) || "\u672A\u547D\u540D\u98CE\u9669\u6E90",
    source_location: (item.source_location as string) || (item.location as string) || "-",
    source_categories: Array.isArray(item.categories)
      ? item.categories as string[]
      : Array.isArray(item.source_categories)
        ? item.source_categories as string[]
        : [],
    suggested_zone: (item.suggested_zone as string) || (item.zone as string) || "\u672A\u77E5\u5206\u533A",
    suggested_object: (item.suggested_object as string) || (item.object as string) || "\u672A\u77E5\u5BF9\u8C61",
    suggested_event: (item.suggested_event as string) || (item.event as string) || "\u672A\u77E5\u4E8B\u4EF6",
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
      const raw = await aiMigratePreview(enterpriseId);
      if (!raw || raw.length === 0) {
        message.warning("\u672A\u68C0\u6D4B\u5230\u53EF\u8FC1\u79FB\u7684\u65E7\u7248\u98CE\u9669\u6E90\u6570\u636E");
        setItems([]);
      } else {
        setItems(mapPreviewData(raw));
      }
    } catch (e: any) {
      message.error("\u52A0\u8F7D\u8FC1\u79FB\u9884\u89C8\u5931\u8D25: " + (e?.message || "\u8BF7\u91CD\u8BD5"));
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
    const zone = item.status === "modified" ? item.suggested_zone : item.suggested_zone;
    const obj = item.status === "modified" ? item.suggested_object : item.suggested_object;
    const ev = item.status === "modified" ? item.suggested_event : item.suggested_event;
    setEditForm({ zone, object: obj, event: ev });
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
        throw new Error("\u6CA1\u6709\u53EF\u8FC1\u79FB\u7684\u9879\u76EE");
      }

      const zoneCache = new Map<string, string>();
      const objectCache = new Map<string, string>();
      let totalCreated = 0;

      for (const item of toMigrate) {
        const zoneName = item.suggested_zone;
        const objectName = item.suggested_object;
        const cacheKey = zoneName + "||" + objectName;

        if (!zoneCache.has(zoneName)) {
          const zone = await createZone(enterpriseId, { name: zoneName });
          zoneCache.set(zoneName, zone.id);
          totalCreated++;
        }

        if (!objectCache.has(cacheKey)) {
          const obj = await createObject(enterpriseId, {
            zone_id: zoneCache.get(zoneName),
            name: objectName,
          });
          objectCache.set(cacheKey, obj.id);
          totalCreated++;
        }

        await createEvent(enterpriseId, objectCache.get(cacheKey)!, {
          object_id: objectCache.get(cacheKey)!,
          accident_type: item.suggested_event,
        });
        totalCreated++;
      }

      return totalCreated;
    },
    onSuccess: (count: number) => {
      message.success("\u6210\u529F\u8FC1\u79FB " + count + " \u6761\u6570\u636E");
      onRefresh();
      onClose();
    },
    onError: (e: Error) => {
      message.error("\u8FC1\u79FB\u5931\u8D25: " + (e?.message || "\u672A\u77E5\u9519\u8BEF"));
    },
  });

  const handleNext = () => {
    if (adoptedItems.length === 0) {
      message.warning("\u8BF7\u81F3\u5C11\u4FDD\u7559\u4E00\u4E2A\u8FC1\u79FB\u9879\u76EE");
      return;
    }
    setStep(1);
  };

  const footer = (() => {
    if (loadingPreview) return null;
    if (step === 0) {
      return [
        <Button key="cancel" onClick={onClose}>
          {"\u53D6\u6D88"}
        </Button>,
        <Button key="next" type="primary" onClick={handleNext} disabled={items.length === 0}>
          {"\u4E0B\u4E00\u6B65"}
        </Button>,
      ];
    }
    return [
      <Button key="back" onClick={() => setStep(0)}>
        {"\u8FD4\u56DE\u4FEE\u6539"}
      </Button>,
      <Button key="cancel" onClick={onClose}>
        {"\u53D6\u6D88"}
      </Button>,
      <Button
        key="migrate"
        type="primary"
        loading={migrateMut.isPending}
        onClick={() => migrateMut.mutate()}
      >
        {"\u786E\u8BA4\u8FC1\u79FB"}
      </Button>,
    ];
  })();

  const stepItems = [
    { title: "\u786E\u8BA4\u6620\u5C04\u5173\u7CFB" },
    { title: "\u786E\u8BA4\u5E76\u6267\u884C\u8FC1\u79FB" },
  ];

  return (
    <Modal
      title="\u65E7\u7248\u98CE\u9669\u6E90\u8FC1\u79FB\u5411\u5BFC"
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
            {"AI \u6B63\u5728\u5206\u6790\u65E7\u7248\u98CE\u9669\u6E90\u6570\u636E\uFF0C\u751F\u6210\u8FC1\u79FB\u5EFA\u8BAE\u2026"}
          </p>
        </div>
      )}

      {!loadingPreview && items.length === 0 && step === 0 && (
        <div style={{ textAlign: "center", padding: 40, color: "#999" }}>
          {"\u672A\u68C0\u6D4B\u5230\u53EF\u8FC1\u79FB\u7684\u65E7\u7248\u98CE\u9669\u6E90\u6570\u636E"}
        </div>
      )}

      {!loadingPreview && step === 0 && items.length > 0 && (
        <div>
          <Alert
            type="info"
            showIcon
            message={"\u4EE5\u4E0B\u662F\u65E7\u7248\u98CE\u9669\u6E90\u53CA AI \u5EFA\u8BAE\u7684\u6620\u5C04\u5173\u7CFB\uFF0C\u8BF7\u786E\u8BA4\u6216\u4FEE\u6539\u540E\u7EE7\u7EED"}
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
                          {"\u4F4D\u7F6E: "}{item.source_location}
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
                                {"\u5206\u533A"}
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
                                {"\u5BF9\u8C61"}
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
                                {"\u4E8B\u4EF6"}
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
                                {"\u4FDD\u5B58"}
                              </Button>
                              <Button size="small" type="link" onClick={cancelEdit}>
                                {"\u53D6\u6D88"}
                              </Button>
                            </div>
                          </div>
                        ) : (
                          <div style={{ fontSize: 13 }}>
                            <span style={{ color: "#8c8c8c" }}>
                              {"\u6620\u5C04: "}
                            </span>
                            <Tag color="blue">{item.suggested_zone}</Tag>
                            <span style={{ color: "#d9d9d9", margin: "0 2px" }}>{"\u2192"}</span>
                            <Tag color="green">{item.suggested_object}</Tag>
                            <span style={{ color: "#d9d9d9", margin: "0 2px" }}>{"\u2192"}</span>
                            <Tag color="purple">{item.suggested_event}</Tag>
                            {isModified && (
                              <Tag color="orange" style={{ marginLeft: 8 }}>
                                {"\u5DF2\u4FEE\u6539"}
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
                            {"\u91C7\u7EB3"}
                          </Button>
                          <Button
                            size="small"
                            icon={<EditOutlined />}
                            onClick={() => startEdit(item)}
                          >
                            {"\u4FEE\u6539"}
                          </Button>
                          <Button
                            size="small"
                            type={isSkipped ? "primary" : "default"}
                            danger={!isSkipped}
                            icon={<CloseOutlined />}
                            onClick={() => handleSkip(item._key)}
                          >
                            {isSkipped ? "\u5DF2\u8DF3\u8FC7" : "\u8DF3\u8FC7"}
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
            message={"\u8FC1\u79FB\u64CD\u4F5C\u5C06\u521B\u5EFA\u65B0\u7684\u98CE\u9669\u5C42\u7EA7\u7ED3\u6784\uFF0C\u4E0D\u4F1A\u5220\u9664\u539F\u6709\u6570\u636E"}
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
              {"\u8FC1\u79FB\u6982\u89C8"}
            </div>
            <div style={{ fontSize: 18, fontWeight: 600, color: "#389e0d" }}>
              {"\u5C06\u521B\u5EFA "}{summary.zones}{" \u5206\u533A \u00B7 "}{summary.objects}{" \u5BF9\u8C61 \u00B7 "}{summary.events}{" \u4E8B\u4EF6"}
            </div>
          </div>

          <div style={{ fontWeight: 500, marginBottom: 8 }}>
            {"\u8FC1\u79FB\u9879\u76EE\u660E\u7EC6 ("}{adoptedItems.length}{" \u6761)"}
          </div>

          <div style={{ maxHeight: 280, overflow: "auto" }}>
            <List
              size="small"
              dataSource={adoptedItems}
              renderItem={(item) => (
                <List.Item>
                  <span style={{ fontWeight: 500 }}>{item.source_name}</span>
                  <span style={{ color: "#8c8c8c", margin: "0 8px" }}>{"\u2192"}</span>
                  <Tag color="blue">{item.suggested_zone}</Tag>
                  <Tag color="green">{item.suggested_object}</Tag>
                  <Tag color="purple">{item.suggested_event}</Tag>
                  {item.status === "modified" && (
                    <Tag color="orange" style={{ marginLeft: 8 }}>
                      {"\u5DF2\u4FEE\u6539"}
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
