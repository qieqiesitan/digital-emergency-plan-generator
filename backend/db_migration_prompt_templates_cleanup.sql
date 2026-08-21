-- 提示词模板旧行下线：同 template_code 存在 active 行时，将旧 status='0' 行置为 'disabled'
-- 幂等：重复执行无新影响
UPDATE prompt_templates old
SET status = 'disabled'
WHERE old.status = '0'
  AND EXISTS (
    SELECT 1 FROM prompt_templates act
    WHERE act.template_code = old.template_code
      AND act.status = 'active'
  );
