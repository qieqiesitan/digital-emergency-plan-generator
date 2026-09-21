import { useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { App as AntApp, Button, Card, Form, Input, Select, Space, Spin, Tabs, Tag } from "antd";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { PageHeader } from "@/components/common/PageHeader";
import RiskObjectPicker from "@/components/enterprise/majorHazard/RiskObjectPicker";
import UnitChemicalTable from "@/components/enterprise/majorHazard/UnitChemicalTable";
import UnitPolygonEditor from "@/components/enterprise/majorHazard/UnitPolygonEditor";
import {
  buildUnitPrefill,
  isPrefillMarkVisible,
  PREFILL_FIELD_LABELS,
} from "@/components/enterprise/majorHazard/riskObjectPrefill";
import {
  listUnitChemicals,
  listUnits,
  replaceUnitChemicals,
  updateUnit,
} from "@/services/majorHazardService";
import type {
  LinkableRiskObject,
  MajorHazardUnitChemicalPayload,
  MajorHazardUnitPayload,
} from "@/types/majorHazard";

export default function MajorHazardUnitPage() {
  const { id, unitId } = useParams<{ id: string; unitId: string }>();
  const navigate = useNavigate();
  const [sp] = useSearchParams();
  const { message } = AntApp.useApp();
  const queryClient = useQueryClient();
  const [form] = Form.useForm<MajorHazardUnitPayload>();
  const [savingChem, setSavingChem] = useState(false);
  /** 带出时记下"字段 → 当时的值"：值没被改过才继续显示来源标记。 */
  const [prefilled, setPrefilled] = useState<Partial<Record<string, string>>>({});

  // 从台账点进来时路由参数就是 unitId；也支持 ?unitId= 形式
  const effectiveUnitId = unitId ?? sp.get("unitId") ?? "";

  const { data: units, isLoading } = useQuery({
    queryKey: ["major-hazard-units", id],
    queryFn: () => listUnits(id!),
    enabled: !!id,
  });
  const unit = units?.find((u) => u.id === effectiveUnitId);

  const { data: chemData, isLoading: chemLoading } = useQuery({
    queryKey: ["major-hazard-chemicals", effectiveUnitId],
    queryFn: () => listUnitChemicals(effectiveUnitId),
    enabled: !!effectiveUnitId,
  });

  const invalidateUnits = () =>
    queryClient.invalidateQueries({ queryKey: ["major-hazard-units", id] });

  // useWatch 与 useState 必须都在下面的提前 return 之前：放在 return 之后，
  // 加载态与数据态之间切换时 hooks 数量会变，报 "Rendered fewer hooks than expected"。
  const watched = {
    address: Form.useWatch("address", form),
    department: Form.useWatch("department", form),
    responsible_person: Form.useWatch("responsible_person", form),
    responsible_phone: Form.useWatch("responsible_phone", form),
  };

  /** 标记只在"值没被改过"时显示——改过的字段已经不是风险点带出来的值了。 */
  const fieldLabel = (field: keyof typeof watched, text: string) =>
    isPrefillMarkVisible(prefilled, field, watched[field]) ? (
      <span>
        {text}
        <Tag color="blue" style={{ marginInlineStart: 6 }}>
          来自风险点
        </Tag>
      </span>
    ) : (
      text
    );

  const handleRiskObjectLinked = (object: LinkableRiskObject | null) => {
    if (!object) {
      setPrefilled({});
      return;
    }
    const { patch, fields } = buildUnitPrefill(object, form.getFieldsValue());
    if (fields.length === 0) {
      setPrefilled({});
      return;
    }
    form.setFieldsValue(patch);
    setPrefilled(patch);
    message.info(`已从风险点带出 ${fields.length} 项，请检查后保存`);
  };

  if (isLoading) return <Spin />;
  if (!effectiveUnitId) return <Card>未指定单元</Card>;
  if (!unit) return <Card>未找到该单元（可能已删除）</Card>;

  const saveBasic = async () => {
    const values = await form.validateFields();
    await updateUnit(effectiveUnitId, values);
    message.success("已保存");
  };

  /**
   * 表单初始值从 unit 派生。因为 `unit` 到位前上面已提前 return，
   * Form 是在数据就绪后才挂载的，initialValues 一次生效即可，不需要 effect 同步。
   */
  const basicInitial = {
    name: unit.name,
    unit_type: unit.unit_type,
    address: unit.address ?? undefined,
    department: unit.department ?? undefined,
    responsible_person: unit.responsible_person ?? undefined,
    responsible_phone: unit.responsible_phone ?? undefined,
  } as MajorHazardUnitPayload;

  /** 后端返回的品种行 → 表格载荷（字段名与类型对齐）。 */
  const chemicalRows: MajorHazardUnitChemicalPayload[] = (chemData ?? []).map((c) => ({
    chemical_id: c.chemical_id ?? null,
    chemical_name: c.chemical_name,
    physical_state: c.physical_state ?? null,
    storage_location: c.storage_location ?? null,
    q_design_max: c.q_design_max,
    q_actual: c.q_actual ?? null,
    critical_quantity_t: c.critical_quantity_t,
    beta: c.beta,
    beta_source: c.beta_source,
  }));

  const saveChemicals = async (rows: MajorHazardUnitChemicalPayload[]) => {
    // 前端先做一道拦截：缺 Q 或 β 的行不允许提交。
    // 后端写入器也会拒（WritePayloadError），但在这里拦住能给出更明确的定位。
    const bad = rows.findIndex(
      (c) => !c.chemical_name || !c.q_design_max || !c.critical_quantity_t || !c.beta,
    );
    if (bad >= 0) {
      message.warning(`第 ${bad + 1} 行资料不全：品种、设计最大量、临界量、β 都必须填写`);
      return;
    }
    setSavingChem(true);
    try {
      await replaceUnitChemicals(effectiveUnitId, rows);
      message.success("已保存品种清单");
    } finally {
      setSavingChem(false);
    }
  };

  return (
    <>
      <PageHeader
        title={unit.name}
        subtitle="单元详情"
        extra={
          <Space>
            <Button onClick={() => navigate(`/enterprises/${id}/major-hazard`)}>返回台账</Button>
            <Button
              type="primary"
              onClick={() => navigate(`/enterprises/${id}/major-hazard/compute?unitId=${effectiveUnitId}`)}
            >
              去计算
            </Button>
            <Button onClick={() => navigate(`/enterprises/${id}/major-hazard/record?unitId=${effectiveUnitId}`)}>
              档案
            </Button>
          </Space>
        }
      />
      <Tabs
        items={[
          {
            key: "basic",
            label: "基本信息",
            children: (
              <Space orientation="vertical" size="middle" style={{ width: "100%" }}>
                <Card>
                  <Form
                    form={form}
                    layout="vertical"
                    style={{ maxWidth: 560 }}
                    initialValues={basicInitial}
                  >
                    <Form.Item name="name" label="单元名称" rules={[{ required: true }]}>
                      <Input />
                    </Form.Item>
                    <Form.Item name="unit_type" label="单元类型" rules={[{ required: true }]}>
                      <Select
                        options={[
                          { value: "production", label: "生产单元" },
                          { value: "storage", label: "储存单元" },
                        ]}
                      />
                    </Form.Item>
                    <Form.Item
                      name="address"
                      label={fieldLabel("address", PREFILL_FIELD_LABELS.address)}
                    >
                      <Input />
                    </Form.Item>
                    <Form.Item
                      name="department"
                      label={fieldLabel("department", PREFILL_FIELD_LABELS.department)}
                    >
                      <Input />
                    </Form.Item>
                    <Form.Item
                      name="responsible_person"
                      label={fieldLabel("responsible_person", PREFILL_FIELD_LABELS.responsible_person)}
                    >
                      <Input />
                    </Form.Item>
                    <Form.Item
                      name="responsible_phone"
                      label={fieldLabel("responsible_phone", PREFILL_FIELD_LABELS.responsible_phone)}
                    >
                      <Input />
                    </Form.Item>
                    <Button type="primary" onClick={saveBasic}>
                      保存
                    </Button>
                  </Form>
                </Card>
                <Card size="small" title="关联风险点">
                  <RiskObjectPicker
                    enterpriseId={id!}
                    unitId={effectiveUnitId}
                    riskObjectId={unit.risk_object_id}
                    onLinked={handleRiskObjectLinked}
                  />
                </Card>
                <UnitPolygonEditor
                  enterpriseId={id!}
                  unitId={effectiveUnitId}
                  floorId={unit.floor_id}
                  polygon={unit.polygon}
                  onSaved={invalidateUnits}
                />
              </Space>
            ),
          },
          {
            key: "chemicals",
            label: "品种与存量",
            children: (
              <Card loading={chemLoading}>
                <UnitChemicalTable
                  key={effectiveUnitId}
                  enterpriseId={id!}
                  value={chemicalRows}
                  onSave={saveChemicals}
                  saving={savingChem}
                />
              </Card>
            ),
          },
        ]}
      />
    </>
  );
}
