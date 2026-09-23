"""ROADMAP v0.2.x gate items and SECURITY.md controls not covered elsewhere."""
import asyncio, json
from types import SimpleNamespace as NS
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from app import main
from app.agent import loop
from app.auth import create_token
from app.config import settings
from app.db.core import SessionLocal
from app.db.models import AuditEvent, MCPServer
from app.llm.router import router, ProvidersUnavailable
from app.rag import service
from app.tools.registry import registry, Effect

def reply(text=None, calls=None):
    return NS(choices=[NS(message=NS(content=text, tool_calls=calls))])

class ScriptedRouter:
    """Returns the scripted replies in order and records the conversations it was sent."""
    def __init__(self, *replies): self.replies, self.seen = list(replies), []
    async def chat(self, *, messages, **kw):
        self.seen.append([dict(m) for m in messages]); return self.replies.pop(0), "fake", "fake-model"

def events(action=None):
    async def q():
        async with SessionLocal() as db:
            stmt = select(AuditEvent).order_by(AuditEvent.created_at)
            if action: stmt = stmt.where(AuditEvent.action == action)
            return (await db.execute(stmt)).scalars().all()
    return asyncio.run(q())

# --- gate 4: sessions are owner-scoped
def test_foreign_session_id_never_exposes_history(db, monkeypatch):
    fake = ScriptedRouter(reply("a1"), reply("b1"))
    monkeypatch.setattr(loop, "router", fake)
    alice = asyncio.run(loop.run_agent("alice secret", owner="alice"))
    bob = asyncio.run(loop.run_agent("hi", session_id=alice["session_id"], owner="bob"))
    assert bob["session_id"] != alice["session_id"]
    assert "alice secret" not in json.dumps(fake.seen[1])

# --- gate 9: automatic fallback
class Prov:
    def __init__(self, fail): self.fail, self.calls = fail, 0
    async def chat(self, **kw):
        self.calls += 1
        if self.fail: raise ConnectionError("down")
        return "ok"

def test_auto_fallback_to_next_provider(monkeypatch):
    monkeypatch.setitem(router.keys, "openrouter", "sk-test"); monkeypatch.setitem(router.models, "9router", "m9")
    provs = {"ollama": Prov(True), "9router": Prov(True), "openrouter": Prov(False)}
    monkeypatch.setattr(router, "providers", provs)
    _, used, _ = asyncio.run(router.chat(messages=[]))
    assert used == "openrouter" and all(p.calls == 1 for p in provs.values())

def test_private_never_falls_back_to_cloud(monkeypatch):
    monkeypatch.setitem(router.keys, "openrouter", "sk-test")
    provs = {"ollama": Prov(True), "9router": Prov(False), "openrouter": Prov(False)}
    monkeypatch.setattr(router, "providers", provs)
    with pytest.raises(ProvidersUnavailable): asyncio.run(router.chat(messages=[], private=True))
    assert provs["9router"].calls == provs["openrouter"].calls == 0

# --- SECURITY §13.3: global cloud kill switch
def test_cloud_disabled_forces_local_only(monkeypatch):
    monkeypatch.setitem(router.keys, "openrouter", "sk-test")
    monkeypatch.setattr(settings, "cloud_providers_enabled", False)
    assert [p for p, _ in router.candidates("auto")] == ["ollama"]
    with pytest.raises(PermissionError, match="CLOUD_PROVIDERS_ENABLED"): router.candidates("openrouter")

def test_cloud_disabled_blocks_cloud_embeddings(monkeypatch):
    monkeypatch.setattr(settings, "cloud_providers_enabled", False)
    monkeypatch.setattr(settings, "embed_provider", "openrouter")
    with pytest.raises(ProvidersUnavailable, match="CLOUD_PROVIDERS_ENABLED"): asyncio.run(service.embed(["x"]))

# --- SECURITY §10: audit of every tool attempt, without raw arguments
async def _echo(secret: str): return "done"
registry.register("audit_probe", "", {"type": "object"}, _echo, effect=Effect.READ)

def test_tool_calls_audited_with_status_and_no_raw_args(db, monkeypatch):
    call = lambda name, args: NS(id="c", function=NS(name=name, arguments=json.dumps(args)))
    fake = ScriptedRouter(reply(calls=[call("audit_probe", {"secret": "hunter2"}), call("nope_tool", {})]), reply("fin"))
    monkeypatch.setattr(loop, "router", fake)
    r = asyncio.run(loop.run_agent("go", owner="alice"))
    tc = {e.detail["tool"]: e.detail for e in events("tool_call")}
    assert tc["audit_probe"]["status"] == "ok" and tc["audit_probe"]["effect"] == "READ"
    assert tc["nope_tool"]["status"] == "denied"
    assert all(d["request_id"] == r["request_id"] and d["provider"] == "fake" and "latency_ms" in d for d in tc.values())
    assert "hunter2" not in json.dumps([e.detail for e in events()])
    res = events("chat_result")[-1].detail
    assert res["status"] == "ok" and res["model"] == "fake-model" and res["steps"] == 2

def test_failed_chat_is_audited(db, monkeypatch):
    class Down:
        async def chat(self, **kw): raise ProvidersUnavailable("down")
    monkeypatch.setattr(loop, "router", Down())
    with pytest.raises(ProvidersUnavailable): asyncio.run(loop.run_agent("x", owner="alice"))
    assert events("chat_result")[-1].detail["status"] == "failed"

# --- SECURITY §13.2: disable a compromised MCP server; registry visibility
client = TestClient(main.app)
ADMIN = {"Authorization": f"Bearer {create_token('admin', 'admin')}"}
USER = {"Authorization": f"Bearer {create_token('u', 'user')}"}

def test_disable_mcp_server_removes_tools(db):
    async def seed():
        async with SessionLocal() as s: s.add(MCPServer(name="srv", url="http://x/mcp", prefix="srv")); await s.commit()
    asyncio.run(seed())
    async def t(**kw): return "x"
    registry.register("srv_tool", "", {"type": "object"}, t, effect=Effect.QUERY, source="mcp:srv")
    r = client.patch("/mcp/servers/srv", json={"enabled": False}, headers=ADMIN)
    assert r.status_code == 200 and r.json()["tools"] == ["srv_tool"]
    with pytest.raises(ValueError): registry.get("srv_tool", "admin")
    assert events("mcp_disabled")[-1].detail["server"] == "srv"

def test_mcp_prefix_must_be_unique(db):
    async def seed():
        async with SessionLocal() as s: s.add(MCPServer(name="a", url="http://x/mcp", prefix="shared")); await s.commit()
    asyncio.run(seed())
    assert client.post("/mcp/servers", json={"name": "b", "url": "http://x/mcp", "prefix": "shared"}, headers=ADMIN).status_code == 409

def test_mcp_url_policy_is_422():
    assert client.post("/mcp/servers", json={"name": "f", "url": "file:///etc/passwd", "prefix": "f"}, headers=ADMIN).status_code == 422

@pytest.mark.parametrize("method,path", [("get", "/tools"), ("get", "/mcp/servers"), ("get", "/approvals"),
                                         ("patch", "/mcp/servers/x")])
def test_admin_endpoints_reject_user_role(method, path):
    kw = {"json": {"enabled": False}} if method == "patch" else {}
    assert getattr(client, method)(path, headers=USER, **kw).status_code == 403

def test_tools_endpoint_lists_effects():
    rows = {t["name"]: t for t in client.get("/tools", headers=ADMIN).json()}
    assert rows["shell"]["effect"] == "EXEC" and rows["shell"]["requires_approval"] is False
    assert rows["rag_search"]["effect"] == "QUERY"
