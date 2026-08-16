import { useCallback, useEffect, useMemo, useState } from "react";
import { PRESET_EMERGENCY_GROUPS } from "@/utils/constants";
import { useNavigate, useParams } from "react-router-dom";
import {
  App as AntApp,
  Alert,
  Button,
  Empty,
  Form,
  Input,
  Modal,
  Popconfirm,
  Select,
  Space,
  Spin,
  Switch,
  Table,
  Tag,
  Tree,
  Upload,
} from "antd";
import type { TableColumnsType } from "antd";
import type { DataNode } from "antd/es/tree";
import {
  ApartmentOutlined,
  DeleteOutlined,
  DownloadOutlined,
  EditOutlined,
  PlusOutlined,
  SaveOutlined,
  SearchOutlined,
  ThunderboltOutlined,
  UploadOutlined,
  UserAddOutlined,
} from "@ant-design/icons";
import { useQuery } from "@tanstack/react-query";
import { PageHeader } from "@/components/common/PageHeader";
import {
  createMember,
  deleteMember,
  downloadMemberTemplate,
  getOrgNodes,
  importMembers,
  listMembers,
  saveOrgNodes,
  searchBindableUsers,
  suggestOrgTree,
  updateMember,
} from "@/services/enterpriseOrgService";
import type {
  BindableUser,
  EnterpriseMember,
  OrgNode,
  OrgNodeType,
  OrgTreeSuggestion,
} from "@/types/enterpriseOrg";

const TYPE_LABEL: Record<OrgNodeType, string> = {
  dept: "部门",
  team: "班组",
  position: "岗位",
};

const ROLE_META: Record<string, { label: string; color: string }> = {
  enterprise_admin: { label: "企业管理员", color: "gold" },
  team_leader: { label: "班组长", color: "blue" },
  member: { label: "员工", color: "default" },
};

const ROLE_OPTIONS = [
  { label: "企业管理员", value: "enterprise_admin" },
  { label: "班组长", value: "team_leader" },
  { label: "员工", value: "member" },
];

/** 生成不与现有节点冲突的短 id（对齐后端 normalize_org_nodes 规则）。 */
function nextNodeId(nodes: OrgNode[]): string {
  const existing = new Set(nodes.map(n => n.id));
  let i = 1;
  while (existing.has(`node-${i}`)) i += 1;
  return `node-${i}`;
}

/** OrgNode[] → antd Tree 数据（孤儿节点挂根，避免整树丢失）。 */
function buildTreeData(nodes: OrgNode[]): DataNode[] {
  const byParent = new Map<string | null, OrgNode[]>();
  for (const n of nodes) {
    const key = n.parent_id ?? null;
    const list = byParent.get(key) ?? [];
    list.push(n);
    byParent.set(key, list);
  }
  const toData = (list: OrgNode[] | undefined): DataNode[] =>
    (list ?? []).map(n => ({
      key: n.id,
      title: n.name,
      children: toData(byParent.get(n.id)),
    }));
  return toData(byParent.get(null));
}

/** 沿 parent_id 拼 部门/班组/岗位 路径（用于成员表格展示）。 */
function buildOrgPath(nodeId: string | null | undefined, nodes: OrgNode[]): string {
  if (!nodeId) return "";
  const byId = new Map(nodes.map(n => [n.id, n]));
  const parts: string[] = [];
  let cur: OrgNode | undefined = byId.get(nodeId);
  const seen = new Set<string>();
  while (cur && !seen.has(cur.id)) {
    seen.add(cur.id);
    parts.push(cur.name);
    cur = cur.parent_id ? byId.get(cur.parent_id) : undefined;
  }
  return parts.reverse().join("/");
}

/** 收集节点及其全部子孙 id（删除子树用）。 */
function collectSubtreeIds(nodes: OrgNode[], rootId: string): Set<string> {
  const ids = new Set<string>([rootId]);
  const childrenOf = new Map<string | null, OrgNode[]>();
  for (const n of nodes) {
    const list = childrenOf.get(n.parent_id ?? null) ?? [];
    list.push(n);
    childrenOf.set(n.parent_id ?? null, list);
  }
  const queue = [rootId];
  while (queue.length) {
    const cur = queue.shift();
    for (const child of childrenOf.get(cur ?? null) ?? []) {
      if (!ids.has(child.id)) {
        ids.add(child.id);
        queue.push(child.id);
      }
    }
  }
  return ids;
}

