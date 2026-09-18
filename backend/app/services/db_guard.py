"""长耗时外部调用（LLM/第三方）前，把请求级数据库连接还给连接池。

为什么需要（2026-09-19 压测实测）：请求级会话一旦执行过 SELECT 就会开事务并**一直占着
连接**。若紧接着 `await` 一个 6~180 秒的 LLM 调用，这条连接在整个推理期间都是
`idle in transaction`。压测（24 个并发聊天，每次推理 6s）结果：
    连接峰值 = pool_size(5)+max_overflow(10) = 15（**单 worker 上限**），
    15 个请求成功、9 个在等 30s 后 500，连"打开预案列表"这种只读请求也被拖到 30s 后失败。

安全前提（很重要）：只在该会话**没有任何未提交写入**时调用。
`Session.close()` 会把已加载对象 expunge 出会话，此后对它们赋的新值不会被 commit——
所以"先读、再改、最后 commit"的写法必须在改之前调用本函数，而不能在改之后。
"""
import logging

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def release_request_connection(db: AsyncSession) -> bool:
    """结束当前事务、把连接还给连接池；会话之后仍可继续使用（会自动开新事务）。

    Returns:
        True 表示确实释放了（当时有活动事务），False 表示本来就没占连接或未释放。
    """
    if not db.in_transaction():
        return False
    # 有未提交写入时不动它：close() 会丢弃这些改动，宁可不释放也不能悄悄丢数据。
    if db.new or db.dirty or db.deleted:
        logger.warning(
            "会话存在未提交改动（new=%d dirty=%d deleted=%d），跳过连接释放，"
            "以免丢弃写入；请把 LLM 调用移到写操作之前。",
            len(db.new), len(db.dirty), len(db.deleted),
        )
        return False
    await db.close()
    return True
