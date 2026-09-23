import asyncio, os, pytest
from app.tools import sandbox

def run(cmd): return asyncio.run(sandbox.shell(cmd))

@pytest.fixture(autouse=True)
def files():
    root = sandbox.ROOT
    (root / "notes.txt").write_text("hello sandbox\n")
    link = root / "escape"
    if not link.is_symlink(): os.symlink("/etc/hostname", link)

@pytest.mark.parametrize("cmd", [
    "awk 'BEGIN{system(\"id\")}'",          # awk removed from allowlist
    "sed -n 1p notes.txt",                  # sed removed from allowlist
    "find . -exec id ;",
    "find . -delete",
    "find -L .",
    "grep -R x .",
    "cat /etc/hostname",
    "cat ../../etc/hostname",
    "cat /proc/self/environ",
    "grep -f/etc/hostname notes.txt",
    "grep --file=/etc/hostname notes.txt",
    "cat escape",                           # symlink pointing outside the sandbox
])
def test_rejects_escapes(cmd):
    with pytest.raises(ValueError): run(cmd)

def test_allowed_commands_still_work():
    assert "hello sandbox" in run("cat notes.txt")
    assert "notes.txt" in run("ls")
    assert "hello" in run("grep -rn hello .")
    assert "./notes.txt" in run("find . -name notes.txt")

def test_subprocess_env_has_no_secrets(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "top-secret")
    assert sandbox.SAFE_ENV.keys() == {"PATH", "LANG"}
