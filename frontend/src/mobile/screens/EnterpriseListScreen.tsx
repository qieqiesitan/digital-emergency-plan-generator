import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Search, Building2 } from "lucide-react";
import NavBar from "@/mobile/components/ui/NavBar";
import SafeArea from "@/mobile/components/ui/SafeArea";
import Input from "@/mobile/components/ui/Input";
import EmptyState from "@/mobile/components/ui/EmptyState";
import EnterpriseCard from "@/mobile/components/enterprise/EnterpriseCard";
import Toast, { useToast } from "@/mobile/components/ui/Toast";
import { listEnterprises, deleteEnterprise } from "@/services/enterpriseService";

export default function EnterpriseListScreen() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { showToast } = useToast();
  const [search, setSearch] = useState("");

  const { data: enterprises = [] } = useQuery({
    queryKey: ["enterprises"],
    queryFn: async () => {
      const res = await listEnterprises({ page: 1, page_size: 100 });
      return res.data.items;
    },
    staleTime: 60000,
  });

  const deleteMutation = useMutation({
    mutationFn: deleteEnterprise,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["enterprises"] });
      showToast?.("企业已删除", "success");
    },
    onError: () => showToast?.("删除失败", "danger"),
  });

  const filtered = enterprises.filter(
    (e) => !search || e.name.toLowerCase().includes(search.toLowerCase())
  );

  const handleDelete = (id: string, name: string) => {
    if (window.confirm(`确定删除"${name}"及其全部关联数据？此操作不可撤销。`)) {
      deleteMutation.mutate(id);
    }
  };

  return (
    <SafeArea className="bg-neutral-50 min-h-dvh">
      <NavBar
        title="企业列表"
        rightActions={[{
          icon: <Plus size={24} />,
          label: "新建企业",
          onPress: () => navigate("/m/enterprises/new"),
        }]}
      />
      <div className="px-md pt-md pb-md">
        <Input
          prefixIcon={<Search size={18} />}
          placeholder="搜索企业名称…"
          value={search}
          onChange={setSearch}
          className="bg-white"
        />
      </div>
      <div className="px-md space-y-2">
        {filtered.map((ent) => (
          <EnterpriseCard
            key={ent.id}
            enterprise={ent}
            onPress={() => navigate(`/m/enterprises/${ent.id}`)}
            onDelete={() => handleDelete(ent.id, ent.name)}
          />
        ))}
        {filtered.length === 0 && enterprises.length > 0 && (
          <EmptyState
            icon={<Search size={40} className="text-neutral-300" />}
            title="未找到匹配企业"
          />
        )}
        {enterprises.length === 0 && (
          <EmptyState
            icon={<Building2 size={40} className="text-neutral-300" />}
            title="暂无企业档案"
            description="添加企业后即可开始创建应急预案"
            action="创建企业"
            onAction={() => navigate("/m/enterprises/new")}
          />
        )}
      </div>
    </SafeArea>
  );
}
