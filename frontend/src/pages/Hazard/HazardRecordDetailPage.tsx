import { useMemo, useState, type ReactNode } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  App as AntApp,
  Button,
  Card,
  Descriptions,
  Divider,
  Form,
  Image,
  Input,
  Modal,
  Popconfirm,
  Radio,
  Result,
  Select,
  Space,
  Spin,
  Tag,
  Timeline,
  Typography,
  Upload,
} from "antd";
import type { UploadProps } from "antd";
import { PlusOutlined, RobotOutlined } from "@ant-design/icons";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import {
  aiGradeHazard,
  aiGovernancePlan,
  approveRecord,
  closeRecord,
  getRecord,
  gradeRecord,
  rectifyRecord,
  rejectRecord,
  reviewRecord,
} from "@/services/hazardService";
import { listMembers } from "@/services/enterpriseOrgService";
import { uploadFile } from "@/services/enterpriseService";
import { useAuth } from "@/contexts/AuthContext";
import type { HazardRecordDetail, HazardStatus } from "@/types/hazard";
import { PageHeader } from "@/components/common/PageHeader";

const STATUS_LABELS: Record<HazardStatus, string> = {
  registered: "已登记",
  grading: "待分级",
  pending_approval: "待审批",
  rectifying: "整改中",
  reviewing: "复查中",
  second_review: "二次复核",
  closed: "已销号",
};

const STATUS_COLORS: Record<HazardStatus, string> = {
  registered: "default",
  grading: "orange",
  pending_approval: "gold",
  rectifying: "blue",
  reviewing: "cyan",
  second_review: "purple",
  closed: "green",
};

const LEVEL_LABELS: Record<string, string> = {
  major: "重大",
  general: "一般",
};

const LEVEL_OPTIONS = [
  { value: "major", label: "重大" },
  { value: "general", label: "一般" },
];

// 与数据字典 hazard_type 系统种子码值一致（db_migration_data_dicts.sql）
const HAZARD_TYPE_LABELS: Record<string, string> = {
  equipment: "设备设施",
  fire: "消防",
  behavior: "作业行为",
  management: "管理缺陷",
  environment: "环境",
  other: "其他",
};

const HAZARD_TYPE_OPTIONS = Object.entries(HAZARD_TYPE_LABELS).map(([value, label]) => ({
  value,
  label,
}));

/** 治理方案五键（与后端 PLAN_KEYS 一致）：goal/measures/budget/emergency_measures/acceptance_criteria。 */
const PLAN_FIELDS: Array<{ key: keyof GradePlan; label: string }> = [
  { key: "goal", label: "治理目标" },
  { key: "measures", label: "治理措施" },
  { key: "budget", label: "资金预算" },
  { key: "emergency_measures", label: "应急处置措施" },
  { key: "acceptance_criteria", label: "验收标准" },
];

/** 审计日志动作中文文案（与后端状态机写库 action 对应）。 */
const AUDIT_ACTION_LABELS: Record<string, string> = {
  grade: "分级确认",
  approve: "挂牌审批通过",
  reject: "挂牌驳回",
  rectify: "提交整改",
  review: "复查判定",
  close: "销号",
};

interface GradePlan {
  goal?: string;
  measures?: string;
  budget?: string;
  emergency_measures?: string;
  acceptance_criteria?: string;
}

interface GradeFormValues {
  level: "major" | "general";
  hazard_type?: string;
  grading_basis?: string;
  rectification_user_id?: string;
  rectification_plan?: GradePlan;
}

interface RectifyFormValues {
  content: string;
  evidence?: string[];
  reviewer_user_id: string;
}

interface ReviewFormValues {
  result: "pass" | "fail";
  comment?: string;
  evidence?: string[];
}

/** 详情页支持的状态机动作（按钮可见性由 canShowAction 按状态 + 身份判定）。 */
type RecordAction = "grade" | "approve" | "reject" | "rectify" | "review" | "close";

interface ActionContext {
  currentUserId: string;
  isAdmin: boolean;
}

function extractDetail(err: unknown): string {
  if (axios.isAxiosError(err)) {
    const detail = (err.response?.data as { detail?: unknown } | undefined)?.detail;
    if (typeof detail === "string" && detail) return detail;
    return err.message;
  }
  return err instanceof Error ? err.message : "";
}

