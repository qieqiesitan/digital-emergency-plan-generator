// @ts-nocheck
import React, { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  ChevronRight, Plus, FileText, Target, Factory,
  Edit3, Eye, Trash2, Search,
} from "lucide-react";
import { motion } from "framer-motion";
import NavBar from "@/mobile/components/ui/NavBar";
import SafeArea from "@/mobile/components/ui/SafeArea";
import Card from "@/mobile/components/ui/Card";
import Badge from "@/mobile/components/ui/Badge";
import Chip from "@/mobile/components/ui/Chip";
import EmptyState from "@/mobile/components/ui/EmptyState";
import FAB from "@/mobile/components/ui/FAB";
import Spinner from "@/mobile/components/ui/Spinner";
import Input from "@/mobile/components/ui/Input";
import Toast, { useToast } from "@/mobile/components/ui/Toast";
import { listPlans, deletePlan } from "@/services/planService";
import { getEnterprise } from "@/services/enterpriseService";
import { fromNow } from "@/utils/formatters";

const TYPE_LABELS: Record<string, { label: string; variant: "info" | "warning" | "success"; icon: React.ReactNode }> = {
  comprehensive: { label: "综合", variant: "info", icon: <FileText size={14} /> },
  special: { label: "专项", variant: "warning", icon: <Target size={14} /> },
  onsite: { label: "现场处置", variant: "success", icon: <Factory size={14} /> },
};

const TYPE_FILTERS = [
  { key: "", label: "全部" },
  { key: "comprehensive", label: "综合" },
  { key: "special", label: "专项" },
  { key: "onsite", label: "现场处置" },
];

const STATUS_FILTERS = [
  { key: "", label: "全部状态" },
  { key: "draft", label: "草稿" },
  { key: "completed", label: "已完成" },
];

