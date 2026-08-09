import { useNavigate, useParams } from "react-router-dom";
import { Spin, message } from "antd";
import axios from "axios";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getEnterprise, updateEnterprise } from "@/services/enterpriseService";
import { PageHeader } from "@/components/common/PageHeader";
import EnterpriseInfoCards from "@/components/enterprise/EnterpriseInfoCards";

function extractDetail(err: unknown): string {
  if (axios.isAxiosError(err)) {
    const detail = (err.response?.data as { detail?: unknown } | undefined)?.detail;
    if (typeof detail === "string" && detail) return detail;
    return err.message;
  }
  return err instanceof Error ? err.message : "";
}

export default function EnterpriseEditPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { data: enterprise, isLoading } = useQuery({
    queryKey: ["enterprise", id],
    queryFn: () => getEnterprise(id!),
    enabled: !!id,
  });
  const mutation = useMutation({
    mutationFn: (values: Record<string, unknown>) => updateEnterprise(id!, values as never),
    onSuccess: () => {
      message.success("保存成功");
      queryClient.invalidateQueries({ queryKey: ["enterprise", id] });
      queryClient.invalidateQueries({ queryKey: ["enterprises"] });
      navigate(`/enterprises/${id}`);
    },
    onError: (err: unknown) => message.error(extractDetail(err) || "保存失败"),
  });

  if (isLoading) return <Spin size="large" />;

  return (
    <div style={{ maxWidth: 720 }}>
      <PageHeader title="编辑企业" onBack={() => navigate(`/enterprises/${id}`)} />
      <EnterpriseInfoCards
        enterprise={enterprise}
        onSaved={async (values) => mutation.mutate(values)}
      />
    </div>
  );
}