function formatDateTime(value: string | null): string {
  if (!value) return "—";
  return value.replace("T", " ").slice(0, 16);
}

/**
 * 按钮可见性矩阵（§15 + 后端状态机 TRANSITIONS/ROLE_GATE 对齐）：
 * - grade：registered/grading 且企业主或启用管理员；
 * - approve/reject：pending_approval 且企业主或启用管理员；
 * - rectify：rectifying 且当前用户=整改责任人（或企业主/管理员）；
 * - review：reviewing/second_review 且当前用户=复查人（或企业主/管理员）；
 * - close：reviewing/second_review 且企业主或启用管理员。
 */
function canShowAction(record: HazardRecordDetail, action: RecordAction, ctx: ActionContext): boolean {
  const { currentUserId, isAdmin } = ctx;
  switch (action) {
    case "grade":
      return (record.status === "registered" || record.status === "grading") && isAdmin;
    case "approve":
    case "reject":
      return record.status === "pending_approval" && isAdmin;
    case "rectify":
      return record.status === "rectifying" && (isAdmin || record.rectification_user_id === currentUserId);
    case "review":
      return (
        (record.status === "reviewing" || record.status === "second_review") &&
        (isAdmin || record.reviewer_user_id === currentUserId)
      );
    case "close":
      return (record.status === "reviewing" || record.status === "second_review") && isAdmin;
  }
}

interface TimelineEntry {
  key: string;
  time: string;
  title: string;
  color?: string;
  content?: ReactNode;
}

function PhotoStrip({ urls }: { urls: string[] }) {
  if (!urls?.length) return null;
  return (
    <Image.PreviewGroup>
      <Space wrap>
        {urls.map(url => (
          <Image
            key={url}
            src={url}
            width={56}
            height={56}
            style={{ objectFit: "cover", borderRadius: 4 }}
          />
        ))}
      </Space>
    </Image.PreviewGroup>
  );
}

/** 证据照片上传（Form 受控组件，复用任务页 ItemPhotoUpload 惯例）。 */
function EvidenceUpload({ value = [], onChange }: { value?: string[]; onChange?: (urls: string[]) => void }) {
  const uploadProps: UploadProps = {
    multiple: true,
    customRequest: ({ file, onSuccess, onError }) => {
      void uploadFile(file as File)
        .then(url => {
          onChange?.([...value, url]);
          onSuccess?.(url);
        })
        .catch(e => onError?.(e as Error));
    },
    onRemove: file => {
      onChange?.(value.filter(u => u !== file.uid));
      return true;
    },
    fileList: value.map(url => ({
      uid: url,
      name: decodeURIComponent(url.split("/").pop() || "photo"),
      status: "done" as const,
      url,
    })),
  };
  return (
    <Upload {...uploadProps} accept="image/*">
      <Button size="small" icon={<PlusOutlined />}>
        上传照片
      </Button>
    </Upload>
  );
}

/**
 * 时间线构造（§15）：audit_logs + rectifications/reviews/approvals 合并，
 * 按 created_at 升序渲染，动作映射中文文案。
 */
function buildTimeline(
  record: HazardRecordDetail,
  memberNameMap: Record<string, string>,
): TimelineEntry[] {
  const entries: TimelineEntry[] = [];
  for (const log of record.audit_logs) {
    const detail = (log.detail || {}) as Record<string, unknown>;
    const actor = log.user_id ? memberNameMap[log.user_id] || "—" : "系统";
    const flow =
      detail.from && detail.to
        ? `状态：${STATUS_LABELS[String(detail.from) as HazardStatus] || String(detail.from)} → ${STATUS_LABELS[String(detail.to) as HazardStatus] || String(detail.to)}`
        : null;
    entries.push({
      key: `audit-${log.id}`,
      time: log.created_at,
      title: AUDIT_ACTION_LABELS[log.action] || log.action,
      content: (
        <div>
          <div>
            操作人：{actor}
            {flow ? `；${flow}` : ""}
          </div>
        </div>
      ),
    });
  }
  for (const rect of record.rectifications) {
    entries.push({
      key: `rect-${rect.id}`,
      time: rect.created_at,
      title: "提交整改",
      color: "orange",
      content: (
        <div>
          <div>{rect.content}</div>
          <PhotoStrip urls={rect.evidence || []} />
        </div>
      ),
    });
  }
  for (const review of record.reviews) {
    const passed = review.result === "pass";
    const title =
      review.review_type === "close"
        ? "销号"
        : review.review_type === "second_review"
          ? "二次复核"
          : "复查";
    entries.push({
      key: `review-${review.id}`,
      time: review.created_at,
      title,
      color: passed ? "green" : "red",
      content: (
        <div>
          <div>
            结果：{passed ? "通过" : "不通过"}
            {review.comment ? `；意见：${review.comment}` : ""}
          </div>
          <PhotoStrip urls={review.evidence || []} />
        </div>
      ),
    });
  }
  for (const approval of record.approvals) {
    entries.push({
      key: `approval-${approval.id}`,
      time: approval.created_at,
      title: approval.action === "approve" ? "挂牌审批通过" : "挂牌驳回",
      color: approval.action === "approve" ? "green" : "red",
      content: approval.comment ? <div>审批意见：{approval.comment}</div> : null,
    });
  }
  return entries.sort((a, b) => a.time.localeCompare(b.time) || a.key.localeCompare(b.key));
}

