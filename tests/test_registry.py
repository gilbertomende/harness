import asyncio
from app.config import settings
from app.tools.registry import ToolRegistry, Effect, registry

async def fn(**kw): return "ran"

def test_unclassified_tool_fails_closed():
    r = ToolRegistry(); r.register("mystery", "", {"type": "object"}, fn)
    assert r.effect("mystery") is Effect.DESTRUCTIVE
    assert r.get("mystery", "admin")["roles"] == {"admin"}
    assert asyncio.run(r.execute("mystery", {}, role="admin")) == "APPROVAL_REQUIRED"

def test_unknown_tool_treated_as_destructive():
    assert ToolRegistry().effect("nope") is Effect.DESTRUCTIVE

def test_native_tools_are_classified():
    effects = {n: t["effect"] for n, t in registry._tools.items() if t["source"] == "native"}
    assert effects["read_file"] is Effect.READ and effects["list_files"] is Effect.READ
    assert effects["shell"] is Effect.EXEC and effects["rag_search"] is Effect.QUERY

def test_approval_effects_setting(monkeypatch):
    assert settings.approval_effects == {Effect.WRITE, Effect.DESTRUCTIVE}
    monkeypatch.setattr(settings, "approval_required_effects", "write,exec,destructive")
    assert Effect.EXEC in settings.approval_effects
    monkeypatch.setattr(settings, "approval_required_for_mutating_tools", False)
    assert settings.approval_effects == frozenset()