export default function EnterprisePlanListScreen() {
  const { id: enterpriseId } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { showToast } = useToast();
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");

  const { data: enterprise } = useQuery({
    queryKey: ["enterprise", enterpriseId],
    queryFn: () => getEnterprise(enterpriseId!),
    enabled: !!enterpriseId,
  });

  const { data: plans = [], isLoading } = useQuery({
    queryKey: ["plans", enterpriseId, typeFilter, search, statusFilter],
    queryFn: async () => {
      const params: Record<string, unknown> = {
        enterprise_id: enterpriseId,
        page: 1,
        page_size: 100,
      };
      if (typeFilter) params.plan_type = typeFilter;
      if (search) params.search = search;
      if (statusFilter) params.status = statusFilter;
      const res = await listPlans(params as Parameters<typeof listPlans>[0]);
      return res.data.items;
    },
    enabled: !!enterpriseId,
  });

  const deleteMutation = useMutation({
    mutationFn: (pid: string) => deletePlan(pid),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["plans", enterpriseId] });
      showToast?.({ type: "success", message: "预案已删除" });
    },
    onError: () => showToast?.({ type: "error", message: "删除失败" }),
  });

  if (isLoading) {
    return (
      <SafeArea className="bg-neutral-50 min-h-dvh">
        <NavBar title="预案列表" showBack onBack={() => navigate(-1)} />
        <div className="px-md mt-md space-y-3">
          {[1, 2, 3].map(i => (
            <div key={i} className="flex items-center justify-center py-10">
              <Spinner size="lg" />
            </div>
          ))}
        </div>
      </SafeArea>
    );
  }

  const hasFilters = typeFilter || search || statusFilter;

  return (
    <SafeArea className="bg-neutral-50 min-h-dvh pb-20">
      <NavBar
        title={enterprise?.name ? `${enterprise.name} 的预案` : "预案列表"}
        showBack
        onBack={() => navigate(-1)}
        rightActions={[{
          icon: <Plus size={24} />,
          label: "新建",
          onPress: () => navigate(`/m/plans/new?enterprise_id=${enterpriseId}`),
        }]}
      />

      {/* 搜索 */}
      <div className="px-md pt-sm pb-1">
        <Input
          prefixIcon={<Search size={18} />}
          placeholder="搜索预案标题…"
          value={search}
          onChange={setSearch}
          className="bg-white"
        />
      </div>

      {/* 类型筛选 */}
      <div className="px-md pt-1 pb-1 flex gap-2 overflow-x-auto hide-scrollbar">
        {TYPE_FILTERS.map(f => (
          <Chip
            key={f.key}
            selected={typeFilter === f.key}
            onClick={() => setTypeFilter(f.key)}
          >
            {f.label}
          </Chip>
        ))}
      </div>

      {/* 状态筛选 */}
      <div className="px-md pb-2 flex gap-2 overflow-x-auto hide-scrollbar">
        {STATUS_FILTERS.map(f => (
          <Chip
            key={f.key}
            selected={statusFilter === f.key}
            onClick={() => setStatusFilter(f.key)}
          >
            {f.label}
          </Chip>
        ))}
      </div>

      {/* 列表 */}
      <div className="px-md py-2 space-y-2">
        {plans.map((plan) => {
          const typeInfo = TYPE_LABELS[plan.plan_type] ?? { label: plan.plan_type, variant: "default" as const, icon: <FileText size={14} /> };
          return (
            <motion.div key={plan.id} whileTap={{ scale: 0.99 }}>
              <Card
                pressable
                className="p-md"
                onClick={() => navigate(`/m/plans/${plan.id}/edit`)}
              >
                {/* 标题行 */}
                <div className="flex items-start gap-3">
                  <div className={`w-10 h-10 rounded-full flex items-center justify-center shrink-0 mt-0.5 ${
                    plan.plan_type === "comprehensive" ? "bg-blue-50 text-info" :
                    plan.plan_type === "special" ? "bg-amber-50 text-warning" :
                    "bg-green-50 text-success"
                  }`}>
                    {typeInfo.icon}
                  </div>

                  <div className="flex-1 min-w-0">
                    <p className="text-h3 font-semibold text-neutral-900 leading-snug line-clamp-2">
                      {plan.title}
                    </p>
                    {plan.accident_type && (
                      <p className="text-caption text-neutral-400 mt-0.5">
                        事故类型：{plan.accident_type}
                      </p>
                    )}
                    <div className="flex items-center flex-wrap gap-2 mt-2">
                      <Badge variant={typeInfo.variant}>{typeInfo.label}</Badge>
                      <span className={`inline-flex items-center gap-1 text-caption ${
                        plan.status === "completed" ? "text-success" :
                        plan.status === "generating" ? "text-info" :
                        "text-neutral-400"
                      }`}>
                        <span className={`w-1.5 h-1.5 rounded-full ${
                          plan.status === "completed" ? "bg-green-500" :
                          plan.status === "generating" ? "bg-blue-500" :
                          "bg-neutral-300"
                        }`} />
                        {plan.status === "completed" ? "已完成" :
                         plan.status === "generating" ? "生成中" : "草稿"}
                      </span>
                      <span className="text-caption text-neutral-300">
                        {fromNow(plan.updated_at)}
                      </span>
                    </div>
                  </div>

                  <ChevronRight size={16} className="text-neutral-300 shrink-0 mt-1" />
                </div>

                {/* 快捷操作栏 */}
                <div className="flex gap-2 mt-3 pt-3 border-t border-neutral-50">
                  <button
                    className="flex-1 flex items-center justify-center gap-1 py-1.5 text-caption text-primary-600 font-medium bg-primary-50 rounded-md active:bg-primary-100"
                    onClick={(e) => {
                      e.stopPropagation();
                      navigate(`/m/plans/${plan.id}/edit`);
                    }}
                  >
                    <Edit3 size={12} /> 编辑
                  </button>
                  <button
                    className="flex-1 flex items-center justify-center gap-1 py-1.5 text-caption text-neutral-600 font-medium bg-neutral-50 rounded-md active:bg-neutral-100"
                    onClick={(e) => {
                      e.stopPropagation();
                      navigate(`/m/plans/${plan.id}/preview`);
                    }}
                  >
                    <Eye size={12} /> 预览
                  </button>
                  <button
                    className="flex items-center justify-center w-9 h-8 text-caption text-red-400 font-medium bg-red-50 rounded-md active:bg-red-100"
                    onClick={(e) => {
                      e.stopPropagation();
                      if (window.confirm(`确定删除"${plan.title}"？此操作不可撤销。`)) {
                        deleteMutation.mutate(plan.id);
                      }
                    }}
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              </Card>
            </motion.div>
          );
        })}

        {plans.length === 0 && (
          <div className="pt-8">
            <EmptyState
              icon={<FileText size={48} className="text-neutral-300" />}
              title={hasFilters ? "未找到匹配预案" : "暂无预案"}
              description={hasFilters ? "尝试调整筛选条件" : "为当前企业创建第一个应急预案"}
              action={hasFilters ? undefined : "新建预案"}
              onAction={hasFilters ? undefined : () => navigate(`/m/plans/new?enterprise_id=${enterpriseId}`)}
            />
          </div>
        )}
      </div>

      <FAB
        icon={<Plus size={24} />}
        onClick={() => navigate(`/m/plans/new?enterprise_id=${enterpriseId}`)}
      />
    </SafeArea>
  );
}
