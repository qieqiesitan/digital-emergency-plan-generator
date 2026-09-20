/**
 * 「生成并复核」弹窗：把聊天里的 workflow 搬到预案页（同一个执行器与模板）。
 *
 * 流程：打开即启动 `plan_generate_review` → 轮询进度 → 停在「生成」门控等用户点确认
 *      （生成不可逆且耗时耗额度，必须显式确认）→ 完成后展示复核结果（issues/warnings）。
 * 轮询在关闭弹窗/完成后自动停止，避免空转。
 */
import { useEffect, useMemo, useRef, useState } from "react";
import { Alert, App as AntApp, Button, Modal, Space, Spin, Tag, Typography } from "antd";
import {
  confirmWorkflowStep, getWorkflowRun, startGenerateReview,
  type WorkflowRunState, type WorkflowStepState,
} from "@/services/workflowService";

const { Text, Paragraph } = Typography;

const STEP_LABEL: Record<string, string> = { generate: "生成正文", review: "质量复核" };
const STATUS_LABEL: Record<WorkflowStepState["status"], { text: string; color: string }> = {
  pending: { text: "待确认/待执行", color: "default" },
  running: { text: "执行中", color: "processing" },
  completed: { text: "已完成", color: "green" },
  confirmed: { text: "已确认", color: "blue" },
  failed: { text: "失败", color: "red" },
};

interface Props {
  open: boolean;
  onClose: () => void;
  planId: string;
  /** 工作流结束后刷新预案（章节内容/状态变了） */
  onFinished?: () => void;
}

export default function PlanGenerateReviewModal({ open, onClose, planId, onFinished }: Props) {
  const { message } = AntApp.useApp();
  const [run, setRun] = useState<WorkflowRunState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const timerRef = useRef<number | null>(null);
  const startedRef = useRef(false);

  // 打开时启动一次（父组件用 key 让本组件在每次打开时重新挂载，因此这里无需重置 state——
  // 仓库启用了 react-hooks/set-state-in-effect，effects 里不许直接 setState）
  useEffect(() => {
    if (!open) return;
    if (startedRef.current) return;
    startedRef.current = true;
    setStarting(true);
    startGenerateReview(planId)
      .then((state) => setRun(state))
      .catch((e) => setError(String((e as Error)?.message || e)))
      .finally(() => setStarting(false));
  }, [open, planId]);

  // 轮询：仅在"运行中/暂停"时继续
  useEffect(() => {
    if (!open || !run) return;
    const live = run.status === "running" || run.status === "pending";
    if (!live) {
      if (timerRef.current) window.clearInterval(timerRef.current);
      timerRef.current = null;
      return;
    }
    if (timerRef.current) return;
    timerRef.current = window.setInterval(() => {
      getWorkflowRun(run.run_id)
        .then((state) => {
          setRun(state);
          if (state.status === "completed" || state.status === "failed") onFinished?.();
        })
        .catch(() => undefined);
    }, 2500);
    return () => {
      if (timerRef.current) window.clearInterval(timerRef.current);
      timerRef.current = null;
    };
  }, [open, run, onFinished]);

  const reviewStep = useMemo(() => run?.steps.find((s) => s.step_name === "review"), [run]);
  const reviewSummary = useMemo(() => {
    const result = (reviewStep?.result || {}) as { issues?: unknown[]; warnings?: unknown[] };
    return { issues: result.issues?.length ?? 0, warnings: result.warnings?.length ?? 0 };
  }, [reviewStep]);

  const waitingStep = run?.status === "paused" ? run.current_step : null;

  const handleConfirm = async () => {
    if (!run || !waitingStep) return;
    setConfirming(true);
    try {
      setRun(await confirmWorkflowStep(run.run_id, waitingStep));
      message.success("已确认，开始生成（可在本窗口看进度）");
    } catch (e) {
      setError(String((e as Error)?.message || e));
    } finally {
      setConfirming(false);
    }
  };

  return (
    <Modal
      open={open}
      onCancel={onClose}
      width={620}
      title="生成并复核"
      footer={
        <Space>
          <Button onClick={onClose}>{run?.status === "completed" ? "关闭" : "取消"}</Button>
          {waitingStep && (
            <Button type="primary" loading={confirming} onClick={() => void handleConfirm()}>
              确认并开始生成
            </Button>
          )}
        </Space>
      }
      destroyOnHidden
    >
      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 12 }}
        title="生成 → 复核（两个步骤）"
        description="生成会覆盖各章节正文并消耗模型额度，因此需要你确认后才开始；复核只读，不会改内容。"
      />

      {starting && <div style={{ textAlign: "center", padding: 16 }}><Spin /> 正在启动…</div>}
      {error && <Alert type="error" showIcon title="工作流出错" description={error} />}

      {run && (
        <Space orientation="vertical" size={10} style={{ width: "100%" }}>
          <div>
            <Text type="secondary">状态：</Text>
            <Tag color={run.status === "failed" ? "red" : run.status === "completed" ? "green" : "blue"}>
              {run.status === "paused" ? "等待你确认" : run.status}
            </Tag>
            <Text type="secondary" style={{ fontSize: 12, marginLeft: 8 }}>run {run.run_id.slice(0, 8)}</Text>
          </div>
          {run.steps.map((s) => (
            <div key={s.step_name}>
              <Space size={8}>
                <Tag color={STATUS_LABEL[s.status]?.color ?? "default"}>
                  {STATUS_LABEL[s.status]?.text ?? s.status}
                </Tag>
                <Text strong>{STEP_LABEL[s.step_name] ?? s.step_name}</Text>
                {s.retry_count > 0 && <Text type="secondary" style={{ fontSize: 12 }}>重试 {s.retry_count} 次</Text>}
              </Space>
              {s.error && <Paragraph type="danger" style={{ margin: "4px 0 0", fontSize: 12 }}>{s.error}</Paragraph>}
            </div>
          ))}
          {reviewStep?.status === "completed" && (
            <Alert
              type={reviewSummary.issues > 0 ? "warning" : "success"}
              showIcon
              title={`复核完成：${reviewSummary.issues} 个问题 / ${reviewSummary.warnings} 条提示`}
              description="详细清单可点「取消」关掉本窗口后，用预案页的「AI 审查」查看逐条定位。"
            />
          )}
        </Space>
      )}
    </Modal>
  );
}
