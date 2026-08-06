// @ts-nocheck
import React, { useState, useMemo } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { FileText, Target, Factory, ChevronRight, Check } from "lucide-react";
import { motion } from "framer-motion";
import NavBar from "@/mobile/components/ui/NavBar";
import SafeArea from "@/mobile/components/ui/SafeArea";
import Input from "@/mobile/components/ui/Input";
import Chip from "@/mobile/components/ui/Chip";
import Card from "@/mobile/components/ui/Card";
import Button from "@/mobile/components/ui/Button";
import Toast, { useToast } from "@/mobile/components/ui/Toast";
import { listEnterprises } from "@/services/enterpriseService";
import { getFullHierarchy } from "@/services/riskManagementService";
import { createPlan } from "@/services/planService";
import type { PlanType } from "@/types/plan";

const TYPE_OPTIONS: { type: PlanType; icon: React.ReactNode; title: string; desc: string }[] = [
  { type: "comprehensive", icon: <FileText size={28} />, title: "综合应急预案", desc: "覆盖全企业的应急管理总纲，自动从企业信息生成框架" },
  { type: "special", icon: <Target size={28} />, title: "专项应急预案", desc: "针对火灾、触电等特定事故类型，关联企业风险源" },
  { type: "onsite", icon: <Factory size={28} />, title: "现场处置方案", desc: "一线操作卡片，简明处置步骤" },
];

