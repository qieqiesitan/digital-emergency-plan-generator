/**
 * antd Table 的 rowKey：给没有稳定主键的行补一个本地 `_key`。
 *
 * 用于「本地编辑中的列表」（周边单位/敏感目标/应急小组成员等），
 * 这些行在保存前没有 id，直接用 index 会导致增删行时选中态错位。
 */
export function ensureRowKey<T extends object>(row: T): string {
  const record = row as T & { _key?: string };
  if (!record._key) {
    record._key = crypto.randomUUID?.() ?? `k-${Math.random()}`;
  }
  return record._key;
}
