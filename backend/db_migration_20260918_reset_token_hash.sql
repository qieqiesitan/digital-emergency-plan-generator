-- 找回令牌改存哈希（W2）。历史行是明文 token 且邮件从未真正发出（SMTP 未接入），
-- 无法反推哈希，直接作废：避免"明文令牌留在库里可被直接用来改密码"。

UPDATE password_reset_tokens
SET used_at = now()
WHERE used_at IS NULL;
