"""
数据库连接管理
支持 SQLite（开发）和 PostgreSQL（生产）
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from core.config import Settings, get_settings
from storage.models import Base

logger = structlog.get_logger(__name__)


class Database:
    """数据库管理器"""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self._engine: AsyncEngine | None = None
        self._session_factory: async_sessionmaker[AsyncSession] | None = None

    @property
    def engine(self) -> AsyncEngine:
        if self._engine is None:
            raise RuntimeError("Database not initialized. Call init() first.")
        return self._engine

    @property
    def session_factory(self) -> async_sessionmaker[AsyncSession]:
        if self._session_factory is None:
            raise RuntimeError("Database not initialized. Call init() first.")
        return self._session_factory

    def _get_engine_config(self) -> dict:
        """根据数据库类型返回引擎配置"""
        url = self.settings.database_url

        if url.startswith("sqlite"):
            # SQLite 配置
            return {
                "echo": self.settings.debug,
                "poolclass": StaticPool,
                "connect_args": {"check_same_thread": False},
            }
        else:
            # PostgreSQL 配置
            return {
                "echo": self.settings.debug,
                "pool_size": 5,
                "max_overflow": 10,
                "pool_pre_ping": True,
                "pool_recycle": 3600,
            }

    async def init(self) -> None:
        """初始化数据库连接"""
        if self._engine is not None:
            logger.warning("Database already initialized")
            return

        url = self.settings.database_url
        config = self._get_engine_config()

        logger.info("Initializing database", url=url.split("@")[-1] if "@" in url else url)

        self._engine = create_async_engine(url, **config)

        # 创建会话工厂
        self._session_factory = async_sessionmaker(
            bind=self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )

        # 创建表
        await self.create_tables()

        logger.info("Database initialized successfully")

    async def create_tables(self) -> None:
        """创建所有表"""
        async with self.engine.begin() as conn:
            # 对于 SQLite，启用外键约束
            if self.settings.database_url.startswith("sqlite"):
                await conn.execute(text("PRAGMA foreign_keys=ON"))

            await conn.run_sync(Base.metadata.create_all)

        logger.debug("Database tables created/verified")

    async def drop_tables(self) -> None:
        """删除所有表（仅用于测试）"""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        logger.warning("All database tables dropped")

    async def close(self) -> None:
        """关闭数据库连接"""
        if self._engine is not None:
            await self._engine.dispose()
            self._engine = None
            self._session_factory = None
            logger.info("Database connection closed")

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """获取数据库会话的上下文管理器"""
        if self._session_factory is None:
            raise RuntimeError("Database not initialized")

        async with self._session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def execute_raw(self, sql: str, params: dict | None = None) -> any:
        """执行原始 SQL"""
        async with self.session() as session:
            result = await session.execute(text(sql), params or {})
            return result.fetchall()


# 全局单例
_db: Database | None = None


def get_database() -> Database:
    """获取数据库单例"""
    global _db
    if _db is None:
        _db = Database()
    return _db


async def init_database() -> Database:
    """初始化并返回数据库"""
    db = get_database()
    await db.init()
    return db


async def close_database() -> None:
    """关闭数据库连接"""
    global _db
    if _db is not None:
        await _db.close()
        _db = None
