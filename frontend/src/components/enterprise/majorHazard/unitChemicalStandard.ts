/**
 * 「查标准表」这一步该把临界量 Q 写成什么。
 *
 * 为什么值得单独成函数：Q 会直接进入 q/Q ≥ 1 的判定，写错等于把重大危险源
 * 判错。而这一步有三种合法但结果相反的情况，混起来必然出错：

 * 1. 标准表里有值（表1 按品种名命中、或按危险性类别从表2 取到）→ 采用标准值
 * 2. 换了另一个品种名、而新名字不在表1 → 旧 Q 已经作废，**必须清空**，
 *    否则上一个品种的临界量会留下来参与计算
 * 3. 首次查一个表1 没有的名字 → **不要动**：用户可能已经手填了 Q
 *
 * 返回 `undefined` 表示"这一格不动"。
 */
export function decideCriticalQuantity(args: {
  /** 后端本次返回的 Q（表1 命中或按符号从表2 取到，取不到为 null）。 */
  returnedQ: number | null;
  /** 本次是否带着危险性类别符号查（即用户刚在类别下拉里选了一下）。 */
  hazardSymbol?: string;
  typedName: string;
  /** 这一行上一次查成功的品种名（没查过则为空）。 */
  previousResolvedName?: string | null;
}): string | undefined {
  const { returnedQ, hazardSymbol, typedName, previousResolvedName } = args;

  if (returnedQ != null) return String(returnedQ);

  // 选类别这一步只负责补值：表2 里没这个符号时就保持原值，交回人工决定
  if (hazardSymbol !== undefined) return undefined;

  const previous = (previousResolvedName ?? "").trim();
  if (previous && previous !== typedName.trim()) return "";

  return undefined;
}