/** 前端基础校验：name 非空（非字符串按非法处理）、type 合法、parent 存在、无自环/环、id 唯一、成员 name 非空。 */
function validateNodes(nodes: OrgNode[]): string[] {
  const errors: string[] = [];
  const ids = new Set<string>();
  const byId = new Map<string, OrgNode>(nodes.map(n => [n.id, n]));
  for (const n of nodes) {
    if (typeof n.name !== "string" || !n.name.trim()) {
      errors.push(`节点 ${n.id || "(无 id)"} 名称不能为空`);
    }
    if (!["dept", "team", "position"].includes(n.type)) {
      errors.push(`节点 ${n.id} type 非法: ${n.type}`);
    }
    if (ids.has(n.id)) {
      errors.push(`节点 id 重复: ${n.id}`);
    }
    ids.add(n.id);
    if (n.parent_id != null && !byId.has(n.parent_id)) {
      errors.push(`节点 ${n.id} parent 不存在: ${n.parent_id}`);
    } else if (n.parent_id === n.id) {
      errors.push(`节点 ${n.id} 不能以自身为父节点`);
    } else if (n.parent_id != null) {
      // 沿 parent 链检测环：从父节点一路向上，回到自身即循环引用
      const walked = new Set<string>();
      let cur: string | null | undefined = n.parent_id;
      while (cur != null && byId.has(cur) && !walked.has(cur)) {
        if (cur === n.id) {
          errors.push(`节点 ${n.id} 存在循环引用`);
          break;
        }
        walked.add(cur);
        cur = byId.get(cur)?.parent_id ?? null;
      }
    }
    if (!Array.isArray(n.members)) {
      errors.push(`节点 ${n.id} members 必须为数组`);
    } else {
      for (const m of n.members) {
        if (typeof m !== "object" || m === null || typeof m.name !== "string" || !m.name.trim()) {
          errors.push(`节点 ${n.id} 存在非法或无姓名成员`);
        }
      }
    }
  }
  return errors;
}

interface NodeModalState {
  open: boolean;
  mode: "add" | "rename";
  node?: OrgNode;
  type?: OrgNodeType;
  parentId?: string | null;
}

interface MemberModalState {
  open: boolean;
  mode: "create" | "edit";
  member?: EnterpriseMember;
}

