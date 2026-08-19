import { useState, useEffect, useMemo, useCallback } from "react";
import { App as AntApp, Modal, Input, Button, Tree, Alert, Spin } from "antd";
import type { DataNode } from "antd/es/tree";
import {
  ThunderboltOutlined,
  EditOutlined,
} from "@ant-design/icons";
import { useMutation } from "@tanstack/react-query";
import {
  aiSmartGuide,
  getFullHierarchy,
  createZone,
  createObject,
  createUnit,
  createEvent,
  createMeasure,
} from "@/services/riskManagementService";
import { buildExistingIndex } from "@/utils/smartGuideImport";
import type {
  MethodType,
  MeasureCategory,
  SmartGuideZone,
  SmartGuideObject,
  SmartGuideUnit,
  SmartGuideEvent,
  SmartGuideMeasure,
} from "@/types/riskManagement";

interface Props {
  open: boolean;
  onClose: () => void;
  onRefresh: () => void;
  enterpriseId: string;
}

type Step = "input" | "loading" | "preview";

type NodeType = "zone" | "object" | "unit" | "event" | "measure";

interface TreeNodeMeta {
  nodeType: NodeType;
  source: Record<string, unknown>;
  parentZoneIdx: number;
  parentObjectIdx: number;
  parentUnitIdx: number;
  parentEventIdx: number;
}

interface Counts {
  zones: number;
  objects: number;
  events: number;
  measures: number;
}

const NODE_ICONS: Record<NodeType, string> = {
  zone: "\u{1F3ED}",
  object: "\u{1F4E6}",
  unit: "\u{2699}\u{FE0F}",
  event: "\u{26A0}\u{FE0F}",
  measure: "\u{1F6E1}\u{FE0F}",
};

function getNodeDisplayName(source: Record<string, unknown>, nodeType: NodeType): string {
  switch (nodeType) {
    case "zone":
    case "object":
    case "unit":
      return (source.name as string) || "未命名";
    case "event":
      return (source.accident_type as string) || (source.description as string) || "未命名事件";
    case "measure":
      return (source.description as string) || "未命名措施";
  }
}

function collectAllKeys(hierarchy: SmartGuideZone[]): React.Key[] {
  const keys: React.Key[] = [];
  hierarchy.forEach((z, zi) => {
    keys.push("z-" + zi);
    (z.objects || []).forEach((o, oi) => {
      keys.push("z-" + zi + "-o-" + oi);
      (o.units || []).forEach((u, ui) => {
        keys.push("z-" + zi + "-o-" + oi + "-u-" + ui);
        (u.events || []).forEach((ev, ei) => {
          keys.push("z-" + zi + "-o-" + oi + "-u-" + ui + "-ev-" + ei);
          (ev.measures || []).forEach((_m, mi) => {
            keys.push("z-" + zi + "-o-" + oi + "-u-" + ui + "-ev-" + ei + "-m-" + mi);
          });
        });
      });
      (o.events || []).forEach((ev, ei) => {
        keys.push("z-" + zi + "-o-" + oi + "-ev-" + ei);
        (ev.measures || []).forEach((_m, mi) => {
          keys.push("z-" + zi + "-o-" + oi + "-ev-" + ei + "-m-" + mi);
        });
      });
    });
  });
  return keys;
}

function countChecked(
  hierarchy: SmartGuideZone[],
  checkedKeys: React.Key[],
): Counts {
  const set = new Set(checkedKeys.map(String));
  const c: Counts = { zones: 0, objects: 0, events: 0, measures: 0 };
  hierarchy.forEach((z, zi) => {
    if (set.has("z-" + zi)) c.zones++;
    (z.objects || []).forEach((o, oi) => {
      if (set.has("z-" + zi + "-o-" + oi)) c.objects++;
      (o.units || []).forEach((u, ui) => {
        (u.events || []).forEach((ev, ei) => {
          if (set.has("z-" + zi + "-o-" + oi + "-u-" + ui + "-ev-" + ei)) c.events++;
          (ev.measures || []).forEach((_m, mi) => {
            if (set.has("z-" + zi + "-o-" + oi + "-u-" + ui + "-ev-" + ei + "-m-" + mi)) c.measures++;
          });
        });
      });
      (o.events || []).forEach((ev, ei) => {
        if (set.has("z-" + zi + "-o-" + oi + "-ev-" + ei)) c.events++;
        (ev.measures || []).forEach((_m, mi) => {
          if (set.has("z-" + zi + "-o-" + oi + "-ev-" + ei + "-m-" + mi)) c.measures++;
        });
      });
    });
  });
  return c;
}

