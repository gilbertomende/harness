import os, tempfile
# Configure before any app module is imported (settings, engine and sandbox root are read at import time).
_tmp = tempfile.mkdtemp(prefix="harness-test-")
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_tmp}/test.db"
os.environ["SANDBOX_ROOT"] = os.path.join(_tmp, "workspace")
os.makedirs(os.environ["SANDBOX_ROOT"], exist_ok=True)

import asyncio, pytest

@pytest.fixture
def db():
    """Fresh schema on the SQLite test database."""
    from app.db.core import engine
    from app.db.models import Base
    async def reset():
        async with engine.begin() as c:
            await c.run_sync(Base.metadata.drop_all); await c.run_sync(Base.metadata.create_all)
    asyncio.run(reset())
