from typing import AsyncGenerator
from sqlmodel import SQLModel
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# 数据库配置
DATABASE_URL = "sqlite+aiosqlite:///database.db"

# 创建异步引擎
engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    future=True,
)

# 创建异步会话
async_session = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

async def init_db():
    """初始化数据库"""
    async with engine.begin() as conn:
        # 如果表不存在则创建
        await conn.run_sync(SQLModel.metadata.create_all)

async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """获取数据库会话"""
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close() 