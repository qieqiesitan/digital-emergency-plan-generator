import { useState, useMemo } from "react";
import {
  Drawer, Form, Input, Select, Button, Segmented, Radio,
  Space, Tag, message, Divider,
} from "antd";
import { RobotOutlined } from "@ant-design/icons";
import { computeRiskLS, computeRiskLEC, getCellClass, ACCIDENT_TYPES, RISK_LEVEL_COLORS } from "@/utils/riskMethodEngine";
import { aiSuggestEvents } from "@/services/riskManagementService";
import type { MethodType } from "@/types/riskManagement";

// ─── L / S label definitions ────────────────────────────────────
const L_LABELS: Record<number, string> = {
  1: "极低 - 事故几乎不可能发生",
  2: "低 - 事故不太可能发生",
  3: "中等 - 事故可能发生",
  4: "高 - 事故很可能发生",
  5: "极高 - 事故几乎必然发生",
};

const S_LABELS: Record<number, string> = {
  1: "轻微 - 轻微伤害或无伤害",
  2: "一般 - 轻微伤害，需医疗处理",
  3: "较大 - 较大伤害，需住院治疗",
  4: "重大 - 严重伤害或多人受伤",
  5: "特别重大 - 多人死亡或重大财产损失",
};

const L_SHORT: Record<number, string> = { 1: "极低", 2: "低", 3: "中等", 4: "高", 5: "极高" };
const S_SHORT: Record<number, string> = { 1: "轻微", 2: "一般", 3: "较大", 4: "重大", 5: "特别重大" };

const LEC_L_OPTIONS = [
  { value: 0.1, label: "0.1 - 实际不可能" },
  { value: 0.5, label: "0.5 - 极不可能" },
  { value: 1, label: "1 - 可能性小，完全意外" },
  { value: 2, label: "2 - 可能，但不经常" },
  { value: 3, label: "3 - 可能" },
  { value: 6, label: "6 - 相当可能" },
  { value: 10, label: "10 - 完全可以预料" },
];

const LEC_E_OPTIONS = [
  { value: 0.5, label: "0.5 - 每年一次" },
  { value: 1, label: "1 - 每月一次" },
  { value: 2, label: "2 - 每周一次" },
  { value: 3, label: "3 - 每日一次" },
  { value: 6, label: "6 - 每班数次" },
  { value: 10, label: "10 - 连续暴露" },
];

const LEC_C_OPTIONS = [
  { value: 1, label: "1 - 轻微，仅需急救" },
  { value: 3, label: "3 - 较小，需医疗处理" },
  { value: 7, label: "7 - 严重，重伤" },
  { value: 15, label: "15 - 非常严重，1人死亡" },
  { value: 40, label: "40 - 灾难，数人死亡" },
  { value: 100, label: "100 - 大灾难，多人死亡" },
];

const DIRECT_LEVELS = [
  { value: 1, label: "低" },
  { value: 2, label: "一般" },
  { value: 3, label: "较大" },
  { value: 4, label: "重大" },
];

type MethodTypeKey = "LS" | "LEC" | "COAL_LS" | "DIRECT";

interface RiskEventFormValues {
  accident_type: string;
  description?: string;
  trigger_conditions?: string;
  consequences?: string;
  method_type?: string;
  method_params?: Record<string, number>;
}

interface Props {
  open: boolean;
  onClose: () => void;
  onSubmit: (values: RiskEventFormValues) => void;
  initialValues?: RiskEventFormValues;
  enterpriseId: string;
  defaultMethodType?: MethodType;
}

