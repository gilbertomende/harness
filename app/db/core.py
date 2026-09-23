from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import text
from app.config import settings
from app.db.models import Base

engine = create_async_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

async def init_db():
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
        # Additive columns for databases created by earlier v0.2 builds (bridge until Alembic, ROADMAP v0.3).
        await conn.execute(text("ALTER TABLE mcp_servers ADD COLUMN IF NOT EXISTS read_only_tools JSON NOT NULL DEFAULT '[]'"))
