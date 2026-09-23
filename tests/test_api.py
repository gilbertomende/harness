import asyncio
import pytest
from fastapi.testclient import TestClient
from app import main
from app.auth import create_token
from app.config import Settings, insecure_settings
from app.db.core import SessionLocal
from app.db.models import MCPServer
from app.rag import service

client = TestClient(main.app)  # no `with`: lifespan (Postgres-only init) is not run
H = {"Authorization": f"Bearer {create_token('admin', 'admin')}"}

# --- secrets guard
@pytest.mark.parametrize("kw", [{}, {"jwt_secret": "CHANGE_TO_LONG_RANDOM_SECRET"}, {"jwt_secret": "short"},
                                {"jwt_secret": "x" * 40, "admin_password": "CHANGE_ADMIN_PASSWORD"}])
def test_insecure_settings_detected(kw):
    assert insecure_settings(Settings(_env_file=None, **kw))

def test_secure_settings_pass():
    assert insecure_settings(Settings(_env_file=None, jwt_secret="a" * 64, admin_password="b" * 20)) == []

def test_lifespan_refuses_insecure_settings(monkeypatch):
    monkeypatch.setattr(main, "settings", Settings(_env_file=None))
    async def start():
        async with main.lifespan(main.app): pass
    with pytest.raises(RuntimeError, match="insecure settings"): asyncio.run(start())

def test_login_constant_time_and_rejects_wrong(monkeypatch):
    monkeypatch.setattr(main.settings, "admin_password", "correct-horse-battery")
    assert client.post("/auth/login", json={"username": "admin", "password": "nope"}).status_code == 401
    assert client.post("/auth/login", json={"username": "admin", "password": "correct-horse-battery"}).status_code == 200

# --- RAG input validation
def test_chunks_drop_blank():
    assert service.chunks("   ") == [] and service.chunks("abc") == ["abc"]

@pytest.mark.parametrize("text", ["", "   \n  "])
def test_ingest_rejects_empty(text):
    assert client.post("/rag/ingest", json={"source": "s", "text": text}, headers=H).status_code == 422

def test_search_clamps_k(monkeypatch):
    seen = {}
    class Emb:
        async def embed(self, *, model, texts): return [[0.0] * 768 for _ in texts]
    class Res:
        def scalars(self): return self
        def all(self): return []
    class DB:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): pass
        async def execute(self, stmt): seen["limit"] = stmt._limit_clause.value; return Res()
    monkeypatch.setattr(service.router, "get", lambda name: Emb())
    monkeypatch.setattr(service, "SessionLocal", DB)
    asyncio.run(service.search("q", k=1000)); assert seen["limit"] == 10
    asyncio.run(service.search("q", k=0)); assert seen["limit"] == 1

# --- MCP registration errors
def test_mcp_duplicate_name_is_409(db):
    async def seed():
        async with SessionLocal() as s: s.add(MCPServer(name="dup", url="http://x/mcp", prefix="dup")); await s.commit()
    asyncio.run(seed())
    r = client.post("/mcp/servers", json={"name": "dup", "url": "http://x/mcp", "prefix": "dup"}, headers=H)
    assert r.status_code == 409

def test_mcp_unreachable_is_502(db):
    r = client.post("/mcp/servers", json={"name": "bad", "url": "http://127.0.0.1:9/mcp", "prefix": "bad"}, headers=H)
    assert r.status_code == 502

def test_mcp_prefix_validated():
    r = client.post("/mcp/servers", json={"name": "n", "url": "http://x/mcp", "prefix": "bad prefix!"}, headers=H)
    assert r.status_code == 422

# --- providers unavailable is 503, not 500
def test_chat_providers_unavailable_is_503(monkeypatch):
    from app.llm.router import ProvidersUnavailable
    async def boom(*a, **k): raise ProvidersUnavailable("All model providers failed")
    monkeypatch.setattr(main, "run_agent", boom)
    assert client.post("/chat", json={"message": "hi"}, headers=H).status_code == 503

# --- embedding backend failures are explicit 503s
class _Emb:
    def __init__(self, dim=768, exc=None): self.dim, self.exc = dim, exc
    async def embed(self, *, model, texts):
        if self.exc: raise self.exc
        return [[0.0] * self.dim for _ in texts]

def test_ingest_embedding_failure_is_503(monkeypatch):
    monkeypatch.setattr(service.router, "get", lambda name: _Emb(exc=RuntimeError("model 'nomic-embed-text' not found")))
    r = client.post("/rag/ingest", json={"source": "s", "text": "hello"}, headers=H)
    assert r.status_code == 503 and "not found" in r.json()["detail"]

def test_search_embedding_failure_is_503(monkeypatch):
    monkeypatch.setattr(service.router, "get", lambda name: _Emb(exc=RuntimeError("down")))
    assert client.get("/rag/search?q=x", headers=H).status_code == 503

def test_embedding_dimension_mismatch_is_explicit(monkeypatch):
    monkeypatch.setattr(service.router, "get", lambda name: _Emb(dim=1024))
    r = client.post("/rag/ingest", json={"source": "s", "text": "hello"}, headers=H)
    assert r.status_code == 503 and "1024" in r.json()["detail"] and "768" in r.json()["detail"]
