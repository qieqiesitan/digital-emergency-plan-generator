import { useState, useEffect, useMemo, useCallback } from "react";
import { App as AntApp, Modal, Input, Button, Tree, Alert, Spin } from "antd";
import type { DataNode } from "antd/es/tree";
import {
  ThunderboltOutlined,
  EditOutlined,
} from "@ant-design/icons";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  aiSmartGuide,
  listZones,
  createZone,
  createObject,
  createUnit,
  createEvent,
  createMeasure,
} from "@/services/riskManagementService";
import { buildImportPlan } from "@/utils/smartGuideImport";
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

  const { data: existingZones = [] } = useQuery({
    queryKey: ["risk-zones", enterpriseId],
    queryFn: () => listZones(enterpriseId),
    enabled: open,
  });
  const existingZoneNames = useMemo(() => new Set(existingZones.map(z => z.name)), [existingZones]);

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
      const { filteredHierarchy, skippedZones } = buildImportPlan(hierarchy, nameOverrides, existingZoneNames);
      let totalCreated = 0;

      for (let zi = 0; zi < filteredHierarchy.length; zi++) {
        const zone = filteredHierarchy[zi];
        const originalZi = hierarchy.indexOf(zone);
        const zoneKey = "z-" + originalZi;
        if (!keySet.has(zoneKey)) continue;

        const zoneName = nameOverrides[zoneKey] || zone.name;
        const createdZone = await createZone(enterpriseId, {
          name: zoneName,
          description: zone.description || undefined,
        });
        totalCreated++;

        for (let oi = 0; oi < (zone.objects || []).length; oi++) {
          const obj = zone.objects![oi];
          const objKey = "z-" + originalZi + "-o-" + oi;
          if (!keySet.has(objKey)) continue;

          const objName = nameOverrides[objKey] || obj.name;
          const createdObj = await createObject(enterpriseId, {
            zone_id: createdZone.id,
            name: objName,
            category: obj.category || undefined,
            is_risk_point: false,
          });
          totalCreated++;

          for (let ui = 0; ui < (obj.units || []).length; ui++) {
            const unit = obj.units![ui];
            const unitKey = "z-" + originalZi + "-o-" + oi + "-u-" + ui;
            const unitName = nameOverrides[unitKey] || unit.name;
            const createdUnit = await createUnit(enterpriseId, createdObj.id, {
              name: unitName,
              unit_type: unit.unit_type || undefined,
            });
            totalCreated++;

            for (let ei = 0; ei < (unit.events || []).length; ei++) {
              const ev = unit.events![ei];
              const evKey = "z-" + originalZi + "-o-" + oi + "-u-" + ui + "-ev-" + ei;
              if (!keySet.has(evKey)) continue;

              const evName = nameOverrides[evKey] || ev.accident_type;
              const createdEv = await createEvent(enterpriseId, createdUnit.id, {
                unit_id: createdUnit.id,
                accident_type: evName,
                description: ev.description || undefined,
                method_type: (ev.method_type as MethodType) || "LS",
                method_params: ev.method_params || {},
              });
              totalCreated++;

              for (let mi = 0; mi < (ev.measures || []).length; mi++) {
                const m = ev.measures![mi];
                const mKey = "z-" + originalZi + "-o-" + oi + "-u-" + ui + "-ev-" + ei + "-m-" + mi;
                if (!keySet.has(mKey)) continue;

                const mDesc = nameOverrides[mKey] || m.description;
                await createMeasure(enterpriseId, createdEv.id, {
                  measure_category: (m.measure_category as MeasureCategory) || "engineering",
                  measure_type: m.measure_type || undefined,
                  description: mDesc,
                  check_items: m.check_items || [],
                });
                totalCreated++;
              }
            }
          }

          for (let ei = 0; ei < (obj.events || []).length; ei++) {
            const ev = obj.events![ei];
            const evKey = "z-" + originalZi + "-o-" + oi + "-ev-" + ei;
            if (!keySet.has(evKey)) continue;

            const evName = nameOverrides[evKey] || ev.accident_type;
            const createdEv = await createEvent(enterpriseId, createdObj.id, {
              object_id: createdObj.id,
              accident_type: evName,
              description: ev.description || undefined,
              method_type: (ev.method_type as MethodType) || "LS",
              method_params: ev.method_params || {},
            });
            totalCreated++;

            for (let mi = 0; mi < (ev.measures || []).length; mi++) {
              const m = ev.measures![mi];
              const mKey = "z-" + originalZi + "-o-" + oi + "-ev-" + ei + "-m-" + mi;
              if (!keySet.has(mKey)) continue;

              const mDesc = nameOverrides[mKey] || m.description;
            await createMeasure(enterpriseId, createdEv.id, {
              measure_category: (m.measure_category as MeasureCategory) || "engineering",
                measure_type: m.measure_type || undefined,
                description: mDesc,
                check_items: m.check_items || [],
              });
              totalCreated++;
            }
          }
        }
      }

      return { count: totalCreated, skipped: skippedZones.length };
    },
    onSuccess: ({ count, skipped }: { count: number; skipped: number }) => {
      antMessage.success(`成功导入 ${count} 条数据${skipped > 0 ? `，跳过 ${skipped} 个重名分区` : ""}`);
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
            message="AI 生成数据请核实后确认导入，确认后可在层级树中继续编辑"
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
