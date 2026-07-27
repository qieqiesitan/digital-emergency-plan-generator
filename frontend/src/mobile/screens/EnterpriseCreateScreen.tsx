import React from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import NavBar from "@/mobile/components/ui/NavBar";
import SafeArea from "@/mobile/components/ui/SafeArea";
import EnterpriseForm from "@/mobile/components/enterprise/EnterpriseForm";
import Toast, { useToast } from "@/mobile/components/ui/Toast";
import type { EnterpriseFormData } from "@/mobile/components/enterprise/EnterpriseForm";
import { createEnterprise } from "@/services/enterpriseService";

export default function EnterpriseCreateScreen() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { showToast } = useToast();

  const mutation = useMutation({
    mutationFn: (data: EnterpriseFormData) =>
      createEnterprise({
        name: data.name,
        industry: data.industry,
        business_scope: data.business_scope || undefined,
        employee_count: data.employee_count,
        address: data.address || undefined,
      }),
    onSuccess: (newEnt) => {
      queryClient.invalidateQueries({ queryKey: ["enterprises"] });
      showToast?.("企业创建成功", "success");
      navigate(`/m/enterprises/${newEnt.id}`);
    },
    onError: () => {
      showToast?.("创建失败，请重试", "danger");
    },
  });

  return (
    <SafeArea className="bg-neutral-50 min-h-dvh">
      <NavBar title="新建企业" showBack onBack={() => navigate(-1)} />
      <div className="px-md py-md">
        <EnterpriseForm
          onSubmit={async (data) => mutation.mutateAsync(data)}
          submitLabel={mutation.isPending ? "创建中…" : "创建企业"}
        />
      </div>
    </SafeArea>
  );
}
