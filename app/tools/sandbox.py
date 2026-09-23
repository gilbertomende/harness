from pathlib import Path
import asyncio, shlex
from app.config import settings
from app.tools.registry import registry
ROOT = Path(settings.sandbox_root).resolve()
ALLOWED = {"ls","pwd","cat","head","tail","wc","find","grep","sed","awk","stat","du","df"}
def safe_path(p: str) -> Path:
    candidate = (ROOT / p).resolve() if not Path(p).is_absolute() else Path(p).resolve()
    if candidate != ROOT and ROOT not in candidate.parents: raise ValueError("Path outside sandbox")
    return candidate
async def read_file(path: str) -> str:
    return safe_path(path).read_text(encoding="utf-8", errors="replace")[:100000]
async def list_files(path: str = ".") -> str:
    p = safe_path(path); return "\n".join(str(x.relative_to(ROOT)) for x in list(p.iterdir())[:500])
async def shell(command: str) -> str:
    parts = shlex.split(command)
    if not parts or parts[0] not in ALLOWED: raise ValueError("Command not allowlisted")
    proc = await asyncio.create_subprocess_exec(*parts,cwd=ROOT,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.STDOUT)
    try: out,_ = await asyncio.wait_for(proc.communicate(),timeout=10)
    except asyncio.TimeoutError: proc.kill(); raise ValueError("Command timeout")
    return out.decode(errors="replace")[:50000]
registry.register("read_file","Read a UTF-8 text file inside the sandbox",{"type":"object","properties":{"path":{"type":"string"}},"required":["path"]},read_file)
registry.register("list_files","List files inside the sandbox",{"type":"object","properties":{"path":{"type":"string","default":"."}}},list_files)
registry.register("shell","Run a read-only allowlisted shell command inside the sandbox",{"type":"object","properties":{"command":{"type":"string"}},"required":["command"]},shell)
