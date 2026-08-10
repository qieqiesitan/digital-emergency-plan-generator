import { useNavigate, useParams } from "react-router-dom";
import { PageHeader } from "@/components/common/PageHeader";
import EnterpriseInfoWorkspace from "@/components/enterprise/EnterpriseInfoWorkspace";

export default function EnterpriseEditPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  if (!id) return null;

  return (
    <div style={{ maxWidth: 720 }}>
      <PageHeader title="编辑企业" onBack={() => navigate(`/enterprises/${id}`)} />
      <EnterpriseInfoWorkspace enterpriseId={id} />
    </div>
  );
}
