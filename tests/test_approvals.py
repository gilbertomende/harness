import asyncio, json
from types import SimpleNamespace as NS
import pytest
from app.db.core import engine
from app.db.models import Base
from app.agent import loop
from app.agent.approvals import decide, list_pending
from app.tools.registry import registry

calls = []
async def danger(target: str):
    calls.append(target); return f"deleted {target}"
registry.register("danger", "mutating test tool", {"type":"object","properties":{"target":{"type":"string"}}}, danger, mutating=True)

class FakeRouter:
    """Calls `danger` on the first step, then answers."""
    async def chat(self, *, messages, **kw):
        if messages[-1]["role"] == "tool":
            msg = NS(content="done: " + messages[-1]["content"], tool_calls=None)
        else:
            tc = NS(id="c1", function=NS(name="danger", arguments=json.dumps({"target": "x"})))
            msg = NS(content=None, tool_calls=[tc])
        return NS(choices=[NS(message=msg)]), "fake", "fake-model"

@pytest.fixture(autouse=True)
def db(monkeypatch):
    async def reset():
        async with engine.begin() as c:
            await c.run_sync(Base.metadata.drop_all); await c.run_sync(Base.metadata.create_all)
    asyncio.run(reset()); calls.clear()
    monkeypatch.setattr(loop, "router", FakeRouter())

def test_client_cannot_self_approve():
    import inspect
    assert "approved" not in inspect.signature(loop.run_agent).parameters

def test_mutating_tool_requires_admin_approval_bound_to_exact_call():
    async def flow():
        r1 = await loop.run_agent("delete x", owner="alice")
        assert calls == [] and len(r1["pending_approvals"]) == 1
        aid = r1["pending_approvals"][0]["id"]; sid = r1["session_id"]
        # Retrying before approval reuses the same pending request and still does not execute.
        r2 = await loop.run_agent("retry", session_id=sid, owner="alice")
        assert calls == [] and r2["pending_approvals"][0]["id"] == aid
        assert [p["id"] for p in await list_pending()] == [aid]
        assert (await decide(aid, "admin", True)).status == "approved"
        assert await decide(aid, "admin", True) is None           # cannot decide twice
        r3 = await loop.run_agent("retry", session_id=sid, owner="alice")
        assert calls == ["x"] and "pending_approvals" not in r3
        # Approval is single-use.
        r4 = await loop.run_agent("again", session_id=sid, owner="alice")
        assert calls == ["x"] and r4["pending_approvals"][0]["id"] != aid
    asyncio.run(flow())

def test_rejected_approval_never_executes():
    async def flow():
        r1 = await loop.run_agent("delete x", owner="bob")
        await decide(r1["pending_approvals"][0]["id"], "admin", False)
        await loop.run_agent("retry", session_id=r1["session_id"], owner="bob")
        assert calls == []
    asyncio.run(flow())

def test_setting_disables_gate(monkeypatch):
    monkeypatch.setattr(loop.settings, "approval_required_for_mutating_tools", False)
    r = asyncio.run(loop.run_agent("delete x", owner="carol"))
    assert calls == ["x"] and "pending_approvals" not in r