export default function RiskEventForm({
  open, onClose, onSubmit, initialValues, enterpriseId, defaultMethodType,
}: Props) {
  const [form] = Form.useForm<RiskEventFormValues>();
  const [methodType, setMethodType] = useState<MethodTypeKey>(
    (defaultMethodType as MethodTypeKey) ?? "LS",
  );
  const [lValue, setLValue] = useState<number>(1);
  const [sValue, setSValue] = useState<number>(1);
  const [lecL, setLecL] = useState<number>(1);
  const [lecE, setLecE] = useState<number>(3);
  const [lecC, setLecC] = useState<number>(7);
  const [aiLoading, setAiLoading] = useState(false);

  const riskResult = useMemo(() => {
    if (methodType === "LS" || methodType === "COAL_LS") {
      return computeRiskLS(lValue, sValue);
    }
    if (methodType === "LEC") {
      return computeRiskLEC(lecL, lecE, lecC);
    }
    return null;
  }, [methodType, lValue, sValue, lecL, lecE, lecC]);

  const directLevel = Form.useWatch("method_params", form);

  const matrixData = useMemo(() => {
    const rows: { l: number; s: number; r: number; cls: string }[][] = [];
    for (let s = 5; s >= 1; s--) {
      const row: typeof rows[0] = [];
      for (let l = 1; l <= 5; l++) {
        const r = l * s;
        row.push({ l, s, r, cls: getCellClass(r) });
      }
      rows.push(row);
    }
    return rows;
  }, []);

  const cellColor = (cls: string) => {
    switch (cls) {
      case "lvl-red": return "#ff4d4f";
      case "lvl-orange": return "#fa8c16";
      case "lvl-yellow": return "#fadb14";
      case "lvl-green": return "#52c41a";
      default: return "#52c41a";
    }
  };

  const handleAISuggest = async () => {
    const base = form.getFieldsValue();
    setAiLoading(true);
    try {
      const results = await aiSuggestEvents(enterpriseId, {
        context: {
          accident_type: base.accident_type,
          description: base.description,
          trigger_conditions: base.trigger_conditions,
          consequences: base.consequences,
          method_type: methodType,
        },
      });
      if (results && results.length > 0) {
        const first = results[0] as Record<string, unknown>;
        form.setFieldsValue({
          accident_type: (first.accident_type as string) ?? base.accident_type,
          description: (first.description as string) ?? base.description,
          trigger_conditions: (first.trigger_conditions as string) ?? base.trigger_conditions,
          consequences: (first.consequences as string) ?? base.consequences,
          method_type: (first.method_type as string) ?? methodType,
        });
        if (first.method_params) {
          const mp = first.method_params as Record<string, number>;
          if (mp.L !== undefined) { setLValue(mp.L); setSValue(mp.S ?? 1); }
          if (mp.E !== undefined) { setLecL(mp.L ?? 1); setLecE(mp.E ?? 3); setLecC(mp.C ?? 7); }
          form.setFieldsValue({ method_params: mp });
        }
        message.success("AI 分析完成，已自动填入");
      } else {
        message.info("AI 未返回建议");
      }
    } catch {
      message.error("AI 分析失败");
    } finally {
      setAiLoading(false);
    }
  };

  const handleFinish = (values: RiskEventFormValues) => {
    let params: Record<string, number> = {};
    if (methodType === "LS" || methodType === "COAL_LS") {
      params = { L: lValue, S: sValue };
    } else if (methodType === "LEC") {
      params = { L: lecL, E: lecE, C: lecC };
    } else if (methodType === "DIRECT") {
      const lv = values.method_params?.level ?? 1;
      params = { level: lv };
    }
    onSubmit({
      ...values,
      method_type: methodType,
      method_params: params,
    });
  };

  return (
    <Drawer
      title={initialValues ? "编辑风险事件" : "新增风险事件"}
      open={open}
      onClose={onClose}
      width={560}
      styles={{ body: { paddingBottom: 80 } }}
      extra={
        <Space>
          <Button onClick={onClose}>取消</Button>
          <Button type="primary" onClick={() => form.submit()}>
            保存
          </Button>
        </Space>
      }
    >
      <Form
        form={form}
        layout="vertical"
        initialValues={initialValues}
        onFinish={handleFinish}
      >
        {/* ─── Section 1: Basic info ───────────────────────────── */}
        <Divider orientation="left" plain style={{ fontSize: 13 }}>基础信息</Divider>

        <Form.Item
          name="accident_type"
          label="事故类型"
          rules={[{ required: true, message: "请选择事故类型" }]}
        >
          <Select
            showSearch
            placeholder="选择 GB6441 事故类型"
            options={ACCIDENT_TYPES.map((t) => ({ value: t, label: t }))}
            filterOption={(input, option) =>
              (option?.label as string)?.includes(input) ?? false
            }
          />
        </Form.Item>

        <Form.Item name="description" label="事件描述">
          <Input.TextArea
            rows={3}
            placeholder="描述该风险事件的具体情形"
          />
        </Form.Item>

        <Form.Item name="trigger_conditions" label="触发条件">
          <Input.TextArea
            rows={2}
            placeholder="描述可能触发该事件的工况、环境或人为因素"
          />
        </Form.Item>

        <Form.Item name="consequences" label="可能后果">
          <Input.TextArea
            rows={2}
            placeholder="描述事件发生后可能造成的人员伤亡、财产损失等"
          />
        </Form.Item>

        <Button
          icon={<RobotOutlined />}
          onClick={handleAISuggest}
          loading={aiLoading}
          style={{ marginBottom: 16 }}
          block
        >
          ✨ AI 分析并建议
        </Button>

        {/* ─── Section 2: Method params ────────────────────────── */}
        <Divider orientation="left" plain style={{ fontSize: 13 }}>评价方法与参数</Divider>

        <Form.Item label="评价方法">
          <Segmented
            block
            value={methodType}
            onChange={(val) => setMethodType(val as MethodTypeKey)}
            options={[
              { value: "LS", label: "LS 矩阵" },
              { value: "LEC", label: "LEC 评价" },
              { value: "COAL_LS", label: "煤矿 LS" },
              { value: "DIRECT", label: "直接判定" },
            ]}
          />
        </Form.Item>

        {/* LS / COAL_LS */}
        {(methodType === "LS" || methodType === "COAL_LS") && (
          <>
            <Form.Item label="可能性 L">
              <Radio.Group
                value={lValue}
                onChange={(e) => setLValue(e.target.value)}
                style={{ display: "flex", flexDirection: "column", gap: 8 }}
              >
                {[1, 2, 3, 4, 5].map((v) => (
                  <Radio.Button
                    key={v}
                    value={v}
                    style={{
                      height: "auto",
                      padding: "8px 12px",
                      lineHeight: 1.5,
                      borderRadius: 6,
                      marginBottom: v < 5 ? 0 : undefined,
                    }}
                  >
                    <strong>{L_SHORT[v]}</strong>
                    <div style={{ fontSize: 12, color: "#666" }}>
                      {L_LABELS[v]?.split(" - ")[1]}
                    </div>
                  </Radio.Button>
                ))}
              </Radio.Group>
            </Form.Item>

            <Form.Item label="严重性 S">
              <Radio.Group
                value={sValue}
                onChange={(e) => setSValue(e.target.value)}
                style={{ display: "flex", flexDirection: "column", gap: 8 }}
              >
                {[1, 2, 3, 4, 5].map((v) => (
                  <Radio.Button
                    key={v}
                    value={v}
                    style={{
                      height: "auto",
                      padding: "8px 12px",
                      lineHeight: 1.5,
                      borderRadius: 6,
                      marginBottom: v < 5 ? 0 : undefined,
                    }}
                  >
                    <strong>{S_SHORT[v]}</strong>
                    <div style={{ fontSize: 12, color: "#666" }}>
                      {S_LABELS[v]?.split(" - ")[1]}
                    </div>
                  </Radio.Button>
                ))}
              </Radio.Group>
            </Form.Item>
          </>
        )}

        {/* LEC */}
        {methodType === "LEC" && (
          <>
            <Form.Item label="L — 事故发生的可能性">
              <Select
                value={lecL}
                onChange={(v) => setLecL(v)}
                options={LEC_L_OPTIONS}
              />
            </Form.Item>
            <Form.Item label="E — 暴露于危险环境的频率">
              <Select
                value={lecE}
                onChange={(v) => setLecE(v)}
                options={LEC_E_OPTIONS}
              />
            </Form.Item>
            <Form.Item label="C — 发生事故产生的后果">
              <Select
                value={lecC}
                onChange={(v) => setLecC(v)}
                options={LEC_C_OPTIONS}
              />
            </Form.Item>
          </>
        )}

        {/* DIRECT */}
        {methodType === "DIRECT" && (
          <Form.Item
            name={["method_params", "level"]}
            label="风险等级"
            rules={[{ required: true, message: "请选择风险等级" }]}
            initialValue={1}
          >
            <Select
              placeholder="直接判定风险等级"
              options={DIRECT_LEVELS}
            />
          </Form.Item>
        )}

        {/* ─── Section 3: Rating Preview ───────────────────────── */}
        {(methodType === "LS" || methodType === "COAL_LS" || methodType === "LEC") && (
          <>
            <Divider orientation="left" plain style={{ fontSize: 13 }}>等级预览</Divider>

            {riskResult && (
              <div style={{ marginBottom: 16 }}>
                <Space size={12}>
                  <span style={{ fontSize: 16, fontWeight: 600 }}>
                    {methodType === "LEC" ? `D = ${lecL} × ${lecE} × ${lecC} = ${lecL * lecE * lecC}` : `R = ${lValue} × ${sValue} = ${lValue * sValue}`}
                  </span>
                  <Tag color={RISK_LEVEL_COLORS[riskResult.riskLevel] ?? "#999"}>
                    {riskResult.riskLevel}
                  </Tag>
                  <span style={{ color: "#999", fontSize: 12 }}>
                    {riskResult.action}
                  </span>
                </Space>
              </div>
            )}

            {(methodType === "LS" || methodType === "COAL_LS") && (
              <div>
                {/* column headers */}
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "40px repeat(5, 1fr)",
                    gap: 2,
                    marginBottom: 2,
                  }}
                >
                  <div />
                  {[1, 2, 3, 4, 5].map((l) => (
                    <div
                      key={l}
                      style={{
                        textAlign: "center",
                        fontSize: 11,
                        color: "#999",
                      }}
                    >
                      L{l}
                    </div>
                  ))}
                </div>

                {matrixData.map((row, ri) => {
                  const s = row[0].s;
                  return (
                    <div
                      key={ri}
                      style={{
                        display: "grid",
                        gridTemplateColumns: "40px repeat(5, 1fr)",
                        gap: 2,
                        marginBottom: 2,
                      }}
                    >
                      <div
                        style={{
                          textAlign: "center",
                          fontSize: 11,
                          color: "#999",
                          lineHeight: "36px",
                        }}
                      >
                        S{s}
                      </div>
                      {row.map((cell, ci) => {
                        const isActive = cell.l === lValue && cell.s === sValue;
                        return (
                          <div
                            key={ci}
                            style={{
                              height: 36,
                              display: "flex",
                              alignItems: "center",
                              justifyContent: "center",
                              fontSize: 12,
                              fontWeight: isActive ? 700 : 400,
                              color: cellColor(cell.cls),
                              background: `${cellColor(cell.cls)}18`,
                              borderRadius: 4,
                              border: isActive ? `2px solid ${cellColor(cell.cls)}` : "1px solid transparent",
                              transition: "all 0.2s",
                            }}
                          >
                            {cell.r}
                          </div>
                        );
                      })}
                    </div>
                  );
                })}

                <div style={{ marginTop: 8, display: "flex", gap: 12, flexWrap: "wrap" }}>
                  {(["重大", "较大", "一般", "低"] as const).map((level) => (
                    <span key={level} style={{ fontSize: 12 }}>
                      <span
                        style={{
                          display: "inline-block",
                          width: 12,
                          height: 12,
                          borderRadius: 2,
                          background: RISK_LEVEL_COLORS[level],
                          verticalAlign: "middle",
                          marginRight: 4,
                        }}
                      />
                      {level}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </>
        )}

        {methodType === "DIRECT" && directLevel?.level && (
          <>
            <Divider orientation="left" plain style={{ fontSize: 13 }}>判定结果</Divider>
            <Tag color={RISK_LEVEL_COLORS[DIRECT_LEVELS.find((d) => d.value === directLevel.level)?.label ?? "低"] ?? "#999"}>
              {DIRECT_LEVELS.find((d) => d.value === directLevel.level)?.label ?? "未选择"}
            </Tag>
          </>
        )}

        <Form.Item name="method_type" hidden>
          <Input />
        </Form.Item>
      </Form>
    </Drawer>
  );
}
