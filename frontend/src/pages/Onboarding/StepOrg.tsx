import { useState } from "react";
import { Button, Input, Table, message } from "antd";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import { getEnterprise, updateOrgStructure } from "@/services/enterpriseService";
import api from "@/services/api";
import type { OrgGroup } from "@/types/enterprise";

interface Props {
  enterpriseId: string;
  onDone: () => void;
  onPrev: () => void;
}

// 后端候选额外返回组级职责描述，前端类型未声明该字段
type OrgCandidate = OrgGroup & { responsibilities?: string };

export default function StepOrg({ enterpriseId, onDone, onPrev }: Props) {
  const queryClient = useQueryClient();
  const [overview, setOverview] = useState("");
  const [candidates, setCandidates] = useState<OrgCandidate[]>([]);
  const [generating, setGenerating] = useState(false);
  const { data: enterprise, isLoading } = useQuery({
    queryKey: ["enterprise", enterpriseId],
    queryFn: () => getEnterprise(enterpriseId),
    enabled: !!enterpriseId,
  });
  const accepted = enterprise?.org_structure || [];

  const generate = async () => {
    setGenerating(true);
    try {
      const r = await api.post("/onboarding/candidates", {
        enterprise_id: enterpriseId,
        module: "org",
        overview,
      });
      setCandidates(r.data.data.items || []);
    } catch (e) {
      message.error(
        axios.isAxiosError(e) && e.response?.data?.detail
          ? e.response.data.detail
          : "生成失败",
      );
    } finally {
      setGenerating(false);
    }
  };

  const saveMut = useMutation({
    mutationFn: (groups: OrgGroup[]) => updateOrgStructure(enterpriseId, groups),
    onSuccess: () => {
      message.success("组织架构已保存");
      queryClient.invalidateQueries({ queryKey: ["enterprise", enterpriseId] });
      queryClient.invalidateQueries({ queryKey: ["completion", enterpriseId] });
    },
    onError: () => message.error("保存失败，请重试"),
  });

  const adoptAll = async () => {
    if (isLoading) return;
    const merged = [...accepted];
    candidates.forEach(g => {
      const key = g.group_key || g.group_name || `g-${merged.length}`;
      if (!merged.some(x => x.group_key === key || x.group_name === key))
        merged.push({ ...g, group_key: key });
    });
    try {
      await saveMut.mutateAsync(merged);
      setCandidates([]);
    } catch {
      // onError 已提示
    }
  };

  return (
    <div style={{ maxWidth: 760 }}>
      <h3>组织架构</h3>
      <p style={{ color: "#666", fontSize: 13 }}>
        突发事件谁来指挥、谁负责什么——预案「应急组织机构及职责」章节直接用它
      </p>
      <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
        <Input.TextArea
          rows={2}
          value={overview}
          onChange={e => setOverview(e.target.value)}
          placeholder="企业概况（可留空，AI 按行业/规模自动生成）"
        />
        <Button type="primary" loading={generating} onClick={generate}>
          AI 生成候选
        </Button>
      </div>
      {candidates.length > 0 && (
        <>
          {candidates.map(g => (
            <div
              key={g.group_key}
              style={{
                border: "1px solid #1677ff",
                borderRadius: 8,
                padding: 10,
                marginBottom: 8,
                background: "#f0f7ff",
              }}
            >
              <b>{g.group_name}</b>
              <div style={{ color: "#666", fontSize: 12, margin: "4px 0" }}>
                {g.responsibilities}
              </div>
              <Table
                size="small"
                pagination={false}
                rowKey={(_, i) => `m-${i}`}
                dataSource={g.members || []}
                columns={[
                  { title: "角色", dataIndex: "role" },
                  {
                    title: "姓名",
                    dataIndex: "name",
                    render: (v: string) =>
                      v || <span style={{ color: "#fa8c16" }}>待填</span>,
                  },
                  {
                    title: "公司职位",
                    dataIndex: "position",
                    render: (v: string) => v || "-",
                  },
                  {
                    title: "电话",
                    dataIndex: "phone",
                    render: (v: string) =>
                      v || <span style={{ color: "#fa8c16" }}>待填</span>,
                  },
                ]}
              />
            </div>
          ))}
          <Button
            type="primary"
            onClick={adoptAll}
            disabled={isLoading}
            style={{ marginBottom: 12 }}
          >
            全部采纳（姓名电话请到企业详情补充）
          </Button>
        </>
      )}
      <div style={{ marginTop: 20, display: "flex", justifyContent: "space-between" }}>
        <Button onClick={onPrev}>上一步</Button>
        <Button type="primary" onClick={onDone}>
          标记完成，下一步 →
        </Button>
      </div>
    </div>
  );
}
