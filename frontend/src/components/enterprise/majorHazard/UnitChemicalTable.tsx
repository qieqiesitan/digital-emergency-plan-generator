import { useMemo, useState } from "react";
import { AutoComplete, Button, InputNumber, Select, Space, Table, Tooltip, Typography } from "antd";
import type { TableColumnsType } from "antd";
import { DeleteOutlined, PlusOutlined, QuestionCircleOutlined } from "@ant-design/icons";
import { useQuery } from "@tanstack/react-query";
import {
  listCriticalQuantities,
  listLedgerChemicals,
  lookupChemical,
  suggestDesignMaxFromLedger,
} from "@/services/majorHazardService";
import type {
  DesignMaxSuggestion,
  HazardSymbolOption,
  MajorHazardUnitChemicalPayload,
} from "@/types/majorHazard";
import { formatQty, toNumber } from "@/utils/majorHazardFormat";

const { Text } = Typography;

/**
 * 设计最大量的口径提示。**常驻在输入框下方**，不放进帮助文档。
 *
 * 因为用户从台账抄数字是个下意识的动作，提示必须出现在他动手的那一刻。
 * 台账登记的是"日常最大储存量"，而 GB 18218 4.2.2 要求按**设计最大量**
 * （设备设计容积/额定充装量）计算——两者常不相等，用错会算小导致漏判。
 */
const DESIGN_MAX_HINT =
  "设计最大量口径（GB 18218 4.2.2），通常 ≥ 台账最大储存量；请勿直接照抄台账数字";

interface Row extends MajorHazardUnitChemicalPayload {
  key: string;
}

interface Props {
  /** 企业 id，用于拉取危化品台账候选。 */
  enterpriseId: string;
  value: MajorHazardUnitChemicalPayload[];
  /** 保存回调。由本组件自己持有行数据，故保存按钮也放在这里——避免父组件用 effect 同步状态。 */
  onSave: (rows: MajorHazardUnitChemicalPayload[]) => Promise<void> | void;
  saving?: boolean;
}

let seq = 0;
const nextKey = () => `row-${Date.now()}-${seq++}`;

/** 把后端返回的数值型字段统一成"字符串或空"，避免 InputNumber 与字符串混用。 */
const asNumString = (v: number | null | undefined): string => (v === null || v === undefined ? "" : String(v));

