from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class EnterpriseDataMark(Base):
    """企业维度「某数据域最后变更时间」标记（D-3）。

    依赖表的时间戳能覆盖新增/修改，但**删除子行不会留下痕迹**（如删掉一条风险事件），
    因此删除类端点额外调用 mark_data_changed 打点。
    """

    __tablename__ = "enterprise_data_marks"

    enterprise_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("enterprises.id", ondelete="CASCADE"),
        primary_key=True,
    )
    domain: Mapped[str] = mapped_column(String(50), primary_key=True)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=func.now()
    )
