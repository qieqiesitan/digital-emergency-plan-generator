import { useState } from "react";
import { Modal, Table, Button, Input, Select, Space, message } from "antd";
import { PlusOutlined, DeleteOutlined } from "@ant-design/icons";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { updateOrgStructure } from "@/services/enterpriseService";
import type { OrgGroup, OrgMember } from "@/types/enterprise";
import { PRESET_EMERGENCY_GROUPS } from "@/utils/constants";

interface Props {
  enterpriseId: string;
  orgStructure: OrgGroup[];
  visible: boolean;
  onClose: () => void;
}

export default function OrgStructureEditor({ enterpriseId, orgStructure, visible, onClose }: Props) {
  const [groups, setGroups] = useState<OrgGroup[]>(() => {
    if (orgStructure.length === 0) {
      return Object.entries(PRESET_EMERGENCY_GROUPS).map(([key, name]) => ({
        group_key: key, group_name: name, members: [],
      }));
    }
    return JSON.parse(JSON.stringify(orgStructure));
  });
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: (data: OrgGroup[]) => updateOrgStructure(enterpriseId, data),
    onSuccess: () => {
      message.success("保存成功");
      queryClient.invalidateQueries({ queryKey: ["enterprise", enterpriseId] });
      onClose();
    },
    onError: () => message.error("保存失败"),
  });

  const addMember = (groupIdx: number) => {
    setGroups((prev) => {
      const next = [...prev];
      next[groupIdx] = {
        ...next[groupIdx],
        members: [...next[groupIdx].members, { role: "", name: "", position: "", phone: "", responsibilities: "" }],
      };
      return next;
    });
  };

  const updateMember = (groupIdx: number, memberIdx: number, field: keyof OrgMember, value: string) => {
    setGroups((prev) => {
      const next = [...prev];
      const members = [...next[groupIdx].members];
      members[memberIdx] = { ...members[memberIdx], [field]: value };
      next[groupIdx] = { ...next[groupIdx], members };
      return next;
    });
  };

  const removeMember = (groupIdx: number, memberIdx: number) => {
    setGroups((prev) => {
      const next = [...prev];
      next[groupIdx] = { ...next[groupIdx], members: next[groupIdx].members.filter((_, i) => i !== memberIdx) };
      return next;
    });
  };

  const ROLE_OPTIONS = [
    { value: "chief", label: "总指挥" },
    { value: "deputy", label: "副总指挥" },
    { value: "leader", label: "组长" },
    { value: "member", label: "成员" },
  ];

  return (
    <Modal title="编辑组织架构" open={visible} onCancel={onClose} width={900}
      footer={[
        <Button key="cancel" onClick={onClose}>取消</Button>,
        <Button key="save" type="primary" loading={mutation.isPending} onClick={() => mutation.mutate(groups)}>保存</Button>,
      ]}
    >
      {groups.map((group, gi) => (
        <div key={group.group_key} style={{ marginBottom: 24 }}>
          <h4>{group.group_name}</h4>
          <Table
            dataSource={group.members}
            rowKey={(r: any) => (r as any)._key || ((r as any)._key = crypto.randomUUID?.() || `k-${Math.random()}`)}
            pagination={false}
            size="small"
            columns={[
              { title: "角色", dataIndex: "role", render: (_: string, __: OrgMember, i: number) => (
                <Select style={{ width: 120 }} value={group.members[i]?.role || undefined}
                  onChange={(v) => updateMember(gi, i, "role", v)}
                  options={ROLE_OPTIONS} />
              )},
              { title: "姓名", render: (_: string, __: OrgMember, i: number) => (
                <Input value={group.members[i]?.name || ""} onChange={(e) => updateMember(gi, i, "name", e.target.value)} />
              )},
              { title: "公司职位", render: (_: string, __: OrgMember, i: number) => (
                <Input value={group.members[i]?.position || ""} onChange={(e) => updateMember(gi, i, "position", e.target.value)} />
              )},
              { title: "电话", render: (_: string, __: OrgMember, i: number) => (
                <Input value={group.members[i]?.phone || ""} onChange={(e) => updateMember(gi, i, "phone", e.target.value)} />
              )},
              { title: "", render: (_: string, __: OrgMember, i: number) => (
                <Button type="text" danger icon={<DeleteOutlined />} onClick={() => removeMember(gi, i)} />
              )},
            ]}
          />
          <Button type="dashed" icon={<PlusOutlined />} onClick={() => addMember(gi)} style={{ marginTop: 8 }} block>
            添加成员
          </Button>
        </div>
      ))}
    </Modal>
  );
}
