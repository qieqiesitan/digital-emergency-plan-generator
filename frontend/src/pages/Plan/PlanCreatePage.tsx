import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Steps, Card, Button, Select, Input, message, Space, Typography, Descriptions } from "antd";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createPlan } from "@/services/planService";
import { useCurrentEnterprise } from "@/contexts/EnterpriseContext";
import { getEnterprise } from "@/services/enterpriseService";
import { PageHeader } from "@/components/common/PageHeader";
import { PlanTypeTag } from "@/components/plan/PlanTypeTag";
import { PLAN_TYPE_LABELS } from "@/utils/constants";
import type { PlanType } from "@/types/plan";

const { Title, Text } = Typography;

export default function PlanCreatePage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [searchParams] = useSearchParams();
  const initType = (searchParams.get("type") as PlanType) || null;
  const queryEnterpriseId = searchParams.get("enterprise_id");
  const { currentEnterpriseId } = useCurrentEnterprise();

  const effectiveEnterpriseId = queryEnterpriseId || currentEnterpriseId;

  const [currentStep, setCurrentStep] = useState(0);
  const [planType, setPlanType] = useState<PlanType | null>(initType);
  const [accidentType, setAccidentType] = useState<string>("");
  const [title, setTitle] = useState("");

  const { data: enterprise } = useQuery({
    queryKey: ["enterprise", effectiveEnterpriseId],
    queryFn: () => getEnterprise(effectiveEnterpriseId!),
    enabled: !!effectiveEnterpriseId,
  });

  const mutation = useMutation({
    mutationFn: createPlan,
    onSuccess: (data) => {
      message.success("预案创建成功");
      queryClient.invalidateQueries({ queryKey: ["plans"] });
      // auto_generate=sample：C2-4（样章确认）在 PlanEditorPage 支持该参数前，创建后不自动生成；依赖记录见 TASKS.md
      navigate(`/plans/${data.id}/edit?auto_generate=sample${queryEnterpriseId ? `&enterprise_id=${queryEnterpriseId}` : ""}`);
    },
    onError: () => message.error("创建失败"),
  });

  const curEnterprise = enterprise;
  const defaultTitle = curEnterprise && planType
    ? `${curEnterprise.name}-${PLAN_TYPE_LABELS[planType]}`
    : "";

  const steps = [
    { title: "选择类型" },
    { title: "确认信息" },
  ];

  return (
    <div style={{ maxWidth: 720 }}>
      <PageHeader
        title="新建预案"
        onBack={() => navigate(queryEnterpriseId ? `/enterprises/${queryEnterpriseId}/plans` : "/plans")}
      />
      <Steps current={currentStep} items={steps} style={{ marginBottom: 32 }} />

      {currentStep === 0 && (
        <div>
          <Title level={5}>选择预案类型</Title>
          <Space orientation="vertical" style={{ width: "100%" }}>
            {(["comprehensive", "special", "onsite"] as PlanType[]).map((type) => (
              <Card
                key={type}
                hoverable
                onClick={() => setPlanType(type)}
                style={{
                  border: planType === type ? "2px solid #1677ff" : "1px solid #d9d9d9",
                }}
              >
                <PlanTypeTag type={type} />
                <Text strong style={{ marginLeft: 8 }}>{PLAN_TYPE_LABELS[type]}</Text>
                <br />
                <Text type="secondary" style={{ fontSize: 13 }}>
                  {type === "comprehensive" && "企业整体应急框架，适用所有事故类型"}
                  {type === "special" && "针对特定事故类型制定专项应对方案"}
                  {type === "onsite" && "一线操作卡片，直接指导现场人员"}
                </Text>
              </Card>
            ))}
          </Space>
          <Button
            type="primary"
            disabled={!planType}
            onClick={() => setCurrentStep(1)}
            style={{ marginTop: 16 }}
          >
            下一步
          </Button>
        </div>
      )}

      {currentStep === 1 && (
        <div>
          <Title level={5}>确认信息</Title>
          <Descriptions column={1} style={{ marginBottom: 16 }}>
            <Descriptions.Item label="企业">{curEnterprise?.name || "-"}</Descriptions.Item>
            <Descriptions.Item label="预案类型">
              {planType ? PLAN_TYPE_LABELS[planType] : "-"}
            </Descriptions.Item>
          </Descriptions>
          <Input
            size="large"
            placeholder="预案标题"
            value={title || defaultTitle}
            onChange={(e) => setTitle(e.target.value)}
            style={{ marginBottom: 16 }}
          />
          <Text type="secondary">事故类型</Text>
          <Select
            style={{ width: "100%" }}
            placeholder="选择事故类型（可留空）"
            allowClear
            value={accidentType || undefined}
            onChange={setAccidentType}
            options={[
              "火灾", "爆炸", "触电", "中毒窒息", "机械伤害",
              "高处坠落", "物体打击", "车辆伤害", "淹溺", "坍塌",
            ].map((t) => ({ value: t, label: t }))}
          />
          <Space style={{ marginTop: 16 }}>
            <Button onClick={() => setCurrentStep(0)}>上一步</Button>
            <Button
              type="primary"
              loading={mutation.isPending}
              disabled={!effectiveEnterpriseId || !planType || !(title || defaultTitle)}
              onClick={() => {
                mutation.mutate({
                  enterprise_id: effectiveEnterpriseId!,
                  plan_type: planType!,
                  title: title || defaultTitle,
                  accident_type: accidentType || null,
                });
              }}
            >
              创建
            </Button>
          </Space>
        </div>
      )}
    </div>
  );
}
