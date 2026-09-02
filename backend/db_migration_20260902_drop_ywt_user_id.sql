-- 2026-09-02: 移除旧业务中台/PROTEGO 商城对接——删除 users 表的外部用户映射列
-- 背景：external.py 路由、HMAC 中间件、external_service 等已一并移除，
--       该列仅由外部接入 API（_ensure_user_and_enterprise）写入，无其他引用。
-- 幂等：DROP COLUMN IF EXISTS，空库（create_all 按新模型建表，无此列）与既有库均安全。
ALTER TABLE users DROP COLUMN IF EXISTS ywt_user_id;
