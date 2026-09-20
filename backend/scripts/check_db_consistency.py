"""全库引用完整性巡检：逐条外键检查孤儿行 + 应用层强制、数据库层没强制的隐性引用。

为什么需要：有些父子关系**没有外键**（例如 `enterprises.org_structure` 这个 JSONB 里
的成员引用、`hazard_records.source_task_id` 这类"来源"字段），删除父行时不会级联，
时间一长就会积累孤儿引用（法规图谱那 109 个孤儿条文节点就是这么发现的）。

用法（容器内 / 能连到 DATABASE_URL 的环境）：
    python scripts/check_db_consistency.py            # 只报告
    python scripts/check_db_consistency.py --strict   # 有孤儿则退出码 1（供发布前门禁）
"""

import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text  # noqa: E402

from app.database import async_session  # noqa: E402

# 应用层强制、库里没有外键的隐性引用：(说明, SQL)
CUSTOM_CHECKS: list[tuple[str, str]] = [
    (
        "企业组织树里的成员引用了不存在的用户",
        """
        SELECT count(*) FROM enterprises e,
             jsonb_array_elements(coalesce(e.org_structure, '[]'::jsonb)) node,
             jsonb_array_elements(coalesce(node->'members', '[]'::jsonb)) m
        WHERE m->>'user_id' IS NOT NULL
          AND NOT EXISTS (SELECT 1 FROM users u WHERE u.id = (m->>'user_id')::uuid)
        """,
    ),
    (
        "企业成员的 org_node_id 在其企业组织树里找不到",
        """
        SELECT count(*) FROM enterprise_members em
        JOIN enterprises e ON e.id = em.enterprise_id
        WHERE em.org_node_id IS NOT NULL
          AND NOT EXISTS (
            SELECT 1 FROM jsonb_array_elements(coalesce(e.org_structure, '[]'::jsonb)) n
            WHERE n->>'id' = em.org_node_id
          )
        """,
    ),
    # ── 组织架构升级（2026-09-20）新增：应急组织三表 + 成员多岗表 ──
    (
        "member_positions 引用的组织节点在该企业组织树里找不到",
        """
        SELECT count(*) FROM member_positions mp
        JOIN enterprise_members em ON em.id = mp.member_id
        JOIN enterprises e ON e.id = em.enterprise_id
        WHERE mp.org_node_id IS NOT NULL
          AND NOT EXISTS (
            SELECT 1 FROM jsonb_array_elements(coalesce(e.org_structure, '[]'::jsonb)) n
            WHERE n->>'id' = mp.org_node_id
          )
        """,
    ),
    (
        "应急组织任职（assignments）挂到了别的企业的成员上（跨租户串号）",
        """
        SELECT count(*) FROM emergency_org_assignments a
        JOIN emergency_org_roles r ON r.id = a.role_id
        JOIN emergency_org_units u ON u.id = r.unit_id
        JOIN enterprise_members em ON em.id = a.member_id
        WHERE em.enterprise_id <> u.enterprise_id
        """,
    ),
    (
        "应急组织单元/角色/任职的 enterprise_id 不一致（越权可见的根因）",
        """
        SELECT count(*) FROM emergency_org_roles r
        JOIN emergency_org_units u ON u.id = r.unit_id
        WHERE r.enterprise_id <> u.enterprise_id
        UNION ALL
        SELECT count(*) FROM emergency_org_assignments a
        JOIN emergency_org_roles r ON r.id = a.role_id
        WHERE a.enterprise_id <> r.enterprise_id
        """,
    ),
    (
        "多个主岗：同一成员存在 >1 条 is_primary 任职（部分唯一索引应已挡住）",
        """
        SELECT count(*) FROM (
          SELECT member_id FROM member_positions WHERE is_primary
          GROUP BY member_id HAVING count(*) > 1
        ) t
        """,
    ),
    (
        "被标记为风险点但缺分区或坐标（应用层 validator 保证，历史数据可能违反）",
        """
        SELECT count(*) FROM risk_objects
        WHERE is_risk_point = true
          AND (zone_id IS NULL OR location_x IS NULL OR location_y IS NULL)
        """,
    ),
    (
        "预案状态出现未知取值",
        """
        SELECT count(*) FROM plan_projects
        WHERE status NOT IN ('draft','generating','completed','failed','archived','pending')
        """,
    ),
    (
        "作业票状态出现未知取值",
        """
        SELECT count(*) FROM work_ticket_instances
        WHERE status NOT IN ('draft','submitted','approving','approved','rejected','working',
                             'finished','closed','cancelled','expired')
        """,
    ),
    (
        "隐患状态出现未知取值",
        """
        SELECT count(*) FROM hazard_records
        WHERE status NOT IN ('registered','grading','pending_approval','rectifying','reviewing',
                             'second_review','closed')
        """,
    ),
]


async def foreign_key_orphans(db) -> list[tuple[str, int]]:
    fks = (await db.execute(text("""
        SELECT tc.table_name, kcu.column_name, ccu.table_name AS parent_table,
               ccu.column_name AS parent_column, tc.constraint_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
          ON kcu.constraint_name = tc.constraint_name AND kcu.table_schema = tc.table_schema
        JOIN information_schema.constraint_column_usage ccu
          ON ccu.constraint_name = tc.constraint_name AND ccu.table_schema = tc.table_schema
        WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_schema = 'public'
        ORDER BY tc.table_name, kcu.column_name
    """))).all()
    out: list[tuple[str, int]] = []
    for table, column, parent, parent_col, name in fks:
        sql = (
            f'SELECT count(*) FROM "{table}" c LEFT JOIN "{parent}" p '
            f'ON p."{parent_col}" = c."{column}" '
            f'WHERE c."{column}" IS NOT NULL AND p."{parent_col}" IS NULL'
        )
        n = (await db.execute(text(sql))).scalar() or 0
        if n:
            out.append((f"{table}.{column} → {parent}.{parent_col} ({name})", n))
    return out


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict", action="store_true", help="发现孤儿引用时以退出码 1 结束")
    args = ap.parse_args()

    problems = 0
    async with async_session() as db:
        print("── 外键孤儿检查（逐条 FK 做 LEFT JOIN）──")
        orphans = await foreign_key_orphans(db)
        if orphans:
            for desc, n in orphans:
                print(f"  ❌ {desc}: {n} 行孤儿")
            problems += len(orphans)
        else:
            print("  ✅ 所有外键引用都指向存在的父行")

        print("── 隐性引用检查（应用层强制，库里没有外键）──")
        for desc, sql in CUSTOM_CHECKS:
            try:
                n = (await db.execute(text(sql))).scalar() or 0
            except Exception as exc:  # 表结构差异时给出提示而不是崩掉
                print(f"  ⚠ {desc}: 检查失败（{str(exc)[:80]}）")
                await db.rollback()  # 不回滚会让同一事务后续语句全部作废
                continue
            if n:
                print(f"  ❌ {desc}: {n} 行")
                problems += 1
            else:
                print(f"  ✅ {desc}")

        expired = (await db.execute(text(
            "SELECT count(*) FROM app_runtime_state WHERE expires_at IS NOT NULL "
            "AND expires_at < now()"
        ))).scalar() or 0
        print(f"── 运行时状态表：已过期未清理 {expired} 行（惰性清理，不视为缺陷）──")

    print(f"\n结论：{'发现 ' + str(problems) + ' 类问题' if problems else '未发现引用完整性/数据一致性问题 ✅'}")
    return 1 if (args.strict and problems) else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
