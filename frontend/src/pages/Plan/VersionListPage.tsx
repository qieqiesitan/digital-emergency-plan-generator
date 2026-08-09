import { useParams, useNavigate } from "react-router-dom";
import { Table, Button, Modal, message } from "antd";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { listVersions, rollbackVersion } from "@/services/planService";
import { PageHeader } from "@/components/common/PageHeader";
import { formatDate } from "@/utils/formatters";

export default function VersionListPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { data: versions, isLoading } = useQuery({ queryKey: ["versions", id], queryFn: () => listVersions(id!), enabled: !!id });
  const rollbackMut = useMutation({
    mutationFn: (vid: string) => rollbackVersion(id!, vid),
    onSuccess: () => { message.success("已回滚"); queryClient.invalidateQueries({ queryKey: ["versions", id] }); queryClient.invalidateQueries({ queryKey: ["planSections", id] }); },
    onError: () => message.error("回滚失败"),
  });

  return (
    <div>
      <PageHeader title="版本历史" onBack={() => navigate(`/plans/${id}/edit`)} />
      <Table dataSource={versions || []} rowKey="id" loading={isLoading}
        columns={[
          { title: "版本", dataIndex: "version_number", render: (v: number) => "V" + v },
          { title: "类型", dataIndex: "created_by", render: (v: string) => v === "auto" ? "自动" : "手动" },
          { title: "说明", dataIndex: "description", render: (v: string | null) => v || "-" },
          { title: "时间", dataIndex: "created_at", render: formatDate },
          { title: "", render: (_: unknown, r: { id: string; version_number: number }) => (
            <Button onClick={() => Modal.confirm({ title: "确定回滚？", content: "确定回滚到 V" + r.version_number + "？", onOk: () => rollbackMut.mutate(r.id) })}>回滚</Button>
          )},
        ]}
      />
    </div>
  );
}
