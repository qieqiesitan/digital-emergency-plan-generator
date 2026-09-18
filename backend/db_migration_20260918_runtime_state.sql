-- 跨 worker 共享运行时状态（W2 架构级）。
-- 背景：uvicorn 以 4 worker 运行，模块级 dict/set 在每个 worker 各一份，
-- 造成生成防重失效、停止信号不到达、登出黑名单/限流/nonce 失效等一整类问题。
-- 本表把它们收敛到 Postgres（公司环境零新增组件）。

CREATE TABLE IF NOT EXISTS app_runtime_state (
    key         VARCHAR(200) PRIMARY KEY,
    value       JSONB        NOT NULL DEFAULT '{}'::jsonb,
    expires_at  TIMESTAMPTZ,
    updated_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_app_runtime_state_expires_at
    ON app_runtime_state (expires_at);