export default function UnitChemicalTable({ enterpriseId, value, onSave, saving }: Props) {
  const [rows, setRows] = useState<Row[]>(() =>
    value.map((r) => ({ ...r, key: nextKey() })),
  );
  /** 每行的危险性类别选项（仅在 β 需人工选择时非空）。 */
  const [symbolOptions, setSymbolOptions] = useState<Record<string, HazardSymbolOption[]>>({});
  const [querying, setQuerying] = useState<Record<string, boolean>>({});
  /**
   * 品种名的候选列表。antd v5 的 AutoComplete 是受控组件——
   * `onSearch` 的返回值会被忽略，必须把结果写进 options 才能显示下拉。
   */
  const [nameOptions, setNameOptions] = useState<Record<string, { value: string }[]>>({});
  /**
   * 每行的台账设计最大量建议。仅当用户主动从台账选入条目后才出现，
   * 且**不自动写进输入框**——设计最大量与台账存量是两个口径，
   * 必须由人看过提示后点「采用」才落到 q_design_max 上。
   */
  const [suggestions, setSuggestions] = useState<Record<string, DesignMaxSuggestion>>({});

  const { data: ledger = [] } = useQuery({
    queryKey: ["ledger-chemicals", enterpriseId],
    queryFn: () => listLedgerChemicals(enterpriseId),
    enabled: !!enterpriseId,
  });

  const push = (next: Row[]) => {
    setRows(next);
  };

  /**
   * 显式构造提交载荷（丢掉表格内部用的 key）。
   *
   * 不用解构 + rest 是因为 eslint 会把 `{ key: _k, ...rest }` 里的 `_k`
   * 判为未使用变量；显式列字段同时也更清楚提交了哪些内容。
   */
  const payload = (next: Row[]): MajorHazardUnitChemicalPayload[] =>
    next.map((r) => ({
      chemical_id: r.chemical_id ?? null,
      chemical_name: r.chemical_name,
      physical_state: r.physical_state ?? null,
      storage_location: r.storage_location ?? null,
      q_design_max: r.q_design_max,
      q_actual: r.q_actual ?? null,
      critical_quantity_t: r.critical_quantity_t,
      beta: r.beta,
      beta_source: r.beta_source,
    }));

  const patch = (key: string, patchObj: Partial<Row>) =>
    push(rows.map((r) => (r.key === key ? { ...r, ...patchObj } : r)));

  const addRow = () =>
    push([
      ...rows,
      {
        key: nextKey(),
        chemical_name: "",
        q_design_max: "",
        critical_quantity_t: "",
        beta: "",
        beta_source: "manual",
      } as Row,
    ]);

  const removeRow = (key: string) => push(rows.filter((r) => r.key !== key));

  /** 选中台账条目：只写引用（chemical_id），顺带取回设计最大量建议供人工采纳。 */
  const handleLedgerSelect = async (key: string, chemicalId?: string) => {
    const entry = chemicalId ? ledger.find((c) => c.id === chemicalId) : undefined;
    const row = rows.find((r) => r.key === key);
    const nextPatch: Partial<Row> = { chemical_id: chemicalId ?? null };
    // 品种名还空着时用台账名称带出，省一次输入；已有名称不覆盖（可能是标准名）
    if (entry && row && !row.chemical_name.trim()) nextPatch.chemical_name = entry.name;
    patch(key, nextPatch);

    if (!chemicalId) {
      setSuggestions((prev) => {
        const next = { ...prev };
        delete next[key];
        return next;
      });
      return;
    }
    try {
      const suggestion = await suggestDesignMaxFromLedger(chemicalId, enterpriseId);
      setSuggestions((prev) => ({ ...prev, [key]: suggestion }));
    } catch {
      // 全局拦截器已提示
    }
  };

  const applySuggestion = (key: string, suggestedQ: number) =>
    patch(key, { q_design_max: asNumString(suggestedQ) });

  /** 选中/输入品种名后查标准值，自动带出 Q 与 β。 */
  const resolveStandard = async (key: string, name: string, hazardSymbol?: string) => {
    if (!name.trim()) return;
    setQuerying((s) => ({ ...s, [key]: true }));
    try {
      const def = await lookupChemical(name, hazardSymbol);
      const next: Partial<Row> = {
        critical_quantity_t: asNumString(def.critical_quantity_t),
        beta: asNumString(def.beta),
        beta_source: def.beta_source ?? "manual",
      };
      patch(key, next);
      setSymbolOptions((s) => ({
        ...s,
        [key]: def.needs_hazard_symbol ? def.hazard_symbol_options : [],
      }));
    } catch {
      // 全局拦截器已提示
    } finally {
      setQuerying((s) => ({ ...s, [key]: false }));
    }
  };

  /** Σq/Q 合计。仅作提示，正式结论以后端计算为准。 */
  const sumRatio = useMemo(() => {
    let total = 0;
    let complete = true;
    for (const r of rows) {
      const q = toNumber(r.q_design_max);
      const Q = toNumber(r.critical_quantity_t);
      if (q === null || Q === null || Q <= 0) {
        complete = false;
        continue;
      }
      total += q / Q;
    }
    return { total, complete };
  }, [rows]);

  const columns: TableColumnsType<Row> = [
    {
      title: "危险化学品",
      width: 220,
      render: (_, r) => (
        <AutoComplete
          value={r.chemical_name}
          placeholder="输入名称，如 氯"
          style={{ width: "100%" }}
          onChange={(v) => patch(r.key, { chemical_name: v })}
          onSelect={(v: string) => resolveStandard(r.key, v)}
          options={nameOptions[r.key] ?? []}
          onSearch={async (kw) => {
            if (kw.trim().length < 2) {
              setNameOptions((s) => ({ ...s, [r.key]: [] }));
              return;
            }
            try {
              const list = await listCriticalQuantities(kw);
              setNameOptions((s) => ({
                ...s,
                [r.key]: list.map((c) => ({ value: c.chemical_name })),
              }));
            } catch {
              setNameOptions((s) => ({ ...s, [r.key]: [] }));
            }
          }}
        />
      ),
    },
    {
      title: "关联台账",
      width: 200,
      render: (_, r) => (
        <Select
          showSearch
          allowClear
          optionFilterProp="label"
          placeholder="选择台账条目"
          style={{ width: "100%" }}
          value={r.chemical_id ?? undefined}
          onChange={(v) => handleLedgerSelect(r.key, v)}
          notFoundContent="本企业暂无危化品台账"
          options={ledger.map((c) => ({ value: c.id, label: c.name }))}
        />
      ),
    },
    {
      title: (
        <Space size={4}>
          设计最大量(t)
          <Tooltip title={DESIGN_MAX_HINT}>
            <QuestionCircleOutlined style={{ color: "#b45309" }} />
          </Tooltip>
        </Space>
      ),
      width: 200,
      render: (_, r) => {
        const suggested = suggestions[r.key]?.suggested_q ?? null;
        return (
          <div>
            <InputNumber
              min={0}
              step={0.1}
              style={{ width: "100%" }}
              value={r.q_design_max === "" ? null : Number(r.q_design_max)}
              onChange={(v) => patch(r.key, { q_design_max: asNumString(v ?? undefined) })}
            />
            <div style={{ fontSize: 11, color: "#b45309", lineHeight: 1.4, marginTop: 2 }}>
              {DESIGN_MAX_HINT}
            </div>
            {suggestions[r.key] && suggested !== null && (
              <div style={{ fontSize: 11, color: "#1677ff", marginTop: 2 }}>
                台账建议 {formatQty(suggested)} t
                <Button
                  type="link"
                  size="small"
                  style={{ padding: "0 4px", height: "auto" }}
                  onClick={() => applySuggestion(r.key, suggested)}
                >
                  采用
                </Button>
              </div>
            )}
            {suggestions[r.key] && suggested === null && (
              <div style={{ fontSize: 11, color: "#8c8c8c", marginTop: 2 }}>
                台账无可解析存量，请手工填写
              </div>
            )}
          </div>
        );
      },
    },
    {
      title: "临界量 Q(t)",
      width: 140,
      render: (_, r) => (
        <InputNumber
          min={0}
          step={0.1}
          style={{ width: "100%" }}
          value={toNumber(r.critical_quantity_t)}
          onChange={(v) => patch(r.key, { critical_quantity_t: asNumString(v ?? undefined) })}
        />
      ),
    },
    {
      title: "β",
      width: 200,
      render: (_, r) => {
        const opts = symbolOptions[r.key] ?? [];
        if (opts.length > 0) {
          return (
            <Select
              placeholder="请选择危险性类别"
              style={{ width: "100%" }}
              loading={querying[r.key]}
              status="warning"
              options={opts.map((o) => ({
                value: o.symbol,
                label: `${o.category ?? o.symbol}（β=${formatQty(o.beta ?? null, 3)}）`,
              }))}
              onChange={(symbol) => resolveStandard(r.key, r.chemical_name, symbol)}
            />
          );
        }
        return (
          <InputNumber
            min={0}
            step={0.1}
            style={{ width: "100%" }}
            value={toNumber(r.beta)}
            onChange={(v) =>
              patch(r.key, { beta: asNumString(v ?? undefined), beta_source: "manual" })
            }
          />
        );
      },
    },
    {
      title: "q÷Q",
      width: 90,
      render: (_, r) => {
        const q = toNumber(r.q_design_max);
        const Q = toNumber(r.critical_quantity_t);
        if (q === null || Q === null || Q <= 0) return <Text type="secondary">—</Text>;
        return <Text>{formatQty(q / Q)}</Text>;
      },
    },
    {
      title: "",
      width: 50,
      render: (_, r) => (
        <Button type="text" danger icon={<DeleteOutlined />} onClick={() => removeRow(r.key)} />
      ),
    },
  ];

  return (
    <div>
      <Table<Row>
        rowKey="key"
        size="small"
        dataSource={rows}
        columns={columns}
        pagination={false}
        scroll={{ x: 1100 }}
      />
      <Space style={{ marginTop: 8 }}>
        <Button type="dashed" icon={<PlusOutlined />} onClick={addRow}>
          添加品种
        </Button>
        <Button type="primary" loading={saving} onClick={() => onSave(payload(rows))}>
          保存品种清单
        </Button>
      </Space>
      <div style={{ marginTop: 8 }}>
        <Text type={sumRatio.total >= 1 ? "danger" : "secondary"}>
          Σq/Q = {formatQty(sumRatio.total)}
          {!sumRatio.complete && "（有未填完的行）"}
          {sumRatio.complete && sumRatio.total >= 1 && " ≥ 1，达到辨识指标"}
        </Text>
        <div style={{ fontSize: 12, color: "#8c8c8c" }}>
          此处仅作即时提示，正式结论以「计算与分级」页的计算结果为准。
        </div>
      </div>
    </div>
  );
}
