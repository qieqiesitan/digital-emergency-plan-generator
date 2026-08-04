import { useState, useEffect, useCallback, Fragment } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  Row, Col, Card, Input, Select, Slider, Table, Collapse, Button,
  Space, Typography, Tag, Spin, message, Popconfirm, ColorPicker,
} from "antd";
import {
  ArrowLeftOutlined, PlusOutlined, DeleteOutlined, SaveOutlined,
} from "@ant-design/icons";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getMethod, updateMethod, createMethod,
} from "@/services/riskManagementService";
import type { RiskAssessmentMethod, MethodConfig } from "@/types/riskManagement";
import {
  computeRiskLS, renderMatrixData, RISK_LEVEL_COLORS,
  computeRiskLEC,
} from "@/utils/riskMethodEngine";

const { Title, Text } = Typography;
const { Panel } = Collapse;

interface ParamLevel {
  value: number;
  label: string;
  desc: string;
}

interface ParamDef {
  key: string;
  label: string;
  type: string;
  range: number[];
  levels: ParamLevel[];
}

interface ThresholdDef {
  min: number;
  max: number;
  level: string;
  color: string;
  action: string;
  deadline: string;
}

const METHOD_TYPE_OPTIONS = [
  { value: "LS", label: "LS 风险评估法" },
  { value: "LEC", label: "LEC 评价法" },
  { value: "COAL_LS", label: "COAL_LS 法" },
  { value: "DIRECT", label: "直接判定" },
];

function thresholdsOverlap(items: ThresholdDef[]): number[] {
  const overlaps: number[] = [];
  for (let i = 0; i < items.length; i++) {
    for (let j = i + 1; j < items.length; j++) {
      const a = items[i], b = items[j];
      if (a.max >= b.min && b.max >= a.min) {
        if (!overlaps.includes(i)) overlaps.push(i);
        if (!overlaps.includes(j)) overlaps.push(j);
      }
    }
  }
  return overlaps;
}

