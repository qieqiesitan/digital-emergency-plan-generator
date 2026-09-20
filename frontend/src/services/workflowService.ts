/**
 * 端到端工作流（前端入口）。后端 `app/routers/workflows.py`，
 * 与聊天工具 `run_workflow` / `get_workflow_progress` / `confirm_workflow_step` 共用同一套执行器。
 */
import api from "./api";

export interface WorkflowStepState {
  step_name: string;
  status: "pending" | "running" | "completed" | "confirmed" | "failed";
  retry_count: number;
  error: string | null;
  /** review 步骤的结果是质检明细 {issues, warnings, ...} */
  result: Record<string, unknown> | null;
}

export interface WorkflowRunState {
  run_id: string;
  workflow_name: string;
  status: "pending" | "running" | "paused" | "failed" | "completed";
  current_step: string | null;
  params: Record<string, unknown>;
  steps: WorkflowStepState[];
}

/** 对已有预案启动「生成 → 复核」（会停在生成前确认门控） */
export async function startGenerateReview(planId: string): Promise<WorkflowRunState> {
  const res = await api.post(`/plans/${planId}/workflows/generate-review`, {}, { skipGlobalError: true });
  return res.data.data;
}

export async function getWorkflowRun(runId: string): Promise<WorkflowRunState> {
  const res = await api.get(`/workflows/${runId}`, { skipGlobalError: true });
  return res.data.data;
}

export async function confirmWorkflowStep(runId: string, stepName: string): Promise<WorkflowRunState> {
  const res = await api.post(`/workflows/${runId}/confirm/${stepName}`, {}, { skipGlobalError: true });
  return res.data.data;
}
