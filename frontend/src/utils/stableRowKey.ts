/**
 * 给 Table 数据挂稳定 rowKey。
 *
 * 背景：antd v6 起 `rowKey(record, index)` 的 index 参数被标记弃用（"不保证按预期工作"）。
 * 既有代码用它给「业务字段可能重复」的行兜底唯一性；这里把同样的语义前移到数据上：
 * 业务前缀 + 数组下标，在渲染前算好，既保持唯一性又不依赖 antd 传 index。
 */
export function withRowKeys<T extends object>(
  rows: readonly T[],
  base: (row: T) => string,
): Array<T & { __rowKey: string }> {
  return rows.map((row, index) => ({ ...row, __rowKey: `${base(row)}-${index}` }));
}