export default function RiskMethodEditorPage() {
  const { id: enterpriseId, methodId } = useParams<{ id: string; methodId: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const isCreate = !methodId || methodId === "new";

  // Basic info state
  const [name, setName] = useState("");
  const [methodType, setMethodType] = useState<string>("LS");
  const [formula, setFormula] = useState("");
  const [description, setDescription] = useState("");

  // Params state
  const [params, setParams] = useState<ParamDef[]>([]);

  // Thresholds state
  const [thresholds, setThresholds] = useState<ThresholdDef[]>([]);

  // Evaluation sliders
  const [lValue, setLValue] = useState(3);
  const [sValue, setSValue] = useState(3);
  const [lecL, setLecL] = useState<number>(1);
  const [lecE, setLecE] = useState<number>(3);
  const [lecC, setLecC] = useState<number>(7);

  // Load existing method
  const { data: method, isLoading } = useQuery({
    queryKey: ["risk-method", enterpriseId, methodId],
    queryFn: () => getMethod(enterpriseId!, methodId!),
    enabled: !isCreate && !!enterpriseId && !!methodId,
  });

  useEffect(() => {
    if (method) {
      setName(method.name);
      setMethodType(method.method_type);
      setFormula(method.config?.formula || "");
      setDescription(method.description || "");
      setParams(method.config?.parameters?.map(p => ({
        key: p.key, label: p.label, type: p.type, range: [...p.range],
        levels: p.levels.map(l => ({ value: l.value, label: l.label, desc: l.desc })),
      })) || []);
      setThresholds(method.config?.risk_thresholds?.map(t => ({
        min: t.min, max: t.max, level: t.level, color: t.color, action: t.action, deadline: t.deadline,
      })) || []);
    }
  }, [method]);

  const buildConfig = useCallback((): MethodConfig => ({
    version: "1.0",
    formula,
    display_name: methodType,
    parameters: params,
    risk_thresholds: thresholds,
  }), [formula, methodType, params, thresholds]);

  const saveMut = useMutation({
    mutationFn: async () => {
      const config = buildConfig();
      if (isCreate) {
        return createMethod(enterpriseId!, { method_type: methodType, name, config });
      }
      return updateMethod(enterpriseId!, methodId!, { name, config });
    },
    onSuccess: (data: RiskAssessmentMethod) => {
      message.success(isCreate ? "创建成功" : "保存成功");
      queryClient.invalidateQueries({ queryKey: ["risk-methods", enterpriseId] });
      if (isCreate) {
        navigate(`/enterprises/${enterpriseId}/risk-methods/${data.id}`, { replace: true });
      }
    },
    onError: () => message.error("保存失败"),
  });

  // Params CRUD helpers
  const addParam = () => {
    setParams(prev => [...prev, {
      key: `p${prev.length + 1}`, label: "", type: "integer", range: [1, 5],
      levels: [],
    }]);
  };

  const updateParam = (idx: number, field: keyof ParamDef, value: unknown) => {
    setParams(prev => prev.map((p, i) => i === idx ? { ...p, [field]: value } : p));
  };

  const deleteParam = (idx: number) => {
    setParams(prev => prev.filter((_, i) => i !== idx));
  };

  const addLevel = (paramIdx: number) => {
    setParams(prev => prev.map((p, i) => {
      if (i !== paramIdx) return p;
      return { ...p, levels: [...p.levels, { value: p.levels.length + 1, label: "", desc: "" }] };
    }));
  };

  const updateLevel = (paramIdx: number, levelIdx: number, field: keyof ParamLevel, value: unknown) => {
    setParams(prev => prev.map((p, i) => {
      if (i !== paramIdx) return p;
      const newLevels = p.levels.map((l, j) => j === levelIdx ? { ...l, [field]: value } : l);
      return { ...p, levels: newLevels };
    }));
  };

  const deleteLevel = (paramIdx: number, levelIdx: number) => {
    setParams(prev => prev.map((p, i) => {
      if (i !== paramIdx) return p;
      return { ...p, levels: p.levels.filter((_, j) => j !== levelIdx) };
    }));
  };

  // Thresholds CRUD helpers
  const addThreshold = () => {
    setThresholds(prev => [...prev, {
      min: prev.length > 0 ? prev[prev.length - 1].max + 1 : 1,
      max: prev.length > 0 ? prev[prev.length - 1].max + 10 : 10,
      level: "", color: "#1890ff", action: "", deadline: "",
    }]);
  };

  const updateThreshold = (idx: number, field: keyof ThresholdDef, value: unknown) => {
    setThresholds(prev => prev.map((t, i) => i === idx ? { ...t, [field]: value } : t));
  };

  const deleteThreshold = (idx: number) => {
    setThresholds(prev => prev.filter((_, i) => i !== idx));
  };

  // Risk evaluation
  const riskResult = methodType === "LEC"
    ? computeRiskLEC(lecL, lecE, lecC)
    : computeRiskLS(lValue, sValue);
  const matrixData = renderMatrixData(methodType === "LEC" ? "LEC" : "LS");
  const overlapRows = thresholdsOverlap(thresholds);

  const paramColumns = (paramIdx: number) => [
    { title: "值", dataIndex: "value", width: 60, render: (_: unknown, record: ParamLevel, ri: number) => (
      <EditableCell value={record.value} onChange={v => updateLevel(paramIdx, ri, "value", Number(v))} />
    )},
    { title: "标签", dataIndex: "label", render: (_: unknown, record: ParamLevel, ri: number) => (
      <EditableCell value={record.label} onChange={v => updateLevel(paramIdx, ri, "label", v)} />
    )},
    { title: "描述", dataIndex: "desc", render: (_: unknown, record: ParamLevel, ri: number) => (
      <EditableCell value={record.desc} onChange={v => updateLevel(paramIdx, ri, "desc", v)} />
    )},
    {
      title: "操作", width: 60,
      render: (_: unknown, __: ParamLevel, ri: number) => (
        <Button type="link" danger size="small" icon={<DeleteOutlined />} onClick={() => deleteLevel(paramIdx, ri)} />
      ),
    },
  ];

  if (isLoading) return <Spin size="large" style={{ display: "block", margin: "80px auto" }} />;

  return (
    <div style={{ padding: 24, maxWidth: 1400, margin: "0 auto" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 }}>
        <Space>
          <Button icon={<ArrowLeftOutlined />} onClick={() => navigate(`/enterprises/${enterpriseId}/risk-methods`)}>返回</Button>
          <Title level={4} style={{ margin: 0 }}>{isCreate ? "新建风险评估方法" : "编辑风险评估方法"}</Title>
        </Space>
        <Button type="primary" icon={<SaveOutlined />} loading={saveMut.isPending} onClick={() => saveMut.mutate()}>
          保存
        </Button>
      </div>

      <Row gutter={24}>
        <Col xs={24} lg={17}>
          {/* Basic Info */}
          <Card title="基本信息" size="small" style={{ marginBottom: 16 }}>
            <Row gutter={[16, 12]}>
              <Col span={12}>
                <Text strong style={{ display: "block", marginBottom: 4 }}>方法名称</Text>
                <Input value={name} onChange={e => setName(e.target.value)} placeholder="输入方法名称" />
              </Col>
              <Col span={12}>
                <Text strong style={{ display: "block", marginBottom: 4 }}>方法类型</Text>
                <Select
                  value={methodType}
                  onChange={setMethodType}
                  disabled={!isCreate}
                  options={METHOD_TYPE_OPTIONS}
                  style={{ width: "100%" }}
                />
              </Col>
              <Col span={12}>
                <Text strong style={{ display: "block", marginBottom: 4 }}>公式</Text>
                <Input
                  value={formula}
                  onChange={e => setFormula(e.target.value)}
                  placeholder="如 R = L x S"
                  style={{ fontFamily: "monospace", color: "#1677ff" }}
                />
              </Col>
              <Col span={12}>
                <Text strong style={{ display: "block", marginBottom: 4 }}>描述</Text>
                <Input value={description} onChange={e => setDescription(e.target.value)} placeholder="方法描述" />
              </Col>
            </Row>
          </Card>

          {/* Parameters */}
          <Card
            title="评估参数"
            size="small"
            style={{ marginBottom: 16 }}
            extra={<Button size="small" icon={<PlusOutlined />} onClick={addParam}>添加参数</Button>}
          >
            {params.length === 0 && <Text type="secondary">暂无参数，点击添加</Text>}
            <Collapse accordion>
              {params.map((param, pi) => (
                <Panel
                  key={param.key || `p-${pi}`}
                  header={
                    <Space>
                      <Text strong>{param.label || `参数 ${pi + 1}`}</Text>
                      <Text type="secondary" style={{ fontSize: 12 }}>{param.key} [{param.range?.[0]}-{param.range?.[1]}]</Text>
                    </Space>
                  }
                  extra={
                    <Popconfirm title="删除此参数？" onConfirm={() => deleteParam(pi)}>
                      <Button size="small" danger icon={<DeleteOutlined />} onClick={e => e.stopPropagation()} />
                    </Popconfirm>
                  }
                >
                  <Space orientation="vertical" style={{ width: "100%" }} size="small">
                    <Row gutter={[12, 0]}>
                      <Col span={8}>
                        <Text style={{ fontSize: 12 }}>Key</Text>
                        <Input size="small" value={param.key} onChange={e => updateParam(pi, "key", e.target.value)} />
                      </Col>
                      <Col span={8}>
                        <Text style={{ fontSize: 12 }}>标签</Text>
                        <Input size="small" value={param.label} onChange={e => updateParam(pi, "label", e.target.value)} />
                      </Col>
                      <Col span={4}>
                        <Text style={{ fontSize: 12 }}>范围min</Text>
                        <Input size="small" type="number" value={param.range?.[0]} onChange={e => updateParam(pi, "range", [Number(e.target.value), param.range?.[1] || 5])} />
                      </Col>
                      <Col span={4}>
                        <Text style={{ fontSize: 12 }}>范围max</Text>
                        <Input size="small" type="number" value={param.range?.[1]} onChange={e => updateParam(pi, "range", [param.range?.[0] || 1, Number(e.target.value)])} />
                      </Col>
                    </Row>
                    <div style={{ marginTop: 8 }}>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
                        <Text strong style={{ fontSize: 13 }}>等级定义</Text>
                        <Button size="small" icon={<PlusOutlined />} onClick={() => addLevel(pi)}>添加等级</Button>
                      </div>
                      <Table
                        dataSource={param.levels}
                        rowKey={(_, ri) => `${param.key}-lvl-${ri}`}
                        columns={paramColumns(pi)}
                        size="small"
                        pagination={false}
                        locale={{ emptyText: "暂无等级定义" }}
                      />
                    </div>
                  </Space>
                </Panel>
              ))}
            </Collapse>
          </Card>

          {/* Thresholds */}
          <Card
            title="风险等级区间"
            size="small"
            style={{ marginBottom: 16 }}
            extra={<Button size="small" icon={<PlusOutlined />} onClick={addThreshold}>添加等级区间</Button>}
          >
            <Table
              dataSource={thresholds}
              rowKey={(_, ri) => `th-${ri}`}
              size="small"
              pagination={false}
              rowClassName={(_, ri) => overlapRows.includes(ri) ? "ant-table-row-overlap" : ""}
              columns={[
                { title: "等级", dataIndex: "level", width: 80, render: (_: unknown, record: ThresholdDef, ri: number) => (
                  <Input size="small" value={record.level} onChange={e => updateThreshold(ri, "level", e.target.value)} placeholder="重大" />
                )},
                { title: "最小", dataIndex: "min", width: 70, render: (_: unknown, record: ThresholdDef, ri: number) => (
                  <Input size="small" type="number" value={record.min} onChange={e => updateThreshold(ri, "min", Number(e.target.value))} />
                )},
                { title: "最大", dataIndex: "max", width: 70, render: (_: unknown, record: ThresholdDef, ri: number) => (
                  <Input size="small" type="number" value={record.max} onChange={e => updateThreshold(ri, "max", Number(e.target.value))} />
                )},
                { title: "颜色", dataIndex: "color", width: 70, render: (_: unknown, record: ThresholdDef, ri: number) => (
                  <ColorPicker value={record.color} onChange={(_, hex) => updateThreshold(ri, "color", hex)} size="small" />
                )},
                { title: "处置措施", dataIndex: "action", render: (_: unknown, record: ThresholdDef, ri: number) => (
                  <Input size="small" value={record.action} onChange={e => updateThreshold(ri, "action", e.target.value)} placeholder="立即整改" />
                )},
                { title: "期限", dataIndex: "deadline", width: 90, render: (_: unknown, record: ThresholdDef, ri: number) => (
                  <Input size="small" value={record.deadline} onChange={e => updateThreshold(ri, "deadline", e.target.value)} placeholder="立即" />
                )},
                {
                  title: "操作", width: 50,
                  render: (_: unknown, __: ThresholdDef, ri: number) => (
                    <Button type="link" danger size="small" icon={<DeleteOutlined />} onClick={() => deleteThreshold(ri)} />
                  ),
                },
              ]}
              locale={{ emptyText: "暂无等级区间" }}
            />
            {overlapRows.length > 0 && (
              <Text type="danger" style={{ fontSize: 12, marginTop: 8, display: "block" }}>
                区间重叠：第 {overlapRows.map(i => i + 1).join("、")} 行存在交叉区间
              </Text>
            )}
          </Card>
        </Col>

        {/* Right Evaluation Panel */}
        <Col xs={24} lg={7}>
          <div style={{ position: "sticky", top: 24 }}>
            <Card title="实时评估" size="small" style={{ marginBottom: 16 }}>
              {methodType === "LEC" ? (
                <>
                  <div style={{ marginBottom: 12 }}>
                    <Text strong style={{ fontSize: 12 }}>L - 事故可能性</Text>
                    <Select value={lecL} onChange={setLecL} style={{ width: "100%", marginTop: 4 }}
                      options={[{ value: 0.1, label: "0.1-实际不可能" },{ value: 0.5, label: "0.5-极不可能" },{ value: 1, label: "1-可能性小" },{ value: 2, label: "2-可能但不经常" },{ value: 3, label: "3-可能" },{ value: 6, label: "6-相当可能" },{ value: 10, label: "10-完全可以预料" }]} />
                  </div>
                  <div style={{ marginBottom: 12 }}>
                    <Text strong style={{ fontSize: 12 }}>E - 暴露频率</Text>
                    <Select value={lecE} onChange={setLecE} style={{ width: "100%", marginTop: 4 }}
                      options={[{ value: 0.5, label: "0.5-每年一次" },{ value: 1, label: "1-每月一次" },{ value: 2, label: "2-每周一次" },{ value: 3, label: "3-每日一次" },{ value: 6, label: "6-每班数次" },{ value: 10, label: "10-连续暴露" }]} />
                  </div>
                  <div style={{ marginBottom: 12 }}>
                    <Text strong style={{ fontSize: 12 }}>C - 事故后果</Text>
                    <Select value={lecC} onChange={setLecC} style={{ width: "100%", marginTop: 4 }}
                      options={[{ value: 1, label: "1-轻微" },{ value: 3, label: "3-较小" },{ value: 7, label: "7-严重" },{ value: 15, label: "15-非常严重" },{ value: 40, label: "40-灾难" },{ value: 100, label: "100-大灾难" }]} />
                  </div>
                  <div style={{ textAlign: "center", padding: "12px 0", background: "#fafafa", borderRadius: 8, marginBottom: 16 }}>
                    <div style={{ fontSize: 13 }}>D = {lecL} × {lecE} × {lecC} = <Text strong style={{ fontSize: 18 }}>{Math.round(lecL * lecE * lecC)}</Text></div>
                    <Tag color={RISK_LEVEL_COLORS[riskResult.riskLevel] || "#1890ff"} style={{ marginTop: 8, fontSize: 16, padding: "4px 16px" }}>{riskResult.riskLevel}</Tag>
                  </div>
                </>
              ) : (
                <>
                  <div style={{ marginBottom: 16 }}>
                    <Text strong>L - 事故可能性</Text>
                    <Slider min={1} max={5} value={lValue} onChange={setLValue} marks={{ 1: "1", 2: "2", 3: "3", 4: "4", 5: "5" }} />
                  </div>
                  <div style={{ marginBottom: 16 }}>
                    <Text strong>S - 后果严重程度</Text>
                    <Slider min={1} max={5} value={sValue} onChange={setSValue} marks={{ 1: "1", 2: "2", 3: "3", 4: "4", 5: "5" }} />
                  </div>
                  <div style={{ textAlign: "center", padding: "12px 0", background: "#fafafa", borderRadius: 8, marginBottom: 16 }}>
                    <div style={{ fontSize: 14 }}>R = {lValue} × {sValue} = <Text strong style={{ fontSize: 18 }}>{riskResult.riskScore.replace("R=", "")}</Text></div>
                    <Tag color={RISK_LEVEL_COLORS[riskResult.riskLevel] || "#1890ff"} style={{ marginTop: 8, fontSize: 16, padding: "4px 16px" }}>{riskResult.riskLevel}</Tag>
                  </div>
                </>
              )}
            </Card>

            {methodType !== "LEC" && (
              <Card title="风险矩阵" size="small">
                <div style={{ display: "grid", gridTemplateColumns: "repeat(6, 1fr)", gap: 2, aspectRatio: "1" }}>
                  <div style={{ fontSize: 10, display: "flex", alignItems: "center", justifyContent: "center", color: "#999" }}>L\S</div>
                  {[1, 2, 3, 4, 5].map(s => (
                    <div key={`eh-${s}`} style={{ fontSize: 10, display: "flex", alignItems: "center", justifyContent: "center", color: "#999" }}>{s}</div>
                  ))}
                  {matrixData.map((row, li) => (
                    <Fragment key={`row-${li}`}>
                      <div key={`elh-${li}`} style={{ fontSize: 10, display: "flex", alignItems: "center", justifyContent: "center", color: "#999" }}>{li + 1}</div>
                      {row.map((cell, si) => {
                        const isActive = (li + 1) === lValue && (si + 1) === sValue;
                        return (
                          <div
                            key={`${li}-${si}`}
                            style={{
                              backgroundColor: cell.color,
                              borderRadius: 2,
                              display: "flex",
                              alignItems: "center",
                              justifyContent: "center",
                              fontSize: 11,
                              color: "#fff",
                              fontWeight: 600,
                              border: isActive ? "3px solid #000" : "1px solid transparent",
                              boxSizing: "border-box",
                            }}
                          >
                            {cell.r}
                          </div>
                        );
                      })}
                    </Fragment>
                  ))}
                </div>
                <div style={{ display: "flex", justifyContent: "space-around", marginTop: 12, flexWrap: "wrap", gap: 4 }}>
                  {Object.entries(RISK_LEVEL_COLORS).map(([level, color]) => (
                    <Space key={level} size={4}>
                      <div style={{ width: 12, height: 12, backgroundColor: color, borderRadius: 2 }} />
                      <Text style={{ fontSize: 11 }}>{level}</Text>
                    </Space>
                  ))}
                </div>
              </Card>
            )}

            {methodType === "LEC" && (
              <Card title="LEC 风险区间" size="small">
                <div style={{ fontSize: 12, color: "#666", marginBottom: 8 }}>D = L × E × C 值所在位置：</div>
                <div style={{ position: "relative", height: 24, background: "linear-gradient(to right, #52c41a, #fadb14, #fa8c16, #ff4d4f)", borderRadius: 6 }}>
                  <div style={{ position: "absolute", top: 0, width: 0, height: 0, borderLeft: "6px solid transparent", borderRight: "6px solid transparent", borderTop: "6px solid #000", left: `${Math.min(100, (Math.round(lecL * lecE * lecC) / 500) * 100)}%`, transform: "translateX(-50%)", zIndex: 2 }} />
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: 10, color: "#999", marginTop: 4 }}>
                  <span>0</span><span>70</span><span>160</span><span>320</span>
                </div>
              </Card>
            )}
          </div>
        </Col>
      </Row>
    </div>
  );
}

/** Inline editable cell: double-click to enter edit mode */
function EditableCell({ value, onChange }: { value: string | number; onChange: (v: string) => void }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(String(value));

  useEffect(() => { setDraft(String(value)); }, [value]);

  const commit = () => { setEditing(false); onChange(draft); };

  if (editing) {
    return (
      <Input
        size="small"
        value={draft}
        onChange={e => setDraft(e.target.value)}
        onBlur={commit}
        onPressEnter={commit}
        autoFocus
      />
    );
  }

  return (
    <div
      onDoubleClick={() => setEditing(true)}
      style={{ cursor: "pointer", minHeight: 22, padding: "2px 4px" }}
    >
      {value !== undefined && value !== null ? String(value) : <span style={{ color: "#bbb" }}>-</span>}
    </div>
  );
}
