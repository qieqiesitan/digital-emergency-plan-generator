import React, { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Plus, FileText, Target, Factory, Building2, AlertTriangle, Search } from "lucide-react";
import NavBar from "@/mobile/components/ui/NavBar";
import SafeArea from "@/mobile/components/ui/SafeArea";
import Card from "@/mobile/components/ui/Card";
import EmptyState from "@/mobile/components/ui/EmptyState";
import Skeleton from "@/mobile/components/ui/Skeleton";
import Input from "@/mobile/components/ui/Input";
import { listEnterprises } from "@/services/enterpriseService";
import { getEnterprisePlanSummary } from "@/services/planService";

export default function PlanCardsScreen() {
  const navigate = useNavigate();
  const [search, setSearch] = useState("");

  const { data: enterprises = [], isLoading: entLoading, error: entError } = useQuery({
    queryKey: ["enterprises"],
    queryFn: async () => {
      const res = await listEnterprises({ page: 1, page_size: 100 });
      return res.data.items;
    },
    staleTime: 60000,
  });

  const { data: summaries = [], isLoading: sumLoading } = useQuery({
    queryKey: ["enterprise-plan-summary"],
    queryFn: getEnterprisePlanSummary,
    staleTime: 60000,
    retry: 1,
  });

  const isLoading = entLoading || sumLoading;

  const getSummary = (eid: string) =>
    summaries.find(s => s.enterprise_id === eid);

  // client-side enterprise name filter
  const filteredEnterprises = useMemo(() => {
    if (!search) return enterprises;
    const q = search.toLowerCase();
    return enterprises.filter(e => e.name.toLowerCase().includes(q));
  }, [enterprises, search]);

  // 璁＄畻鎬昏
  const totalStats = useMemo(() => {
    let comprehensive = 0, special = 0, onsite = 0;
    summaries.forEach(s => {
      comprehensive += s.comprehensive_count ?? 0;
      special += s.special_count ?? 0;
      onsite += s.onsite_count ?? 0;
    });
    return { comprehensive, special, onsite, total: comprehensive + special + onsite };
  }, [summaries]);

  if (isLoading) {
    return (
      <SafeArea className="bg-neutral-50 min-h-dvh">
        <NavBar title="预案管理" />
        <div className="px-md space-y-md mt-md">
          <div className="flex gap-md overflow-hidden">
            {[1, 2, 3].map(i => (
              <Skeleton key={i} variant="card" className="min-w-[100px] h-20 flex-1" />
            ))}
          </div>
          <div className="grid grid-cols-1 gap-3">
            {[1, 2, 3].map(i => (
              <Skeleton key={i} variant="card" className="h-32" />
            ))}
          </div>
        </div>
      </SafeArea>
    );
  }

  // API 閿欒
  if (entError && enterprises.length === 0) {
    return (
      <SafeArea className="bg-neutral-50 min-h-dvh">
        <NavBar title="预案管理" />
        <div className="pt-8">
          <EmptyState
            icon={<AlertTriangle size={48} className="text-red-300" />}
            title="加载失败"
            description="无法获取企业数据，请检查网络连接"
            action="重试"
            onAction={() => window.location.reload()}
          />
        </div>
      </SafeArea>
    );
  }

  // 鏃犱紒涓?
  if (enterprises.length === 0) {
    return (
      <SafeArea className="bg-neutral-50 min-h-dvh">
        <NavBar title="预案管理" />
        <div className="pt-8">
          <EmptyState
            icon={<Building2 size={48} className="text-neutral-300" />}
            title="暂无企业档案"
            description="先添加企业，再创建应急预案"
            action="添加企业"
            onAction={() => navigate("/m/enterprises/new")}
          />
        </div>
      </SafeArea>
    );
  }

  // 鍒嗙鏈夐妗堝拰鏃犻妗堢殑浼佷笟锛堜娇鐢ㄨ繃婊ゅ悗鐨勫垪琛級
  const withPlans = filteredEnterprises.filter(ent => {
    const s = getSummary(ent.id);
    return ((s?.comprehensive_count ?? 0) + (s?.special_count ?? 0) + (s?.onsite_count ?? 0)) > 0;
  });
  const withoutPlans = filteredEnterprises.filter(ent => !withPlans.includes(ent));

  return (
    <SafeArea className="bg-neutral-50 min-h-dvh">
      <NavBar title="预案管理" />

      <div className="px-md py-md space-y-lg">
        {/* 缁熻姒傝 */}
        {totalStats.total > 0 && (
          <div className="flex gap-3">
            <div className="flex-1 bg-white rounded-md shadow-card p-3 text-center">
              <p className="text-display text-info font-bold">{totalStats.comprehensive}</p>
              <p className="text-caption text-neutral-400 mt-1">综合预案</p>
            </div>
            <div className="flex-1 bg-white rounded-md shadow-card p-3 text-center">
              <p className="text-display text-warning font-bold">{totalStats.special}</p>
              <p className="text-caption text-neutral-400 mt-1">专项预案</p>
            </div>
            <div className="flex-1 bg-white rounded-md shadow-card p-3 text-center">
              <p className="text-display text-success font-bold">{totalStats.onsite}</p>
              <p className="text-caption text-neutral-400 mt-1">现场方案</p>
            </div>
          </div>
        )}

        {/* 鎼滅储 */}
        <div>
          <Input
            prefixIcon={<Search size={18} />}
            placeholder="搜索企业名称…"
            value={search}
            onChange={setSearch}
            className="bg-white"
          />
        </div>

        {/* 鏈夐妗堢殑浼佷笟 */}
        {withPlans.length > 0 && (
          <>
            <div className="flex items-center justify-between">
              <p className="text-h2">企业预案</p>
              <button
                className="text-caption text-primary-600"
                onClick={() => navigate("/m/enterprises")}
              >
                全部企业 →
              </button>
            </div>

            <div className="grid grid-cols-1 gap-3">
              {withPlans.map((ent) => {
                const s = getSummary(ent.id);
                const total = (s?.comprehensive_count ?? 0) + (s?.special_count ?? 0) + (s?.onsite_count ?? 0);

                return (
                  <Card
                    key={ent.id}
                    pressable
                    className="p-md"
                    onClick={() => navigate(`/m/enterprises/${ent.id}/plans`)}
                  >
                    <div className="flex items-center gap-md mb-3">
                      <div className="w-11 h-11 rounded-full bg-primary-50 flex items-center justify-center text-primary-600 font-semibold text-body shrink-0">
                        {ent.name.charAt(0)}
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-h3 font-semibold text-neutral-900 truncate">{ent.name}</p>
                        <p className="text-caption text-neutral-400">{ent.industry ?? "企业"}</p>
                      </div>
                      <div className="text-right shrink-0">
                        <p className="text-display text-primary-600 font-bold">{total}</p>
                        <p className="text-caption text-neutral-400">个预案</p>
                      </div>
                    </div>

                    <div className="flex gap-2">
                      {(s?.comprehensive_count ?? 0) > 0 && (
                        <span className="inline-flex items-center gap-1 px-2 py-1 bg-blue-50 text-info text-caption rounded-sm">
                          <FileText size={10} /> 综合 {s?.comprehensive_count}
                        </span>
                      )}
                      {(s?.special_count ?? 0) > 0 && (
                        <span className="inline-flex items-center gap-1 px-2 py-1 bg-amber-50 text-warning text-caption rounded-sm">
                          <Target size={10} /> 专项 {s?.special_count}
                        </span>
                      )}
                      {(s?.onsite_count ?? 0) > 0 && (
                        <span className="inline-flex items-center gap-1 px-2 py-1 bg-green-50 text-success text-caption rounded-sm">
                          <Factory size={10} /> 现场 {s?.onsite_count}
                        </span>
                      )}
                    </div>

                    <div className="flex gap-2 mt-3 pt-3 border-t border-neutral-50">
                      <button
                        className="flex-1 py-1.5 text-center text-caption text-primary-600 font-medium bg-primary-50 rounded-md"
                        onClick={(e) => {
                          e.stopPropagation();
                          navigate(`/m/enterprises/${ent.id}/plans`);
                        }}
                      >
                        查看预案
                      </button>
                      <button
                        className="flex-1 py-1.5 text-center text-caption text-white font-medium bg-primary-600 rounded-md flex items-center justify-center gap-1"
                        onClick={(e) => {
                          e.stopPropagation();
                          navigate(`/m/plans/new?enterprise_id=${ent.id}`);
                        }}
                      >
                        <Plus size={14} /> 新建
                      </button>
                    </div>
                  </Card>
                );
              })}
            </div>
          </>
        )}

        {/* 鏃犻妗堢殑浼佷笟 — 涔熷睍绀哄嚭鏉ワ紝寮曞鍒涘缓 */}
        {withoutPlans.length > 0 && (
          <>
            <div className="flex items-center justify-between">
              <p className="text-h2">
                {withPlans.length > 0 ? "其他企业" : "企业"}
              </p>
            </div>

            <div className="grid grid-cols-1 gap-3">
              {withoutPlans.map((ent) => (
                <Card
                  key={ent.id}
                  pressable
                  className="p-md border border-dashed border-neutral-200"
                  onClick={() => navigate(`/m/enterprises/${ent.id}/plans`)}
                >
                  <div className="flex items-center gap-md">
                    <div className="w-10 h-10 rounded-full bg-neutral-100 flex items-center justify-center text-neutral-400 font-semibold text-body shrink-0">
                      {ent.name.charAt(0)}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-h3 font-semibold text-neutral-900 truncate">{ent.name}</p>
                      <p className="text-caption text-neutral-400">
                        {ent.industry ? `${ent.industry} · ` : ""}暂无预案
                      </p>
                    </div>
                    <button
                      className="shrink-0 px-3 py-1.5 bg-primary-600 text-white rounded-md text-caption font-medium flex items-center gap-1"
                      onClick={(e) => {
                        e.stopPropagation();
                        navigate(`/m/plans/new?enterprise_id=${ent.id}`);
                      }}
                    >
                      <Plus size={14} /> 创建
                    </button>
                  </div>
                </Card>
              ))}
            </div>
          </>
        )}

        {/* 鎼滅储鏃犵粨鏋? */}
        {search && filteredEnterprises.length === 0 && (
          <div className="pt-4">
            <EmptyState
              icon={<Search size={40} className="text-neutral-300" />}
              title="未找到匹配企业"
              description="尝试其他关键词"
            />
          </div>
        )}

        {/* 鏋佺绌烘€? */}
        {!search && withPlans.length === 0 && withoutPlans.length > 0 && totalStats.total === 0 && (
          <div className="text-center py-6">
            <p className="text-body-sm text-neutral-400">
              以上企业暂未创建预案，点击「创建」开始
            </p>
          </div>
        )}
      </div>
    </SafeArea>
  );
}
