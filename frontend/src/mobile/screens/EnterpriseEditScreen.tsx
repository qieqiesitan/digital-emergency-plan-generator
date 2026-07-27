import React from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import NavBar from "@/mobile/components/ui/NavBar";
import SafeArea from "@/mobile/components/ui/SafeArea";
import EnterpriseForm from "@/mobile/components/enterprise/EnterpriseForm";
import Skeleton from "@/mobile/components/ui/Skeleton";
import Toast, { useToast } from "@/mobile/components/ui/Toast";
import type { EnterpriseFormData } from "@/mobile/components/enterprise/EnterpriseForm";
import { getEnterprise, updateEnterprise, deleteEnterprise } from "@/services/enterpriseService";

export default function EnterpriseEditScreen() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { showToast } = useToast();

  const { data: enterprise, isLoading } = useQuery({
    queryKey: ["enterprise", id],
    queryFn: () => getEnterprise(id!),
    enabled: !!id,
  });

  const updateMutation = useMutation({
    mutationFn: (data: EnterpriseFormData) =>
      updateEnterprise(id!, {
        name: data.name,
        industry: data.industry,
        business_scope: data.business_scope || undefined,
        employee_count: data.employee_count,
        address: data.address || undefined,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["enterprises"] });
      queryClient.invalidateQueries({ queryKey: ["enterprise", id] });
      showToast?.("企业信息已更新", "success");
      navigate(`/m/enterprises/${id}`);
    },
    onError: () => showToast?.("更新失败", "danger"),
  });

  const deleteMutation = useMutation({
    mutationFn: () => deleteEnterprise(id!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["enterprises"] });
      showToast?.("企业已删除", "success");
      navigate("/m/enterprises");
    },
    onError: () => showToast?.("删除失败", "danger"),
  });

  const handleDelete = () => {
    if (window.confirm(`确定删除"${enterprise?.name}"及其全部关联数据？此操作不可撤销。`)) {
      deleteMutation.mutate();
    }
  };

  if (isLoading) {
    return (
      <SafeArea className="bg-neutral-50 min-h-dvh">
        <NavBar title="编辑企业" showBack onBack={() => navigate(-1)} />
        <div className="px-md space-y-md mt-md">
          <Skeleton variant="card" className="h-64" />
        </div>
      </SafeArea>
    );
  }

  if (!enterprise) return null;

  return (
    <SafeArea className="bg-neutral-50 min-h-dvh">
      <NavBar title="编辑企业" showBack onBack={() => navigate(-1)} />
      <div className="px-md py-md">
        <EnterpriseForm
          initialValues={{
            name: enterprise.name,
            industry: enterprise.industry ?? "",
            business_scope: enterprise.business_scope ?? "",
            employee_count: enterprise.employee_count,
            address: enterprise.address ?? "",
          }}
          onSubmit={async (data) => updateMutation.mutateAsync(data)}
          submitLabel={updateMutation.isPending ? "保存中…" : "保存"}
        />
        {/* 删除按钮 */}
        <div className="mt-lg pb-lg text-center">
          <button
            className="text-red-500 text-body font-medium py-2"
            onClick={handleDelete}
            disabled={deleteMutation.isPending}
          >
            {deleteMutation.isPending ? "删除中…" : "删除企业"}
          </button>
        </div>
      </div>
    </SafeArea>
  );
}
