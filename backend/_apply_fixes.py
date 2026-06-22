import re

# Fix 1: generation.py - stuck status in generate_batch_background
gen_path = r'C:\Users\55061\Documents\数字化预案自动生成 2\backend\app\routers\generation.py'
with open(gen_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Fix 1a: Add logging import
if 'import logging' not in content:
    content = content.replace('import asyncio', 'import asyncio\nimport logging\nlogger = logging.getLogger(__name__)')

# Fix 1b: Replace stuck status check in generate_batch_background
old_check = '''if p.status == "generating": return {"code": 0, "message": "正在生成中"}'''
new_check = '''if p.status == "generating":
        if not _active_generations.get(plan_id):
            logger.warning(f"Plan {plan_id} status is generating but no active task — resetting to draft")
            p.status = "draft"
            await db.commit()
        else:
            return {"code": 0, "message": "正在生成中"}'''
content = content.replace(old_check, new_check)

# Fix 1c: Also reset status in /batch endpoint if stuck
old_batch_reset = '''p.status = "generating"
    await db.commit()
    _active_generations[plan_id] = True'''
new_batch_reset = '''# Reset stuck status if backend restarted while this plan was generating
    if p.status == "generating" and not _active_generations.get(plan_id):
        p.status = "draft"
        await db.commit()
    p.status = "generating"
    await db.commit()
    _active_generations[plan_id] = True'''
content = content.replace(old_batch_reset, new_batch_reset)

# Fix 1d: Better error logging in /batch/background background task
old_except_pass = '''except Exception:
            pass'''
new_except_log = '''except Exception as e:
            logger.error(f"Background batch generation failed: {e}")'''
content = content.replace(old_except_pass, new_except_log)

with open(gen_path, 'w', encoding='utf-8') as f:
    f.write(content)
print('generation.py: OK')

# Fix 2: enterprise.py - increase default max_tokens for reasoning models
ent_path = r'C:\Users\55061\Documents\数字化预案自动生成 2\backend\app\models\enterprise.py'
with open(ent_path, 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('max_tokens: Mapped[int] = mapped_column(Integer, default=4096)',
                          'max_tokens: Mapped[int] = mapped_column(Integer, default=16384)')

with open(ent_path, 'w', encoding='utf-8') as f:
    f.write(content)
print('enterprise.py: OK')

print('All backend fixes applied.')