/** 企业组织与成员管理页：组织树 + 成员管理 + Excel 导入 + AI 建树。 */
export default function EnterpriseOrgPage() {
  const { id: enterpriseId = "" } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { message, modal } = AntApp.useApp();
  const [form] = Form.useForm();

  const { data: fetchedNodes = [], isLoading: nodesLoading, refetch: refetchNodes } = useQuery({
    queryKey: ["org-nodes", enterpriseId],
    queryFn: () => getOrgNodes(enterpriseId),
    enabled: !!enterpriseId,
  });
  const { data: members = [], isLoading: membersLoading, refetch: refetchMembers } = useQuery({
    queryKey: ["org-members", enterpriseId],
    queryFn: () => listMembers(enterpriseId),
    enabled: !!enterpriseId,
  });

  // 本地编辑副本：null 表示未开始编辑（直接展示后端数据）；编辑后切换为副本，
  // 保存成功再置回 null 由 refetch 刷新，编辑中不被 refetch 覆盖
  const [localNodes, setLocalNodes] = useState<OrgNode[] | null>(null);
  const nodes = localNodes ?? fetchedNodes;
  const dirty = localNodes !== null;

  // 组织架构为空时预置应急预案所需六个应急小组（指挥部/抢险/疏散/医疗/通讯/后勤），
  // 用户可直接在组下挂成员，避免生成预案时应急组织机构缺组
  useEffect(() => {
    if (!nodesLoading && fetchedNodes.length === 0 && localNodes === null) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- 空组织架构首次加载时播种预置应急小组，属一次性初始化；react-hooks v7 新规则对同步 setState 误报（全仓同类基线）
      setLocalNodes(
        Object.entries(PRESET_EMERGENCY_GROUPS).map(([key, name]) => ({
          id: `preset-${key}`,
          type: "team" as const,
          name,
          members: [],
          parent_id: null,
        })),
      );
    }
  }, [fetchedNodes, nodesLoading, localNodes]);

  const [nodeModal, setNodeModal] = useState<NodeModalState>({ open: false, mode: "add" });
  const [memberModal, setMemberModal] = useState<MemberModalState>({ open: false, mode: "create" });
  const [searchEmail, setSearchEmail] = useState("");
  const [searchResults, setSearchResults] = useState<BindableUser[]>([]);
  const [searching, setSearching] = useState(false);
  const [selectedUser, setSelectedUser] = useState<BindableUser | null>(null);
  const [aiModal, setAiModal] = useState<{ open: boolean; suggestion: OrgTreeSuggestion | null; loading: boolean }>({
    open: false,
    suggestion: null,
    loading: false,
  });
  const [importing, setImporting] = useState(false);

  const nodeOptions = useMemo(
    () => nodes.map(n => ({ label: `${TYPE_LABEL[n.type]}：${n.name}`, value: n.id })),
    [nodes],
  );

  const refetchAll = useCallback(() => {
    refetchMembers();
    refetchNodes();
  }, [refetchMembers, refetchNodes]);

  // ── 组织树操作 ──

  const openAddNode = useCallback((type: OrgNodeType, parentId: string | null) => {
    setNodeModal({ open: true, mode: "add", type, parentId });
  }, []);

  const openRenameNode = useCallback((node: OrgNode) => {
    setNodeModal({ open: true, mode: "rename", node });
  }, []);

  const submitNodeModal = useCallback(() => {
    form.validateFields().then(values => {
      const name = String(values.name ?? "").trim();
      if (!name) {
        message.error("名称不能为空");
        return;
      }
      if (nodeModal.mode === "add") {
        const type = nodeModal.type ?? "dept";
        const id = nextNodeId(nodes);
        setLocalNodes([
          ...nodes,
          { id, type, name, parent_id: nodeModal.parentId ?? null, members: [] },
        ]);
      } else {
        const node = nodeModal.node;
        if (node) {
          setLocalNodes(
            nodes.map(n => (n.id === node.id ? { ...n, name } : n)),
          );
        }
      }
      setNodeModal({ open: false, mode: "add" });
      form.resetFields();
    });
  }, [form, message, nodeModal, nodes]);

  const deleteNode = useCallback(
    (node: OrgNode) => {
      const ids = collectSubtreeIds(nodes, node.id);
      setLocalNodes(nodes.filter(n => !ids.has(n.id)));
    },
    [nodes],
  );

  const handleSaveTree = useCallback(async () => {
    let errors: string[];
    try {
      errors = validateNodes(nodes);
    } catch {
      message.error("组织树校验失败：数据格式异常");
      return;
    }
    if (errors.length) {
      message.error(`组织树校验失败：${errors.join("；")}`);
      return;
    }
    try {
      await saveOrgNodes(enterpriseId, nodes);
      setLocalNodes(null);
      message.success("组织树已保存");
      refetchAll();
    } catch (e) {
      message.error(`保存失败：${e instanceof Error ? e.message : "未知错误"}`);
    }
  }, [enterpriseId, message, nodes, refetchAll]);

  // ── AI 建树 ──

  const handleAiSuggest = useCallback(async () => {
    setAiModal({ open: true, suggestion: null, loading: true });
    try {
      const suggestion = await suggestOrgTree(enterpriseId);
      setAiModal({ open: true, suggestion, loading: false });
    } catch (e) {
      setAiModal({ open: false, suggestion: null, loading: false });
      message.error(`AI 建树失败：${e instanceof Error ? e.message : "未知错误"}`);
    }
  }, [enterpriseId, message]);

  const applyAiSuggestion = useCallback(
    (suggestion: OrgTreeSuggestion) => {
      const suggested = (suggestion.nodes ?? []).map((n, i) => ({
        ...n,
        id: n.id || `suggest-${i + 1}`,
        parent_id: n.parent_id ?? null,
        members: n.members ?? [],
      }));
      setLocalNodes(suggested);
      setAiModal({ open: false, suggestion: null, loading: false });
      message.info("已填充 AI 建议树，请核对后点击「保存组织树」生效");
    },
    [message],
  );

  const aiTreeData = useMemo(
    () => (aiModal.suggestion?.available ? buildTreeData(aiModal.suggestion.nodes ?? []) : []),
    [aiModal.suggestion],
  );

  // ── 成员操作 ──

  const handleSearchUser = useCallback(async () => {
    const email = searchEmail.trim();
    if (!email) {
      message.warning("请输入邮箱关键词");
      return;
    }
    setSearching(true);
    setSelectedUser(null);
    try {
      const result = await searchBindableUsers(enterpriseId, email);
      setSearchResults(result);
      if (!result.length) message.info("未找到匹配的账号（可能已是企业成员）");
    } catch (e) {
      message.error(`搜索失败：${e instanceof Error ? e.message : "未知错误"}`);
    } finally {
      setSearching(false);
    }
  }, [enterpriseId, message, searchEmail]);

  const openMemberModal = useCallback((mode: "create" | "edit", member?: EnterpriseMember) => {
    setSearchResults([]);
    setSelectedUser(null);
    setSearchEmail("");
    form.resetFields();
    if (mode === "edit" && member) {
      form.setFieldsValue({
        org_node_id: member.org_node_id ?? undefined,
        position: member.position ?? "",
        role: member.role,
        enabled: member.enabled,
      });
    }
    setMemberModal({ open: true, mode, member });
  }, [form]);

  const submitMemberModal = useCallback(() => {
    form.validateFields().then(async values => {
      const payload = {
        org_node_id: values.org_node_id ?? null,
        position: values.position || null,
        role: values.role,
      };
      try {
        if (memberModal.mode === "edit" && memberModal.member) {
          await updateMember(enterpriseId, memberModal.member.id, {
            ...payload,
            enabled: values.enabled,
          });
          message.success("成员已更新");
        } else {
          if (!selectedUser) {
            message.error("请先按邮箱搜索并选择要绑定的账号");
            return;
          }
          await createMember(enterpriseId, { user_id: selectedUser.id, ...payload });
          message.success(`成员「${selectedUser.name}」已添加`);
        }
        setMemberModal({ open: false, mode: "create" });
        refetchAll();
      } catch (e) {
        message.error(`操作失败：${e instanceof Error ? e.message : "未知错误"}`);
      }
    });
  }, [enterpriseId, form, memberModal, message, refetchAll, selectedUser]);

  const toggleMemberEnabled = useCallback(
    async (member: EnterpriseMember) => {
      try {
        await updateMember(enterpriseId, member.id, { enabled: !member.enabled });
        message.success(member.enabled ? "已停用" : "已启用");
        refetchMembers();
      } catch (e) {
        message.error(`操作失败：${e instanceof Error ? e.message : "未知错误"}`);
      }
    },
    [enterpriseId, message, refetchMembers],
  );

  const handleDeleteMember = useCallback(
    async (member: EnterpriseMember) => {
      try {
        await deleteMember(enterpriseId, member.id);
        message.success("成员已删除");
        refetchAll();
      } catch (e) {
        message.error(`删除失败：${e instanceof Error ? e.message : "未知错误"}`);
      }
    },
    [enterpriseId, message, refetchAll],
  );

  // ── Excel 导入 ──

  const handleDownloadTemplate = useCallback(async () => {
    try {
      const res = await downloadMemberTemplate(enterpriseId);
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const a = document.createElement("a");
      a.href = url;
      a.download = "member_import_template.xlsx";
      a.click();
      window.URL.revokeObjectURL(url);
      message.success("模板已下载");
    } catch (e) {
      message.error(`下载失败：${e instanceof Error ? e.message : "未知错误"}`);
    }
  }, [enterpriseId, message]);

  const handleImportFile = useCallback(
    async (file: File) => {
      setImporting(true);
      try {
        const result = await importMembers(enterpriseId, file);
        if (result.errors.length) {
          modal.info({
            title: "导入完成",
            width: 560,
            content: (
              <div>
                <p>
                  成功导入 <b>{result.imported}</b> 条，跳过 <b>{result.skipped}</b> 条，
                  失败 <b>{result.errors.length}</b> 条。
                </p>
                <ul style={{ maxHeight: 260, overflow: "auto", paddingLeft: 20 }}>
                  {result.errors.map(e => (
                    <li key={e.row}>
                      第 {e.row} 行：{e.reason}
                    </li>
                  ))}
                </ul>
              </div>
            ),
          });
        } else {
          message.success(`导入成功 ${result.imported} 条${result.skipped ? `，跳过 ${result.skipped} 条` : ""}`);
        }
        refetchAll();
      } catch (e) {
        message.error(`导入失败：${e instanceof Error ? e.message : "未知错误"}`);
      } finally {
        setImporting(false);
      }
    },
    [enterpriseId, message, modal, refetchAll],
  );

  // ── 渲染 ──

  const columns: TableColumnsType<EnterpriseMember> = useMemo(
    () => [
      { title: "姓名", dataIndex: "name", width: 110, render: (v?: string | null) => v || "-" },
      { title: "邮箱", dataIndex: "email", width: 190, render: (v?: string | null) => v || "-" },
      {
        title: "部门班组",
        dataIndex: "org_node_id",
        width: 150,
        render: (v: string | null) => buildOrgPath(v, nodes) || "-",
      },
      { title: "岗位", dataIndex: "position", width: 110, render: (v?: string | null) => v || "-" },
      {
        title: "角色",
        dataIndex: "role",
        width: 100,
        render: (v: string) => {
          const meta = ROLE_META[v];
          return meta ? <Tag color={meta.color}>{meta.label}</Tag> : <Tag>{v}</Tag>;
        },
      },
      {
        title: "状态",
        dataIndex: "enabled",
        width: 80,
        render: (v: boolean) => (v ? <Tag color="green">启用</Tag> : <Tag color="red">停用</Tag>),
      },
      {
        title: "操作",
        key: "actions",
        width: 190,
        render: (_, member) => (
          <Space size={4}>
            <Button size="small" icon={<EditOutlined />} onClick={() => openMemberModal("edit", member)}>
              编辑
            </Button>
            <Button size="small" onClick={() => toggleMemberEnabled(member)}>
              {member.enabled ? "停用" : "启用"}
            </Button>
            <Popconfirm title={`确认删除成员「${member.name ?? member.email}」？`} onConfirm={() => handleDeleteMember(member)}>
              <Button size="small" danger icon={<DeleteOutlined />} />
            </Popconfirm>
          </Space>
        ),
      },
    ],
    [handleDeleteMember, nodes, openMemberModal, toggleMemberEnabled],
  );

  const treeTitle = (node: OrgNode) => (
    <Space size={4}>
      <Tag color={node.type === "dept" ? "blue" : node.type === "team" ? "cyan" : "purple"}>
        {TYPE_LABEL[node.type]}
      </Tag>
      <span>{node.name}</span>
      {node.type !== "position" && (
        <Button size="small" type="text" icon={<PlusOutlined />} onClick={() => openAddNode(node.type === "dept" ? "team" : "position", node.id)} />
      )}
      <Button size="small" type="text" icon={<EditOutlined />} onClick={() => openRenameNode(node)} />
      <Popconfirm title={`确认删除「${node.name}」及其下级？`} onConfirm={() => deleteNode(node)}>
        <Button size="small" type="text" danger icon={<DeleteOutlined />} />
      </Popconfirm>
    </Space>
  );

  // seen 防环：环形 parent_id 数据不无限递归，已访问节点跳过（保存仍由前后端校验拦截）
  function buildChildren(parentId: string, seen: Set<string> = new Set()): DataNode[] {
    return nodes
      .filter(n => n.parent_id === parentId && !seen.has(n.id))
      .map(n => {
        const nextSeen = new Set(seen);
        nextSeen.add(n.id);
        return {
          key: n.id,
          title: treeTitle(n),
          children: buildChildren(n.id, nextSeen),
        };
      });
  }

  // 只映射根节点（parent_id 为空），子节点由 buildChildren 按 parent_id 嵌套；
  // 孤儿节点（parent_id 指向缺失节点）挂到根层，避免节点在树中不可见、无法删除/改名
  // （前后端校验仍会拦截此类数据保存）。
  const treeData: DataNode[] = nodes
    .filter(n => !n.parent_id || !nodes.some(x => x.id === n.parent_id))
    .map(n => ({
      key: n.id,
      title: treeTitle(n),
      children: buildChildren(n.id, new Set([n.id])),
    }));

  const isLoading = nodesLoading || membersLoading;

  return (
    <div>
      <PageHeader
        title="组织与人员管理"
        subtitle="维护企业组织架构（部门/班组/岗位）与企业成员，支持 Excel 导入与 AI 建树"
        onBack={() => navigate(`/enterprises/${enterpriseId}`)}
        extra={
          <Space wrap>
            <Button icon={<DownloadOutlined />} onClick={handleDownloadTemplate}>
              下载导入模板
            </Button>
            <Upload
              accept=".xlsx"
              showUploadList={false}
              beforeUpload={file => {
                void handleImportFile(file);
                return false;
              }}
            >
              <Button icon={<UploadOutlined />} loading={importing}>
                Excel 导入
              </Button>
            </Upload>
            <Button icon={<ThunderboltOutlined />} type="primary" ghost onClick={handleAiSuggest}>
              AI 建树
            </Button>
            <Button icon={<SaveOutlined />} type="primary" disabled={!dirty} onClick={handleSaveTree}>
              保存组织树
            </Button>
          </Space>
        }
      />

      <div style={{ display: "flex", gap: 16, alignItems: "flex-start" }}>
        {/* 左：组织树 */}
        <div style={{ flex: 1, minWidth: 420, background: "#fff", borderRadius: 8, padding: 12, boxShadow: "0 2px 8px rgba(0,0,0,.08)" }}>
          <Space style={{ marginBottom: 12 }} wrap>
            <Button icon={<PlusOutlined />} onClick={() => openAddNode("dept", null)}>
              添加根部门
            </Button>
            <Button icon={<ApartmentOutlined />} onClick={() => openAddNode("position", null)}>
              添加根岗位
            </Button>
            {dirty && <Tag color="orange">有未保存的修改</Tag>}
          </Space>
          {isLoading ? (
            <Spin />
          ) : nodes.length === 0 ? (
            <Empty description="暂无组织架构，请添加部门/班组/岗位或使用 AI 建树" />
          ) : (
            <Tree
              key={nodes.map(n => n.id).join(",")}
              treeData={treeData}
              defaultExpandAll
              selectable={false}
            />
          )}
        </div>

        {/* 右：成员列表 */}
        <div style={{ flex: 2, background: "#fff", borderRadius: 8, padding: 12, boxShadow: "0 2px 8px rgba(0,0,0,.08)" }}>
          <Space style={{ marginBottom: 12 }}>
            <Button type="primary" icon={<UserAddOutlined />} onClick={() => openMemberModal("create")}>
              添加成员
            </Button>
            <span style={{ color: "#8c8c8c", fontSize: 13 }}>绑定已有账号：按邮箱搜索</span>
          </Space>
          <Table
            rowKey="id"
            size="small"
            loading={membersLoading}
            columns={columns}
            dataSource={members}
            pagination={false}
            locale={{ emptyText: <Empty description="暂无成员，可 Excel 导入或手动添加" /> }}
          />
        </div>
      </div>

      {/* 节点新增/改名 Modal */}
      <Modal
        title={nodeModal.mode === "add" ? `添加${nodeModal.type ? TYPE_LABEL[nodeModal.type] : "节点"}` : "重命名节点"}
        open={nodeModal.open}
        onCancel={() => setNodeModal({ open: false, mode: "add" })}
        onOk={submitNodeModal}
        destroyOnClose
      >
        <Form form={form} layout="vertical" autoComplete="off">
          <Form.Item
            name="name"
            label="名称"
            rules={[{ required: true, whitespace: true, message: "请输入名称" }]}
          >
            <Input placeholder="请输入节点名称" maxLength={50} />
          </Form.Item>
        </Form>
      </Modal>

      {/* 成员添加/编辑 Modal */}
      <Modal
        title={memberModal.mode === "edit" ? `编辑成员「${memberModal.member?.name ?? ""}」` : "添加成员（绑定已有账号）"}
        open={memberModal.open}
        onCancel={() => setMemberModal({ open: false, mode: "create" })}
        onOk={submitMemberModal}
        destroyOnClose
      >
        <Form form={form} layout="vertical" autoComplete="off">
          {memberModal.mode === "create" && (
            <>
              <Form.Item label="按邮箱搜索已有账号" required>
                <Space.Compact style={{ width: "100%" }}>
                  <Input
                    value={searchEmail}
                    onChange={e => setSearchEmail(e.target.value)}
                    placeholder="输入邮箱关键词，如 zhang@x.com"
                    allowClear
                    onPressEnter={handleSearchUser}
                  />
                  <Button icon={<SearchOutlined />} loading={searching} onClick={handleSearchUser}>
                    搜索
                  </Button>
                </Space.Compact>
              </Form.Item>
              <Form.Item label="选择账号" required>
                <Select
                  placeholder={searchResults.length ? "请选择要绑定的账号" : "先搜索，再从结果中选择"}
                  options={searchResults.map(u => ({
                    label: `${u.name}（${u.email}）`,
                    value: u.id,
                  }))}
                  value={selectedUser?.id}
                  onChange={id => setSelectedUser(searchResults.find(u => u.id === id) ?? null)}
                  notFoundContent={searching ? <Spin size="small" /> : "无匹配账号"}
                />
              </Form.Item>
            </>
          )}
          <Form.Item name="org_node_id" label="组织节点">
            <Select
              allowClear
              placeholder="选择部门/班组/岗位"
              options={nodeOptions}
              showSearch
              optionFilterProp="label"
            />
          </Form.Item>
          <Form.Item name="position" label="岗位名称">
            <Input placeholder="如 班组长/安全员" maxLength={50} />
          </Form.Item>
          <Form.Item name="role" label="角色" rules={[{ required: true, message: "请选择角色" }]}>
            <Select options={ROLE_OPTIONS} />
          </Form.Item>
          {memberModal.mode === "edit" && (
            <Form.Item name="enabled" label="启用状态" valuePropName="checked">
              <Switch checkedChildren="启用" unCheckedChildren="停用" />
            </Form.Item>
          )}
        </Form>
      </Modal>

      {/* AI 建树预览 Modal */}
      <Modal
        title="AI 建树建议"
        open={aiModal.open}
        onCancel={() => setAiModal({ open: false, suggestion: null, loading: false })}
        footer={
          aiModal.suggestion?.available
            ? [
                <Button key="cancel" onClick={() => setAiModal({ open: false, suggestion: null, loading: false })}>
                  取消
                </Button>,
                <Button key="apply" type="primary" onClick={() => aiModal.suggestion && applyAiSuggestion(aiModal.suggestion)}>
                  使用建议（未保存）
                </Button>,
              ]
            : [
                <Button key="close" onClick={() => setAiModal({ open: false, suggestion: null, loading: false })}>
                  关闭
                </Button>,
              ]
        }
      >
        {aiModal.loading ? (
          <div style={{ textAlign: "center", padding: 24 }}>
            <Spin tip="AI 正在分析企业信息并生成组织架构建议…" />
          </div>
        ) : aiModal.suggestion?.available === false ? (
          <Alert
            type="warning"
            showIcon
            message="AI 暂不可用"
            description={aiModal.suggestion.note || "AI 服务未配置或调用失败，请手动维护组织架构。"}
          />
        ) : aiModal.suggestion ? (
          <div>
            <Alert
              type="info"
              showIcon
              style={{ marginBottom: 12 }}
              message="以下为 AI 建议的组织架构，确认后将填充到左侧组织树（尚未保存，需手动点击保存）。"
            />
            <Tree treeData={aiTreeData} defaultExpandAll selectable={false} />
          </div>
        ) : null}
      </Modal>
    </div>
  );
}