export default function RiskSmartGuideModal({
  open,
  onClose,
  onRefresh,
  enterpriseId,
}: Props) {
  const { message: antMessage } = AntApp.useApp();
  const [step, setStep] = useState<Step>("input");
  const [description, setDescription] = useState("");
  const [hierarchy, setHierarchy] = useState<SmartGuideZone[]>([]);
  const [checkedKeys, setCheckedKeys] = useState<React.Key[]>([]);
  const [expandedKeys, setExpandedKeys] = useState<React.Key[]>([]);
  const [editingKey, setEditingKey] = useState<string | null>(null);
  const [editValue, setEditValue] = useState("");
  const [nameOverrides, setNameOverrides] = useState<Record<string, string>>({});

  useEffect(() => {
    if (open) {
      setStep("input");
      setDescription("");
      setHierarchy([]);
      setCheckedKeys([]);
      setExpandedKeys([]);
      setEditingKey(null);
      setNameOverrides({});
    }
  }, [open]);

  const guideMut = useMutation({
    mutationFn: () => aiSmartGuide(enterpriseId, description),
    onSuccess: (data) => {
      setHierarchy(data.hierarchy);
      const allKeys = collectAllKeys(data.hierarchy);
      setCheckedKeys(allKeys);
      setExpandedKeys(allKeys.filter((k) => String(k).startsWith("z-") && String(k).split("-").length === 2));
      setStep("preview");
    },
    onError: (e: Error) => {
      antMessage.error("AI 分析失败: " + (e?.message || "请重试"));
      setStep("input");
    },
  });

  const handleStartAnalysis = () => {
    if (!description.trim()) {
      antMessage.warning("请先描述区域情况");
      return;
    }
    setStep("loading");
    guideMut.mutate();
  };

  const importMut = useMutation({
    mutationFn: async () => {
      const keySet = new Set(checkedKeys.map(String));
      const existing = await getFullHierarchy(enterpriseId);
      const index = buildExistingIndex(existing);
      let created = 0;
      let merged = 0;
      let skipped = 0;

      // 本批次新建集合：避免建议自身重复（分区/对象/单元按名，事件按事故类型，措施按 类别|描述）
      const newZoneIds = new Map<string, string>();
      const newObjectIds = new Map<string, Map<string, string>>();
      const newUnitIds = new Map<string, Map<string, string>>();
      const newEventTypes = new Map<string, Set<string>>();
      const newMeasureKeys = new Map<string, Set<string>>();

      const createMeasures = async (
        eventId: string,
        ev: SmartGuideEvent,
        keyPrefix: string,
        existingMeasureKeys: Set<string>,
      ) => {
        const batchMeasures = newMeasureKeys.get(eventId) ?? new Set<string>();
        newMeasureKeys.set(eventId, batchMeasures);
        for (let mi = 0; mi < (ev.measures || []).length; mi++) {
          const m = ev.measures![mi];
          const mKey = keyPrefix + "-m-" + mi;
          if (!keySet.has(mKey)) continue;
          const mDesc = nameOverrides[mKey] || m.description;
          const mCategory = (m.measure_category as MeasureCategory) || "engineering";
          const dedupeKey = `${mCategory}|${mDesc}`;
          if (existingMeasureKeys.has(dedupeKey) || batchMeasures.has(dedupeKey)) {
            skipped++;
            continue;
          }
          await createMeasure(enterpriseId, eventId, {
            measure_category: mCategory,
            measure_type: m.measure_type || undefined,
            description: mDesc,
            check_items: m.check_items || [],
          });
          batchMeasures.add(dedupeKey);
          created++;
        }
      };

      for (let zi = 0; zi < hierarchy.length; zi++) {
        const zone = hierarchy[zi];
        const zoneKey = "z-" + zi;
        if (!keySet.has(zoneKey)) continue;

        const zoneName = nameOverrides[zoneKey] || zone.name;
        let zoneId: string;
        const existingZoneId = index.zones.get(zoneName);
        if (existingZoneId) {
          zoneId = existingZoneId;
          merged++;
        } else if (newZoneIds.has(zoneName)) {
          zoneId = newZoneIds.get(zoneName)!;
          skipped++;
        } else {
          const createdZone = await createZone(enterpriseId, {
            name: zoneName,
            description: zone.description || undefined,
          });
          zoneId = createdZone.id;
          newZoneIds.set(zoneName, zoneId);
          created++;
        }

        for (let oi = 0; oi < (zone.objects || []).length; oi++) {
          const obj = zone.objects![oi];
          const objKey = zoneKey + "-o-" + oi;
          if (!keySet.has(objKey)) continue;

          const objName = nameOverrides[objKey] || obj.name;
          let objectId: string;
          const existingObjectId = index.objects.get(zoneName)?.get(objName);
          const batchObjects = newObjectIds.get(zoneId) ?? new Map<string, string>();
          newObjectIds.set(zoneId, batchObjects);
          if (existingObjectId) {
            objectId = existingObjectId;
            merged++;
          } else if (batchObjects.has(objName)) {
            objectId = batchObjects.get(objName)!;
            skipped++;
          } else {
            const createdObj = await createObject(enterpriseId, {
              zone_id: zoneId,
              name: objName,
              category: obj.category || undefined,
              is_risk_point: false,
            });
            objectId = createdObj.id;
            batchObjects.set(objName, objectId);
            created++;
          }

          for (let ui = 0; ui < (obj.units || []).length; ui++) {
            const unit = obj.units![ui];
            const unitKey = objKey + "-u-" + ui;
            const unitName = nameOverrides[unitKey] || unit.name;
            let unitId: string;
            const existingUnitId = index.units.get(objectId)?.get(unitName);
            const batchUnits = newUnitIds.get(objectId) ?? new Map<string, string>();
            newUnitIds.set(objectId, batchUnits);
            if (existingUnitId) {
              unitId = existingUnitId;
              merged++;
            } else if (batchUnits.has(unitName)) {
              unitId = batchUnits.get(unitName)!;
              skipped++;
            } else {
              const createdUnit = await createUnit(enterpriseId, objectId, {
                name: unitName,
                unit_type: unit.unit_type || undefined,
              });
              unitId = createdUnit.id;
              batchUnits.set(unitName, unitId);
              created++;
            }

            for (let ei = 0; ei < (unit.events || []).length; ei++) {
              const ev = unit.events![ei];
              const evKey = unitKey + "-ev-" + ei;
              if (!keySet.has(evKey)) continue;

              const evName = nameOverrides[evKey] || ev.accident_type;
              const existingEventId = index.eventIds.get(unitId)?.get(evName);
              if (existingEventId) {
                // 事件已存在：合并模式只补充缺失措施，不重复创建事件
                merged++;
                await createMeasures(existingEventId, ev, evKey, index.measures.get(existingEventId) ?? new Set<string>());
                continue;
              }
              const batchTypes = newEventTypes.get(unitId) ?? new Set<string>();
              if (batchTypes.has(evName)) {
                skipped++;
                continue;
              }
              const createdEv = await createEvent(enterpriseId, unitId, {
                unit_id: unitId,
                accident_type: evName,
                description: ev.description || undefined,
                method_type: (ev.method_type as MethodType) || "LS",
                method_params: ev.method_params || {},
              });
              batchTypes.add(evName);
              newEventTypes.set(unitId, batchTypes);
              created++;
              await createMeasures(createdEv.id, ev, evKey, new Set<string>());
            }
          }

          for (let ei = 0; ei < (obj.events || []).length; ei++) {
            const ev = obj.events![ei];
            const evKey = objKey + "-ev-" + ei;
            if (!keySet.has(evKey)) continue;

            const evName = nameOverrides[evKey] || ev.accident_type;
            const existingEventId = index.eventIds.get(objectId)?.get(evName);
            if (existingEventId) {
              merged++;
              await createMeasures(existingEventId, ev, evKey, index.measures.get(existingEventId) ?? new Set<string>());
              continue;
            }
            const batchTypes = newEventTypes.get(objectId) ?? new Set<string>();
            if (batchTypes.has(evName)) {
              skipped++;
              continue;
            }
            const createdEv = await createEvent(enterpriseId, objectId, {
              object_id: objectId,
              accident_type: evName,
              description: ev.description || undefined,
              method_type: (ev.method_type as MethodType) || "LS",
              method_params: ev.method_params || {},
            });
            batchTypes.add(evName);
            newEventTypes.set(objectId, batchTypes);
            created++;
            await createMeasures(createdEv.id, ev, evKey, new Set<string>());
          }
        }
      }

      return { created, merged, skipped };
    },
    onSuccess: ({ created, merged, skipped }: { created: number; merged: number; skipped: number }) => {
      antMessage.success(`导入完成：新增 ${created} 条，并入现有 ${merged} 条，跳过重复 ${skipped} 条`);
      onRefresh();
      onClose();
    },
    onError: (e: Error) => {
      antMessage.error("导入失败: " + (e?.message || "未知错误"));
    },
  });

  const treeData = useMemo<DataNode[]>(() => {
    function buildMeasures(
      measures: SmartGuideMeasure[],
      zi: number,
      oi: number,
      ui: number,
      ei: number,
      prefix: string,
    ): DataNode[] {
      return measures.map((m, mi) => {
        const key = prefix + "-m-" + mi;
        return {
          key,
          title: "",
          isLeaf: true,
          _meta: {
            nodeType: "measure" as const,
            source: m as unknown as Record<string, unknown>,
            parentZoneIdx: zi,
            parentObjectIdx: oi,
            parentUnitIdx: ui,
            parentEventIdx: ei,
          },
        };
      });
    }

    function buildEvents(
      events: SmartGuideEvent[],
      zi: number,
      oi: number,
      ui: number,
      prefix: string,
    ): DataNode[] {
      return events.map((ev, ei) => {
        const key = prefix + "-ev-" + ei;
        const childNodes = buildMeasures(ev.measures || [], zi, oi, ui, ei, key);
        return {
          key,
          title: "",
          children: childNodes.length > 0 ? childNodes : undefined,
          isLeaf: childNodes.length === 0,
          _meta: {
            nodeType: "event" as const,
            source: ev as unknown as Record<string, unknown>,
            parentZoneIdx: zi,
            parentObjectIdx: oi,
            parentUnitIdx: ui,
            parentEventIdx: ei,
          },
        };
      });
    }

    function buildUnits(
      units: SmartGuideUnit[],
      zi: number,
      oi: number,
      prefix: string,
    ): DataNode[] {
      return units.map((u, ui) => {
        const key = prefix + "-u-" + ui;
        const childNodes = buildEvents(u.events || [], zi, oi, ui, key);
        return {
          key,
          title: "",
          children: childNodes.length > 0 ? childNodes : undefined,
          isLeaf: childNodes.length === 0,
          _meta: {
            nodeType: "unit" as const,
            source: u as unknown as Record<string, unknown>,
            parentZoneIdx: zi,
            parentObjectIdx: oi,
            parentUnitIdx: ui,
            parentEventIdx: -1,
          },
        };
      });
    }

    function buildObjects(
      objects: SmartGuideObject[],
      zi: number,
    ): DataNode[] {
      return objects.map((o, oi) => {
        const key = "z-" + zi + "-o-" + oi;
        const unitNodes = buildUnits(o.units || [], zi, oi, key);
        const directEvNodes = buildEvents(o.events || [], zi, oi, -1, key);
        const allChildren = [...unitNodes, ...directEvNodes];
        return {
          key,
          title: "",
          children: allChildren.length > 0 ? allChildren : undefined,
          isLeaf: allChildren.length === 0,
          _meta: {
            nodeType: "object" as const,
            source: o as unknown as Record<string, unknown>,
            parentZoneIdx: zi,
            parentObjectIdx: oi,
            parentUnitIdx: -1,
            parentEventIdx: -1,
          },
        };
      });
    }

    return hierarchy.map((z, zi) => {
      const key = "z-" + zi;
      const childNodes = buildObjects(z.objects || [], zi);
      return {
        key,
        title: "",
        children: childNodes.length > 0 ? childNodes : undefined,
        isLeaf: childNodes.length === 0,
        _meta: {
          nodeType: "zone" as const,
          source: z as unknown as Record<string, unknown>,
          parentZoneIdx: zi,
          parentObjectIdx: -1,
          parentUnitIdx: -1,
          parentEventIdx: -1,
        },
      };
    });
  }, [hierarchy]);

  const startEdit = useCallback((key: string, currentName: string) => {
    setEditingKey(key);
    setEditValue(currentName);
  }, []);

  const saveEdit = useCallback(() => {
    if (editingKey) {
      setNameOverrides((prev) => ({ ...prev, [editingKey]: editValue }));
    }
    setEditingKey(null);
  }, [editingKey, editValue]);

  const cancelEdit = useCallback(() => {
    setEditingKey(null);
  }, []);

  const titleRender = useCallback(
    (nodeData: DataNode) => {
      const meta = (nodeData as DataNode & { _meta?: TreeNodeMeta })._meta;
      if (!meta) return <span>{String(nodeData.title)}</span>;

      const nodeType = meta.nodeType;
      const key = String(nodeData.key);
      const isEditing = editingKey === key;
      const displayName = nameOverrides[key] || getNodeDisplayName(meta.source, nodeType);

      return (
        <span
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 6,
            maxWidth: "100%",
          }}
        >
          <span style={{ flexShrink: 0 }}>{NODE_ICONS[nodeType]}</span>
          {isEditing ? (
            <span
              style={{ display: "inline-flex", alignItems: "center", gap: 4, flex: 1 }}
              onClick={(e) => e.stopPropagation()}
            >
              <Input
                size="small"
                value={editValue}
                onChange={(e) => setEditValue(e.target.value)}
                onPressEnter={saveEdit}
                style={{ width: 160 }}
                autoFocus
              />
              <Button size="small" type="link" onClick={saveEdit}>
                {"保存"}
              </Button>
              <Button size="small" type="link" onClick={cancelEdit}>
                {"取消"}
              </Button>
            </span>
          ) : (
            <>
              <span
                style={{
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                  flex: 1,
                  minWidth: 0,
                }}
              >
                {displayName}
              </span>
              <Button
                size="small"
                type="link"
                icon={<EditOutlined />}
                onClick={(e) => {
                  e.stopPropagation();
                  startEdit(key, displayName);
                }}
                style={{ flexShrink: 0, padding: "0 4px", fontSize: 12 }}
              />
            </>
          )}
        </span>
      );
    },
    [editingKey, editValue, nameOverrides, startEdit, saveEdit, cancelEdit],
  );

  const handleCheck = useCallback((keys: React.Key[] | { checked: React.Key[]; halfChecked: React.Key[] }) => {
    if (Array.isArray(keys)) {
      setCheckedKeys(keys);
    } else {
      setCheckedKeys(keys.checked);
    }
  }, []);

  const counts = useMemo(() => countChecked(hierarchy, checkedKeys), [hierarchy, checkedKeys]);

  const footer = (() => {
    if (step === "input") {
      return [
        <Button key="cancel" onClick={onClose}>
          {"取消"}
        </Button>,
        <Button
          key="analyze"
          type="primary"
          icon={<ThunderboltOutlined />}
          onClick={handleStartAnalysis}
          loading={guideMut.isPending}
        >
          {"下一步→AI 分析"}
        </Button>,
      ];
    }
    if (step === "loading") {
      return null;
    }
    return [
      <Button key="back" onClick={() => setStep("input")}>
        {"返回修改"}
      </Button>,
      <Button key="cancel" onClick={onClose}>
        {"取消"}
      </Button>,
      <Button
        key="import"
        type="primary"
        loading={importMut.isPending}
        onClick={() => importMut.mutate()}
        disabled={checkedKeys.length === 0}
      >
        {"确认并导入全部"}
      </Button>,
    ];
  })();

  return (
    <Modal
      title="AI 智能生成风险层级"
      open={open}
      onCancel={onClose}
      width={720}
      footer={footer}
      destroyOnHidden
    >
      {step === "input" && (
        <div>
          <div style={{ marginBottom: 8, fontWeight: 500 }}>
            {"请描述需要 AI 分析的区域情况"}
          </div>
          <Input.TextArea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder={"储罐区有3个5000m³原油储罐..."}
            rows={6}
            maxLength={2000}
            showCount
          />
          <div
            style={{
              marginTop: 10,
              padding: "8px 12px",
              background: "#f0f5ff",
              borderRadius: 6,
              fontSize: 13,
              color: "#2f54eb",
              display: "flex",
              alignItems: "flex-start",
              gap: 6,
            }}
          >
            <span style={{ flexShrink: 0 }}>{"💡"}</span>
            <span>
              {"请详细描述区域内的设备、工艺、物料、周边环境等信息，描述越详细，AI 生成的层级结构越准确。支持中文自然语言输入。"}
            </span>
          </div>
        </div>
      )}

      {step === "loading" && (
        <div style={{ textAlign: "center", padding: "60px 0" }}>
          <Spin size="large" />
          <p style={{ marginTop: 20, color: "#8c8c8c", fontSize: 14 }}>
            {"AI 正在分析区域描述，生成风险层级结构…"}
          </p>
        </div>
      )}

      {step === "preview" && (
        <div>
          <Alert
            type="warning"
            showIcon
            message="AI 生成数据请核实后确认导入；同名分区/对象/单元/事件将并入现有树（只补充缺失内容），措施按类别与描述去重"
            style={{ marginBottom: 12 }}
          />

          <div
            style={{
              maxHeight: 420,
              overflow: "auto",
              border: "1px solid #f0f0f0",
              borderRadius: 6,
              padding: "8px 12px",
            }}
          >
            {treeData.length === 0 ? (
              <div style={{ textAlign: "center", padding: 40, color: "#999" }}>
                {"AI 未能生成层级结构，请返回修改描述后重试"}
              </div>
            ) : (
              <Tree
                checkable
                treeData={treeData}
                checkedKeys={checkedKeys}
                expandedKeys={expandedKeys}
                onExpand={(keys) => setExpandedKeys(keys)}
                onCheck={handleCheck}
                titleRender={titleRender}
                showLine={{ showLeafIcon: false }}
                blockNode
                style={{ background: "transparent", fontSize: 13 }}
              />
            )}
          </div>

          <div
            style={{
              marginTop: 12,
              padding: "8px 12px",
              background: "#fafafa",
              borderRadius: 6,
              fontSize: 13,
              color: "#595959",
              display: "flex",
              alignItems: "center",
              gap: 4,
            }}
          >
            <span style={{ fontWeight: 500 }}>{"选中汇总："}</span>
            <span>
              {counts.zones}{"分区 · "}{counts.objects}{"对象 · "}{counts.events}{"事件 · "}{counts.measures}{"措施"}
            </span>
          </div>
        </div>
      )}
    </Modal>
  );
}