export default function PlanCreateScreen() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const queryClient = useQueryClient();
  const { showToast } = useToast();

  const preselectedEnterpriseId = searchParams.get("enterprise_id") ?? "";
  const preselectedType = (searchParams.get("type") as PlanType) ?? "";

  const [step, setStep] = useState<1 | 2 | 3>(preselectedType ? 2 : 1);
  const [selectedType, setSelectedType] = useState<PlanType>(preselectedType);
  const [selectedEnterpriseId, setSelectedEnterpriseId] = useState(preselectedEnterpriseId);
  const [title, setTitle] = useState("");
  const [accidentTypes, setAccidentTypes] = useState<string[]>([]);

  const { data: enterprises = [] } = useQuery({
    queryKey: ["enterprises"],
    queryFn: async () => {
      const res = await listEnterprises({ page: 1, page_size: 100 });
      return res.data.items;
    },
  });

  const { data: riskHierarchy = [] } = useQuery({
    queryKey: ["risk-hierarchy", selectedEnterpriseId],
    queryFn: () => getFullHierarchy(selectedEnterpriseId),
    enabled: !!selectedEnterpriseId,
  });

  const enterprise = useMemo(
    () => enterprises.find(e => e.id === selectedEnterpriseId),
    [enterprises, selectedEnterpriseId]
  );

  const accidentOptions = useMemo(
    () => [
      ...new Set(
        riskHierarchy.flatMap((zone) =>
          (zone.objects || []).flatMap((obj) => [
            ...(obj.events || []).map((ev) => ev.accident_type),
            ...(obj.units || []).flatMap((unit) => (unit.events || []).map((ev) => ev.accident_type)),
          ])
        )
      ),
    ],
    [riskHierarchy]
  );

  const defaultTitle = useMemo(() => {
    if (!enterprise) return "";
    if (selectedType === "comprehensive") return `${enterprise.name} 综合应急预案`;
    if (accidentTypes.length === 0) return "";
    if (selectedType === "special") return `${enterprise.name} ${accidentTypes.join("、")}专项应急预案`;
    return `${enterprise.name} ${accidentTypes.join("、")}现场处置方案`;
  }, [enterprise, selectedType, accidentTypes]);

  const createMutation = useMutation({
    mutationFn: () =>
      createPlan({
        enterprise_id: selectedEnterpriseId,
        plan_type: selectedType,
        title: title || defaultTitle,
        accident_type: accidentTypes.length > 0 ? accidentTypes.join("、") : undefined,
      }),
    onSuccess: (newPlan) => {
      queryClient.invalidateQueries({ queryKey: ["plans"] });
      queryClient.invalidateQueries({ queryKey: ["enterprise-plan-summary"] });
      showToast?.({ type: "success", message: "预案创建成功" });
      navigate(`/m/plans/${newPlan.id}/edit`);
    },
    onError: () => showToast?.({ type: "error", message: "创建失败，请重试" }),
  });

  const canSubmit = selectedType && selectedEnterpriseId && (title || defaultTitle);

  // 进度指示
  const steps = [
    { num: 1, label: "选择类型" },
    { num: 2, label: "企业 & 事故" },
    { num: 3, label: "确认创建" },
  ];

  return (
    <SafeArea className="bg-neutral-50 min-h-dvh">
      <NavBar title="新建预案" showBack onBack={() => navigate(-1)} />

      {/* 步骤指示器 */}
      <div className="flex items-center justify-center gap-2 px-md py-4 bg-white border-b border-neutral-100">
        {steps.map((s, i) => (
          <React.Fragment key={s.num}>
            <div className="flex items-center gap-1.5">
              <div className={`w-6 h-6 rounded-full flex items-center justify-center text-caption font-semibold ${
                step >= s.num ? "bg-primary-600 text-white" : "bg-neutral-100 text-neutral-400"
              }`}>
                {step > s.num ? <Check size={12} /> : s.num}
              </div>
              <span className={`text-caption ${step >= s.num ? "text-primary-600 font-medium" : "text-neutral-400"}`}>
                {s.label}
              </span>
            </div>
            {i < steps.length - 1 && (
              <div className={`w-8 h-px ${step > s.num ? "bg-primary-600" : "bg-neutral-200"}`} />
            )}
          </React.Fragment>
        ))}
      </div>

      <div className="px-md py-lg">
        {/* 第 1 步：选择类型 */}
        {step === 1 && (
          <motion.div initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }}>
            <p className="text-h2 mb-1">选择预案类型</p>
            <p className="text-body-sm text-neutral-500 mb-lg">不同类型的预案结构和适用范围不同</p>

            <div className="space-y-3">
              {TYPE_OPTIONS.map(opt => (
                <Card
                  key={opt.type}
                  pressable
                  selected={selectedType === opt.type}
                  className="flex items-center gap-md p-md"
                  onClick={() => setSelectedType(opt.type)}
                >
                  <div className={`w-12 h-12 rounded-full flex items-center justify-center shrink-0 ${
                    selectedType === opt.type ? "bg-primary-600 text-white" : "bg-primary-50 text-primary-600"
                  }`}>
                    {opt.icon}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-body font-semibold text-neutral-900">{opt.title}</p>
                    <p className="text-caption text-neutral-400 mt-0.5">{opt.desc}</p>
                  </div>
                  {selectedType === opt.type && (
                    <div className="w-6 h-6 rounded-full bg-primary-600 flex items-center justify-center">
                      <Check size={14} className="text-white" />
                    </div>
                  )}
                </Card>
              ))}
            </div>

            <div className="mt-lg">
              <Button
                variant="primary"
                size="lg"
                fullWidth
                disabled={!selectedType}
                onClick={() => setStep(2)}
              >
                下一步 <ChevronRight size={18} className="ml-xs" />
              </Button>
            </div>
          </motion.div>
        )}

        {/* 第 2 步：企业 & 事故类型 */}
        {step === 2 && (
          <motion.div initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }}>
            <p className="text-h2 mb-1">选择企业与事故类型</p>
            <p className="text-body-sm text-neutral-500 mb-lg">预案关联到企业，并根据风险源自动推荐事故类型</p>

            {/* 企业选择 */}
            <div className="mb-lg">
              <label className="block text-body-sm font-medium text-neutral-600 mb-2">所属企业</label>
              <div className="grid grid-cols-2 gap-2">
                {enterprises.map(ent => (
                  <button
                    key={ent.id}
                    className={`p-3 rounded-md border text-left transition-colors ${
                      selectedEnterpriseId === ent.id
                        ? "border-primary-600 bg-primary-50"
                        : "border-neutral-200 bg-white"
                    }`}
                    onClick={() => setSelectedEnterpriseId(ent.id)}
                  >
                    <div className="flex items-center gap-2">
                      <div className="w-8 h-8 rounded-full bg-primary-50 flex items-center justify-center text-primary-600 font-semibold text-caption shrink-0">
                        {ent.name.charAt(0)}
                      </div>
                      <span className="text-body-sm text-neutral-900 truncate">{ent.name}</span>
                    </div>
                  </button>
                ))}
              </div>
            </div>

            {/* 事故类型（专项/现场） */}
            {selectedType !== "comprehensive" && (
              <div className="mb-lg">
                <label className="block text-body-sm font-medium text-neutral-600 mb-2">
                  事故类型 {accidentTypes.length > 0 && <span className="text-primary-600">({accidentTypes.length} 个已选)</span>}
                </label>
                {accidentOptions.length > 0 ? (
                  <div className="flex flex-wrap gap-2">
                    {accidentOptions.map(name => (
                      <Chip
                        key={name}
                        selected={accidentTypes.includes(name)}
                        onClick={() =>
                          setAccidentTypes(prev =>
                            prev.includes(name) ? prev.filter(n => n !== name) : [...prev, name]
                          )
                        }
                      >
                        {name}
                      </Chip>
                    ))}
                  </div>
                ) : (
                  <Input
                    placeholder="输入事故类型，多个用、分隔（如：火灾、触电）"
                    value={accidentTypes.join("、")}
                    onChange={(v) => setAccidentTypes(v ? v.split(/[、,]/).filter(Boolean) : [])}
                  />
                )}
              </div>
            )}

            {/* 企业信息摘要 */}
            {enterprise && (
              <div className="bg-white rounded-md shadow-card p-md mb-lg">
                <p className="text-caption text-neutral-400 mb-2">企业信息确认</p>
                <div className="text-body-sm space-y-1">
                  <p><span className="text-neutral-400">名称：</span><span className="text-neutral-900">{enterprise.name}</span></p>
                  {enterprise.industry && <p><span className="text-neutral-400">行业：</span><span className="text-neutral-900">{enterprise.industry}</span></p>}
                  {enterprise.risk_events_count !== undefined && (
                    <p><span className="text-neutral-400">风险事件：</span><span className="text-neutral-900">{enterprise.risk_events_count} 个</span></p>
                  )}
                </div>
              </div>
            )}

            <div className="flex gap-sm">
              <Button variant="secondary" size="lg" className="flex-1" onClick={() => setStep(1)}>
                上一步
              </Button>
              <Button
                variant="primary"
                size="lg"
                className="flex-1"
                disabled={!selectedEnterpriseId || (selectedType !== "comprehensive" && accidentTypes.length === 0)}
                onClick={() => setStep(3)}
              >
                下一步 <ChevronRight size={18} className="ml-xs" />
              </Button>
            </div>
          </motion.div>
        )}

        {/* 第 3 步：确认并创建 */}
        {step === 3 && (
          <motion.div initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }}>
            <p className="text-h2 mb-1">确认预案信息</p>
            <p className="text-body-sm text-neutral-500 mb-lg">确认无误后点击创建，即可进入编辑器</p>

            {/* 摘要卡片 */}
            <Card className="p-md mb-lg">
              <div className="space-y-4">
                <div className="flex items-start gap-3">
                  <div className="w-10 h-10 rounded-full bg-primary-50 flex items-center justify-center text-primary-600 shrink-0">
                    {TYPE_OPTIONS.find(o => o.type === selectedType)?.icon ?? <FileText size={20} />}
                  </div>
                  <div>
                    <p className="text-body-sm font-medium text-neutral-900">
                      {TYPE_OPTIONS.find(o => o.type === selectedType)?.title}
                    </p>
                    <p className="text-caption text-neutral-400 mt-0.5">预案类型</p>
                  </div>
                </div>

                <div className="border-t border-neutral-50 pt-3">
                  <p className="text-caption text-neutral-400 mb-1">预案标题</p>
                  <Input
                    value={title || defaultTitle}
                    onChange={setTitle}
                    placeholder={defaultTitle || "输入预案标题"}
                  />
                </div>

                <div className="border-t border-neutral-50 pt-3">
                  <p className="text-caption text-neutral-400 mb-1">所属企业</p>
                  <p className="text-body text-neutral-900">{enterprise?.name}</p>
                </div>

                {accidentTypes.length > 0 && (
                  <div className="border-t border-neutral-50 pt-3">
                    <p className="text-caption text-neutral-400 mb-1">事故类型</p>
                    <div className="flex flex-wrap gap-1">
                      {accidentTypes.map(t => (
                        <Chip key={t}>{t}</Chip>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </Card>

            <div className="flex gap-sm">
              <Button variant="secondary" size="lg" className="flex-1" onClick={() => setStep(2)}>
                上一步
              </Button>
              <Button
                variant="primary"
                size="lg"
                className="flex-1"
                disabled={!canSubmit || createMutation.isPending}
                loading={createMutation.isPending}
                onClick={() => createMutation.mutate()}
              >
                创建预案
              </Button>
            </div>
          </motion.div>
        )}
      </div>
    </SafeArea>
  );
}
