import type { OrgNode } from "@/types/enterpriseOrg";

/** 按深度排序（父先于子），保证增量合并时父节点映射可解析。 */
function sortByDepth(nodes: OrgNode[]): OrgNode[] {
  const byId = new Map(nodes.filter(n => n.id).map(n => [n.id, n]));
  const depth = (n: OrgNode): number =>
    n.parent_id && byId.has(n.parent_id) ? depth(byId.get(n.parent_id)!) + 1 : 0;
  return [...nodes].sort((a, b) => depth(a) - depth(b));
}

/**
 * 增量合并组织树节点：保留已有节点，按 (type, name, 父节点) 匹配 incoming，
 * 匹配不到才新增（生成不与现有 id 冲突的新 id）。用于「应用预置应急组织」与「AI 建树」，
 * 避免整树替换丢掉用户已有数据。
 */
export function mergeOrgNodes(existing: OrgNode[], incoming: OrgNode[]): OrgNode[] {
  const result: OrgNode[] = existing.map(n => ({ ...n, members: n.members ?? [] }));
  const idSet = new Set(result.map(n => n.id));
  const nextId = (): string => {
    let i = 1;
    while (idSet.has(`node-${i}`)) i += 1;
    return `node-${i}`;
  };

  // incoming 父节点 id → 合并后实际节点 id
  const mappedParent = new Map<string, string | null>();

  for (const n of sortByDepth(incoming)) {
    const parentId = n.parent_id ? (mappedParent.get(n.parent_id) ?? null) : null;
    // 部门/班组按 (type, name) 全局复用（避免同名组重复建树）；岗位按 (type, name, 父组) 匹配
    const match =
      n.type === "position"
        ? result.find(
            r =>
              r.type === n.type &&
              r.name === n.name &&
              (r.parent_id ?? null) === parentId,
          )
        : result.find(r => r.type === n.type && r.name === n.name);
    if (match) {
      mappedParent.set(n.id, match.id);
      continue;
    }
    const id = nextId();
    idSet.add(id);
    const node: OrgNode = {
      id,
      type: n.type,
      name: n.name,
      parent_id: parentId,
      members: n.members ?? [],
    };
    result.push(node);
    mappedParent.set(n.id, id);
  }

  return result;
}
