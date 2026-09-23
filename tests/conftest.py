import os, tempfile
# Configure before any app module is imported (settings, engine and sandbox root are read at import time).
_tmp = tempfile.mkdtemp(prefix="harness-test-")
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_tmp}/test.db"
os.environ["SANDBOX_ROOT"] = os.path.join(_tmp, "workspace")
os.makedirs(os.environ["SANDBOX_ROOT"], exist_ok=True)
