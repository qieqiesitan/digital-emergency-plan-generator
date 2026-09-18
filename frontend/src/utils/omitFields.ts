/**
 * 返回去掉指定字段的浅拷贝。
 *
 * 用途：列表/表单在本地编辑时会挂一些仅供前端使用的草稿字段
 * （例如列表行上的 `_key`、`_isNew`，周边环境表单上的 `_ext`），
 * 提交给后端前需要剥离，避免把前端临时字段发出去。
 *
 * 用「拷贝 + delete」而不是「解构 + rest」，是为了不产生
 * “解构出来的变量未使用”的 lint 噪音（等价语义，意图更明确）。
 */
export function omitFields<T extends object, K extends keyof T>(
  item: T,
  keys: readonly K[],
): Omit<T, K> {
  const copy = { ...item } as Record<string, unknown>;
  for (const key of keys) {
    delete copy[key as string];
  }
  return copy as Omit<T, K>;
}
