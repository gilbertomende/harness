from pathlib import Path
import asyncio, os, shlex
from app.config import settings
from app.tools.registry import registry
ROOT = Path(settings.sandbox_root).resolve()
# awk/sed are excluded on purpose: awk system() and GNU sed "e"/"w"/-i can execute or write.
ALLOWED = {"ls","pwd","cat","head","tail","wc","find","grep","stat","du","df"}
# Flags that execute commands, write files or follow symlinks out of the sandbox.
BLOCKED_FLAGS = {
    "find": {"-exec","-execdir","-ok","-okdir","-delete","-fprint","-fprint0","-fprintf","-fls","-L","-H","-follow"},
    "grep": {"-R","--dereference-recursive"},
    "du": {"-L","--dereference"},
}
SAFE_ENV = {"PATH": "/usr/local/bin:/usr/bin:/bin", "LANG": "C.UTF-8"}
def safe_path(p: str) -> Path:
    candidate = (ROOT / p).resolve() if not Path(p).is_absolute() else Path(p).resolve()
    if candidate != ROOT and ROOT not in candidate.parents: raise ValueError("Path outside sandbox")
    return candidate
def _path_candidates(arg: str):
    if not arg.startswith("-"): return [arg]
    if "=" in arg: return [arg.split("=", 1)[1]]
    if not arg.startswith("--") and len(arg) > 2: return [arg[2:]]  # attached short-option value, e.g. -f/etc/x
    return []
def check_args(cmd: str, args: list[str]):
    blocked = BLOCKED_FLAGS.get(cmd, set())
    for a in args:
        if a in blocked or a.split("=", 1)[0] in blocked: raise ValueError(f"Flag not allowed: {a}")
        for c in _path_candidates(a):
            if not c: continue
            if c.startswith(("/", "~")) or ".." in Path(c).parts or (ROOT / c).is_symlink() or (ROOT / c).exists():
                safe_path(c)
async def read_file(path: str) -> str:
    return safe_path(path).read_text(encoding="utf-8", errors="replace")[:100000]
async def list_files(path: str = ".") -> str:
    p = safe_path(path); return "\n".join(str(x.relative_to(ROOT)) for x in list(p.iterdir())[:500])
async def shell(command: str) -> str:
    parts = shlex.split(command)
    if not parts or parts[0] not in ALLOWED: raise ValueError("Command not allowlisted")
    check_args(parts[0], parts[1:])
    proc = await asyncio.create_subprocess_exec(*parts,cwd=ROOT,env=SAFE_ENV,stdin=asyncio.subprocess.DEVNULL,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.STDOUT)
    try: out,_ = await asyncio.wait_for(proc.communicate(),timeout=10)
    except asyncio.TimeoutError: proc.kill(); await proc.wait(); raise ValueError("Command timeout")
    return out.decode(errors="replace")[:50000]
registry.register("read_file","Read a UTF-8 text file inside the sandbox",{"type":"object","properties":{"path":{"type":"string"}},"required":["path"]},read_file)
registry.register("list_files","List files inside the sandbox",{"type":"object","properties":{"path":{"type":"string","default":"."}}},list_files)
registry.register("shell","Run a read-only allowlisted shell command inside the sandbox ("+", ".join(sorted(ALLOWED))+"). Paths must stay inside the sandbox.",{"type":"object","properties":{"command":{"type":"string"}},"required":["command"]},shell)