/** 隐患单详情页（§15）：基本信息 + 治理方案 + 时间线 + 按角色/状态显示的状态机操作。 */
export default function HazardRecordDetailPage() {
  const { id: enterpriseId = "", rid = "" } = useParams<{ id: string; rid: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { message } = AntApp.useApp();
  const { user } = useAuth();
  const backTarget = `/enterprises/${enterpriseId}/hazard`;

  const [gradeOpen, setGradeOpen] = useState(false);
  const [approveOpen, setApproveOpen] = useState(false);
  const [rejectOpen, setRejectOpen] = useState(false);
  const [rectifyOpen, setRectifyOpen] = useState(false);
  const [reviewOpen, setReviewOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [aiGradeLoading, setAiGradeLoading] = useState(false);
  const [aiPlanLoading, setAiPlanLoading] = useState(false);
  const [aiAppliedLevel, setAiAppliedLevel] = useState<string | null>(null);
  const [gradeForm] = Form.useForm<GradeFormValues>();
  const [approveForm] = Form.useForm<{ comment?: string; rectification_user_id?: string }>();
  const [rejectForm] = Form.useForm<{ comment?: string }>();
  const [rectifyForm] = Form.useForm<RectifyFormValues>();
  const [reviewForm] = Form.useForm<ReviewFormValues>();

  const {
    data: record,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ["hazard-record-detail", enterpriseId, rid],
    queryFn: () => getRecord(enterpriseId, rid),
    enabled: !!enterpriseId && !!rid,
  });
  const {
    data: members = [],
    isLoading: membersLoading,
  } = useQuery({
    queryKey: ["enterprise-members", enterpriseId],
    queryFn: () => listMembers(enterpriseId),
    enabled: !!enterpriseId,
  });

  const gradeLevel = Form.useWatch("level", gradeForm);
  const gradeIsMajor = gradeLevel === "major";

  const currentUserId = user?.id || "";
  const memberNameMap = useMemo(
    () => Object.fromEntries(members.map(m => [m.user_id, m.name || m.email || m.user_id])),
    [members],
  );
  const memberOptions = useMemo(
    () =>
      members
        .filter(m => m.enabled)
        .map(m => ({ value: m.user_id, label: m.name || m.email || m.user_id })),
    [members],
  );
  const reviewerOptions = useMemo(
    () => memberOptions.filter(o => o.value !== record?.rectification_user_id),
    [memberOptions, record?.rectification_user_id],
  );
  // 详情页访问者必为企业主或启用成员（后端 _get_ent），启用成员必有 enterprise_members 行：
  // 成员列表找不到当前用户 → 企业主；否则按成员行 role=enabled 的 enterprise_admin 判定。
  const currentMember = useMemo(
    () => members.find(m => m.user_id === currentUserId),
    [members, currentUserId],
  );
  const isAdmin = useMemo(
    () => !currentMember || (currentMember.role === "enterprise_admin" && currentMember.enabled),
    [currentMember],
  );

  const refreshDetail = () => {
    refetch();
    queryClient.invalidateQueries({ queryKey: ["hazard-records", enterpriseId] });
  };

  const openGrade = () => {
    if (!record) return;
    setAiAppliedLevel(null);
    gradeForm.setFieldsValue({
      level: record.level ?? undefined,
      hazard_type: record.hazard_type ?? undefined,
      grading_basis: record.grading_basis ?? undefined,
      rectification_user_id: record.rectification_user_id ?? undefined,
      rectification_plan: (record.rectification_plan as GradePlan | undefined) ?? undefined,
    });
    setGradeOpen(true);
  };

  const handleAiGrade = async () => {
    if (!record) return;
    setAiGradeLoading(true);
    try {
      const result = await aiGradeHazard(enterpriseId, { description: record.description });
      if (result.available && result.suggested_level) {
        gradeForm.setFieldsValue({ level: result.suggested_level, grading_basis: result.basis || "" });
        setAiAppliedLevel(result.suggested_level);
        message.success(
          `AI 建议等级：${LEVEL_LABELS[result.suggested_level] || result.suggested_level}（置信度 ${result.confidence ?? "—"}%），请核对后提交`,
        );
      } else {
        message.warning(result.note || "AI 暂不可用，请手动分级");
      }
    } catch (e) {
      message.error("获取 AI 分级建议失败: " + extractDetail(e));
    } finally {
      setAiGradeLoading(false);
    }
  };

  const handleAiPlan = async () => {
    if (!record) return;
    setAiPlanLoading(true);
    try {
      const result = await aiGovernancePlan(enterpriseId, { description: record.description });
      if (result.available && result.plan) {
        gradeForm.setFieldsValue({ rectification_plan: result.plan });
        message.success("AI 已生成治理方案草稿，请核对修改后提交");
      } else {
        message.warning(result.note || "AI 暂不可用，请手动填写治理方案");
      }
    } catch (e) {
      message.error("获取治理方案草稿失败: " + extractDetail(e));
    } finally {
      setAiPlanLoading(false);
    }
  };

  const handleGrade = async (values: GradeFormValues) => {
    setSubmitting(true);
    try {
      await gradeRecord(enterpriseId, rid, {
        level: values.level,
        grading_basis: (values.grading_basis || "").trim() || null,
        hazard_type: values.hazard_type || null,
        rectification_user_id: values.rectification_user_id || null,
        rectification_plan:
          values.level === "major"
            ? {
                goal: (values.rectification_plan?.goal || "").trim(),
                measures: (values.rectification_plan?.measures || "").trim(),
                budget: (values.rectification_plan?.budget || "").trim(),
                emergency_measures: (values.rectification_plan?.emergency_measures || "").trim(),
                acceptance_criteria: (values.rectification_plan?.acceptance_criteria || "").trim(),
              }
            : null,
        level_source: values.level === aiAppliedLevel ? "ai" : "manual",
      });
      message.success("分级确认成功");
      setGradeOpen(false);
      gradeForm.resetFields();
      refreshDetail();
    } catch (e) {
      message.error(extractDetail(e) || "分级确认失败，请稍后重试");
    } finally {
      setSubmitting(false);
    }
  };

  const handleApprove = async (values: { comment?: string; rectification_user_id?: string }) => {
    setSubmitting(true);
    try {
      await approveRecord(enterpriseId, rid, {
        comment: (values.comment || "").trim() || null,
        rectification_user_id: values.rectification_user_id || null,
      });
      message.success("挂牌审批已通过");
      setApproveOpen(false);
      approveForm.resetFields();
      refreshDetail();
    } catch (e) {
      message.error(extractDetail(e) || "审批失败，请稍后重试");
    } finally {
      setSubmitting(false);
    }
  };

  const handleReject = async (values: { comment?: string }) => {
    setSubmitting(true);
    try {
      await rejectRecord(enterpriseId, rid, { comment: (values.comment || "").trim() || null });
      message.success("已驳回，记录退回重新分级");
      setRejectOpen(false);
      rejectForm.resetFields();
      refreshDetail();
    } catch (e) {
      message.error(extractDetail(e) || "驳回失败，请稍后重试");
    } finally {
      setSubmitting(false);
    }
  };

  const handleRectify = async (values: RectifyFormValues) => {
    setSubmitting(true);
    try {
      await rectifyRecord(enterpriseId, rid, {
        content: values.content.trim(),
        evidence: values.evidence?.length ? values.evidence : undefined,
        reviewer_user_id: values.reviewer_user_id,
      });
      message.success("整改已提交，等待复查");
      setRectifyOpen(false);
      rectifyForm.resetFields();
      refreshDetail();
    } catch (e) {
      message.error(extractDetail(e) || "提交整改失败，请稍后重试");
    } finally {
      setSubmitting(false);
    }
  };

  const handleReview = async (values: ReviewFormValues) => {
    setSubmitting(true);
    try {
      await reviewRecord(enterpriseId, rid, {
        result: values.result,
        comment: (values.comment || "").trim() || null,
        evidence: values.evidence?.length ? values.evidence : undefined,
      });
      message.success(values.result === "pass" ? "复查通过" : "复查不通过，已退回整改");
      setReviewOpen(false);
      reviewForm.resetFields();
      refreshDetail();
    } catch (e) {
      message.error(extractDetail(e) || "复查失败，请稍后重试");
    } finally {
      setSubmitting(false);
    }
  };

  const handleClose = async () => {
    setSubmitting(true);
    try {
      await closeRecord(enterpriseId, rid);
      message.success("隐患已销号");
      refreshDetail();
    } catch (e) {
      message.error(extractDetail(e) || "销号失败，请稍后重试");
    } finally {
      setSubmitting(false);
    }
  };

  const actions = useMemo(() => {
    if (!record || !currentUserId) return [] as RecordAction[];
    const ctx: ActionContext = { currentUserId, isAdmin };
    return (["grade", "approve", "reject", "rectify", "review", "close"] as RecordAction[]).filter(a =>
      canShowAction(record, a, ctx),
    );
  }, [record, currentUserId, isAdmin]);

  const timeline = useMemo(
    () => (record ? buildTimeline(record, memberNameMap) : []),
    [record, memberNameMap],
  );

  const actionBar =
    record && !membersLoading ? (
      <Space wrap>
        {actions.includes("grade") && (
          <Button type="primary" onClick={openGrade}>
            分级确认
          </Button>
        )}
        {actions.includes("approve") && (
          <Button type="primary" onClick={() => setApproveOpen(true)}>
            审批通过
          </Button>
        )}
        {actions.includes("reject") && (
          <Button danger onClick={() => setRejectOpen(true)}>
            驳回
          </Button>
        )}
        {actions.includes("rectify") && (
          <Button type="primary" onClick={() => setRectifyOpen(true)}>
            提交整改
          </Button>
        )}
        {actions.includes("review") && (
          <Button type="primary" onClick={() => setReviewOpen(true)}>
            {record.status === "second_review" ? "二次复核" : "复查"}
          </Button>
        )}
        {actions.includes("close") && (
          <Popconfirm
            title="确认销号"
            description="销号后该隐患标记为已闭环，历史记录与时间线保留"
            okText="确认销号"
            cancelText="取消"
            okButtonProps={{ danger: true }}
            onConfirm={() => void handleClose()}
          >
            <Button danger>销号</Button>
          </Popconfirm>
        )}
      </Space>
    ) : undefined;

  if (isLoading) {
    return (
      <div style={{ textAlign: "center", paddingTop: 80 }}>
        <Spin size="large" />
      </div>
    );
  }
  if (isError || !record) {
    return (
      <div>
        <PageHeader title="隐患详情" onBack={() => navigate(backTarget)} />
        <Result
          status="warning"
          title="隐患单加载失败"
          subTitle={extractDetail(error) || "记录不存在或无权访问"}
          extra={
            <Space>
              <Button onClick={() => void refetch()}>重试</Button>
              <Button type="primary" onClick={() => navigate(backTarget)}>
                返回台账
              </Button>
            </Space>
          }
        />
      </div>
    );
  }

  const plan = record.rectification_plan as GradePlan | null;

  return (
    <div>
      <PageHeader
        title={`${record.code} ${record.title}`}
        subtitle={`状态：${record.status_label}`}
        onBack={() => navigate(backTarget)}
        extra={actionBar}
      />

      <Card title="基本信息" size="small" style={{ marginBottom: 16 }}>
        <Descriptions size="small" column={3}>
          <Descriptions.Item label="编号">{record.code}</Descriptions.Item>
          <Descriptions.Item label="等级">
            {record.level ? (
              <Tag color={record.level === "major" ? "red" : "blue"}>{record.level_label}</Tag>
            ) : (
              "—"
            )}
          </Descriptions.Item>
          <Descriptions.Item label="状态">
            <Tag color={STATUS_COLORS[record.status]}>{record.status_label}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="来源">{record.source_type_label}</Descriptions.Item>
          <Descriptions.Item label="隐患类型">
            {record.hazard_type ? HAZARD_TYPE_LABELS[record.hazard_type] || record.hazard_type : "—"}
          </Descriptions.Item>
          <Descriptions.Item label="位置">{record.location || "—"}</Descriptions.Item>
          <Descriptions.Item label="关联风险点">{record.object_name || "—"}</Descriptions.Item>
          <Descriptions.Item label="关联管控措施">{record.measure_name || "—"}</Descriptions.Item>
          <Descriptions.Item label="整改责任人">
            {record.rectification_user_id ? memberNameMap[record.rectification_user_id] || "—" : "—"}
          </Descriptions.Item>
          <Descriptions.Item label="复查人">
            {record.reviewer_user_id ? memberNameMap[record.reviewer_user_id] || "—" : "—"}
          </Descriptions.Item>
          <Descriptions.Item label="登记人">
            {record.created_by ? memberNameMap[record.created_by] || "—" : "—"}
          </Descriptions.Item>
          <Descriptions.Item label="整改期限">{formatDateTime(record.deadline)}</Descriptions.Item>
          <Descriptions.Item label="登记时间">{formatDateTime(record.created_at)}</Descriptions.Item>
          <Descriptions.Item label="销号时间">{formatDateTime(record.closed_at)}</Descriptions.Item>
          <Descriptions.Item label="隐患描述" span={3}>
            <Typography.Paragraph style={{ marginBottom: 0, whiteSpace: "pre-wrap" }}>
              {record.description || "—"}
            </Typography.Paragraph>
          </Descriptions.Item>
          {record.photo_urls?.length ? (
            <Descriptions.Item label="现场照片" span={3}>
              <PhotoStrip urls={record.photo_urls} />
            </Descriptions.Item>
          ) : null}
        </Descriptions>
      </Card>

      <Card title="治理方案" size="small" style={{ marginBottom: 16 }}>
        {plan ? (
          <Descriptions size="small" column={1}>
            {PLAN_FIELDS.map(f => (
              <Descriptions.Item key={f.key} label={f.label}>
                {String(plan[f.key] ?? "") || "—"}
              </Descriptions.Item>
            ))}
          </Descriptions>
        ) : (
          <Typography.Text type="secondary">未填写</Typography.Text>
        )}
      </Card>

      <Card title="处理时间线" size="small">
        {timeline.length ? (
          <Timeline
            items={timeline.map(e => ({
              key: e.key,
              color: e.color,
              children: (
                <div>
                  <Space>
                    <Typography.Text strong>{e.title}</Typography.Text>
                    <Typography.Text type="secondary">{formatDateTime(e.time)}</Typography.Text>
                  </Space>
                  {e.content ? <div style={{ marginTop: 4 }}>{e.content}</div> : null}
                </div>
              ),
            }))}
          />
        ) : (
          <Typography.Text type="secondary">暂无处理记录</Typography.Text>
        )}
      </Card>

      <Modal
        title="分级确认"
        open={gradeOpen}
        confirmLoading={submitting}
        okText="确认分级"
        width={680}
        onOk={() => gradeForm.submit()}
        onCancel={() => {
          setGradeOpen(false);
          gradeForm.resetFields();
        }}
        destroyOnClose
      >
        <Form
          form={gradeForm}
          layout="vertical"
          onFinish={values => void handleGrade(values)}
          style={{ marginTop: 12 }}
        >
          <Form.Item name="level" label="隐患等级" rules={[{ required: true, message: "请选择隐患等级" }]}>
            <Radio.Group options={LEVEL_OPTIONS} />
          </Form.Item>
          <Form.Item name="hazard_type" label="隐患类型">
            <Select allowClear options={HAZARD_TYPE_OPTIONS} placeholder="选择隐患类型（可选）" />
          </Form.Item>
          <Form.Item
            name="grading_basis"
            label="判定依据"
            rules={gradeIsMajor ? [{ required: true, message: "重大隐患须填写判定依据" }] : []}
          >
            <Input.TextArea rows={3} placeholder="依据重大隐患判定要点说明定级理由（参考提示，以现行有效判定标准为准）" />
          </Form.Item>
          <Form.Item>
            <Space wrap>
              <Button icon={<RobotOutlined />} loading={aiGradeLoading} onClick={() => void handleAiGrade()}>
                AI 分级建议
              </Button>
              <Button icon={<RobotOutlined />} loading={aiPlanLoading} onClick={() => void handleAiPlan()}>
                AI 治理方案草稿
              </Button>
            </Space>
          </Form.Item>
          <Form.Item name="rectification_user_id" label="整改责任人">
            <Select allowClear options={memberOptions} placeholder="选择整改责任人（可选）" />
          </Form.Item>
          {gradeIsMajor && (
            <>
              <Divider plain>治理方案（重大隐患必填）</Divider>
              {PLAN_FIELDS.map(f => (
                <Form.Item
                  key={f.key}
                  name={["rectification_plan", f.key]}
                  label={f.label}
                  rules={[{ required: true, message: `请填写${f.label}` }]}
                >
                  <Input.TextArea rows={f.key === "measures" ? 4 : 2} placeholder={`${f.label}（重大隐患必填）`} />
                </Form.Item>
              ))}
            </>
          )}
        </Form>
      </Modal>

      <Modal
        title="挂牌审批通过"
        open={approveOpen}
        confirmLoading={submitting}
        okText="审批通过"
        onOk={() => approveForm.submit()}
        onCancel={() => {
          setApproveOpen(false);
          approveForm.resetFields();
        }}
        destroyOnClose
      >
        <Form
          form={approveForm}
          layout="vertical"
          onFinish={values => void handleApprove(values)}
          style={{ marginTop: 12 }}
        >
          <Form.Item name="rectification_user_id" label="整改责任人">
            <Select allowClear options={memberOptions} placeholder="指定整改责任人（可选）" />
          </Form.Item>
          <Form.Item name="comment" label="审批意见">
            <Input.TextArea rows={3} placeholder="审批意见（可选）" />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="挂牌驳回"
        open={rejectOpen}
        confirmLoading={submitting}
        okText="确认驳回"
        onOk={() => rejectForm.submit()}
        onCancel={() => {
          setRejectOpen(false);
          rejectForm.resetFields();
        }}
        destroyOnClose
      >
        <Form
          form={rejectForm}
          layout="vertical"
          onFinish={values => void handleReject(values)}
          style={{ marginTop: 12 }}
        >
          <Form.Item name="comment" label="驳回意见">
            <Input.TextArea rows={3} placeholder="驳回意见（可选），记录将退回重新分级" />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="提交整改"
        open={rectifyOpen}
        confirmLoading={submitting}
        okText="提交整改"
        onOk={() => rectifyForm.submit()}
        onCancel={() => {
          setRectifyOpen(false);
          rectifyForm.resetFields();
        }}
        destroyOnClose
      >
        <Form
          form={rectifyForm}
          layout="vertical"
          onFinish={values => void handleRectify(values)}
          style={{ marginTop: 12 }}
        >
          <Form.Item name="content" label="整改内容" rules={[{ required: true, message: "请填写整改内容" }]}>
            <Input.TextArea rows={4} placeholder="描述整改措施与完成情况" />
          </Form.Item>
          <Form.Item name="evidence" label="整改证据照片">
            <EvidenceUpload />
          </Form.Item>
          <Form.Item
            name="reviewer_user_id"
            label="指定复查人"
            rules={[{ required: true, message: "请指定复查人" }]}
          >
            <Select options={reviewerOptions} placeholder="选择复查人（不能是整改人本人）" />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={record.status === "second_review" ? "二次复核" : "复查"}
        open={reviewOpen}
        confirmLoading={submitting}
        okText="提交复查结果"
        onOk={() => reviewForm.submit()}
        onCancel={() => {
          setReviewOpen(false);
          reviewForm.resetFields();
        }}
        destroyOnClose
      >
        <Form
          form={reviewForm}
          layout="vertical"
          onFinish={values => void handleReview(values)}
          style={{ marginTop: 12 }}
        >
          <Form.Item name="result" label="复查结果" rules={[{ required: true, message: "请选择复查结果" }]}>
            <Radio.Group
              options={[
                { value: "pass", label: "通过" },
                { value: "fail", label: "不通过（退回整改）" },
              ]}
            />
          </Form.Item>
          <Form.Item name="comment" label="复查意见">
            <Input.TextArea rows={3} placeholder="复查意见（可选）" />
          </Form.Item>
          <Form.Item name="evidence" label="复查证据照片">
            <EvidenceUpload />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
