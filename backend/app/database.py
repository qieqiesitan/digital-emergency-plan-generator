from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from app.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    # W2：4 worker × (5+10) = 60，留出 Postgres max_connections=100 的安全余量
    # （原 4×(10+20)=120 会撞上限，压测实测 120 连接 50 次 too many clients）
    pool_size=5,
    max_overflow=10,
    # P2 #10：30 分钟回收陈旧连接 + 取用前探活，缓解 idle in transaction / 断连堆积
    pool_recycle=1800,
    pool_pre_ping=True,
)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

async def get_db() -> AsyncSession:
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()
