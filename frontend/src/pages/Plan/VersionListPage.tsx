import { useParams, useNavigate } from "react-router-dom";
import { Table, Button, Modal, message } from "antd";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { listVersions, rollbackVersion } from "@/services/versionService";
import { PageHeader } from "@/components/common/PageHeader";
import { formatDate } from "@/utils/formatters";

export default function VersionListPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { data: versions, isLoading } = useQuery({ queryKey: ["versions", id], queryFn: () => listVersions(id!), enabled: !!id });
  const rollbackMut = useMutation({
    mutationFn: (vid: string) => rollbackVersion(id!, vid),
    onSuccess: () => { message.success("rolled back"); queryClient.invalidateQueries({ queryKey: ["versions", id] }); queryClient.invalidateQueries({ queryKey: ["planSections", id] }); },
    onError: () => message.error("rollback failed"),
  });

  return (
    <div>
      <PageHeader title="version history" onBack={() => navigate(`/plans/${id}/edit`)} />
      <Table dataSource={versions || []} rowKey="id" loading={isLoading}
        columns={[
          { title: "version", dataIndex: "version_number", render: (v: number) => "V" + v },
          { title: "type", dataIndex: "created_by", render: (v: string) => v === "auto" ? "auto" : "manual" },
          { title: "note", dataIndex: "description", render: (v: string | null) => v || "-" },
          { title: "time", dataIndex: "created_at", render: formatDate },
          { title: "", render: (_: unknown, r: { id: string; version_number: number }) => (
            <Button onClick={() => Modal.confirm({ title: "rollback?", content: "rollback to V" + r.version_number + "?", onOk: () => rollbackMut.mutate(r.id) })}>rollback</Button>
          )},
        ]}
      />
    </div>
  );
}
