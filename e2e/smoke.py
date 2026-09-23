#!/usr/bin/env python3
"""End-to-end homologation of a running stack (docker-compose.yml + compose.e2e.yaml).

Usage:  python3 e2e/smoke.py [--base http://127.0.0.1:8000] [--restart]
Reads ADMIN_USERNAME/ADMIN_PASSWORD from the environment or ./.env (never printed).
--restart restarts the harness container mid-run to prove sessions persist in PostgreSQL.
Stdlib only, so it runs on any host with python3. Exit code != 0 on the first failure.
"""
import argparse, json, os, subprocess, sys, time, urllib.error, urllib.request

COMPOSE = os.environ.get("COMPOSE", "docker compose -f docker-compose.yml -f compose.e2e.yaml").split()
MCP_URL = os.environ.get("E2E_MCP_URL", "http://mcp-demo:9100/mcp")
RESULTS = []
BASE = "http://127.0.0.1:8000"

def env(name):
    if os.environ.get(name): return os.environ[name]
    try:
        for line in open(".env", encoding="utf-8"):
            k, _, v = line.strip().partition("=")
            if k == name: return v
    except FileNotFoundError: pass
    sys.exit(f"{name} not set (environment or .env)")

def call(method, path, body=None, token=None, expect=200):
    req = urllib.request.Request(BASE + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json", **({"Authorization": f"Bearer {token}"} if token else {})})
    try:
        with urllib.request.urlopen(req, timeout=60) as r: status, raw = r.status, r.read()
    except urllib.error.HTTPError as e: status, raw = e.code, e.read()
    data = json.loads(raw) if raw else None
    if status != expect: raise AssertionError(f"{method} {path}: expected {expect}, got {status}: {data}")
    return data

def check(name, fn):
    try:
        detail = fn(); RESULTS.append((name, True, detail or "")); print(f"PASS  {name}  {detail or ''}")
    except Exception as e:
        RESULTS.append((name, False, str(e))); print(f"FAIL  {name}  {e}"); summary(); sys.exit(1)

def summary():
    ok = sum(1 for _, p, _ in RESULTS if p); print(f"\n{ok}/{len(RESULTS)} checks passed")

def wait_healthy(timeout=90):
    end = time.time() + timeout
    while time.time() < end:
        try:
            if call("GET", "/health")["status"] == "ok": return
        except Exception: pass
        time.sleep(2)
    raise AssertionError("harness did not become healthy")

def main():
    global BASE
    ap = argparse.ArgumentParser(); ap.add_argument("--base", default="http://127.0.0.1:8000"); ap.add_argument("--restart", action="store_true")
    a = ap.parse_args(); BASE = a.base.rstrip("/")
    wait_healthy()
    S = {}

    # 7. health + auth
    check("health", lambda: call("GET", "/health"))
    check("auth: chat without token -> 401", lambda: call("POST", "/chat", {"message": "x"}, expect=401) and "401")
    check("auth: wrong password -> 401", lambda: call("POST", "/auth/login", {"username": env("ADMIN_USERNAME"), "password": "wrong"}, expect=401) and "401")
    def login():
        S["t"] = call("POST", "/auth/login", {"username": env("ADMIN_USERNAME"), "password": env("ADMIN_PASSWORD")})["access_token"]
        return "token issued"
    check("auth: login", login)
    t = lambda: S["t"]

    # 8. model adapter (OpenAI-compatible) via the agent loop
    def chat1():
        r = call("POST", "/chat", {"message": "hello harness"}, t()); S["sid"] = r["session_id"]
        assert r["answer"] == "ECHO: hello harness | user_turns=1", r
        assert r["provider"] == "ollama", r
        return f"provider={r['provider']} model={r['model']}"
    check("llm: chat through OpenAI-compatible adapter", chat1)
    check("router: private=true + remote provider -> 403",
          lambda: call("POST", "/chat", {"message": "x", "private": True, "provider": "openrouter"}, t(), expect=403) and "403")

    # 9. session persistence
    def chat2():
        r = call("POST", "/chat", {"message": "second", "session_id": S["sid"]}, t())
        assert r["session_id"] == S["sid"] and r["answer"].endswith("user_turns=2"), r
        return "history reloaded from DB (user_turns=2)"
    check("session: history is persisted and reused", chat2)
    if a.restart:
        def restart():
            subprocess.run(COMPOSE + ["restart", "harness"], check=True, capture_output=True); wait_healthy()
            login()
            r = call("POST", "/chat", {"message": "after restart", "session_id": S["sid"]}, t())
            assert r["session_id"] == S["sid"] and r["answer"].endswith("user_turns=3"), r
            return "session survived container restart (user_turns=3)"
        check("session: survives harness restart", restart)

    # 10. tool calling + sandbox
    def tool(cmd, args):
        return call("POST", "/chat", {"message": f"CALL {cmd} {json.dumps(args)}"}, t())["answer"]
    def list_files():
        a = tool("list_files", {"path": "."}); assert a.startswith("TOOL_RESULT") and "ERROR" not in a, a; return a[:80]
    check("tools: list_files", list_files)
    def sandbox_ok():
        a = tool("shell", {"command": "pwd"}); assert "/workspace" in a, a; return a[:80]
    check("sandbox: allowlisted shell runs in /workspace", sandbox_ok)
    for label, cmd in [("absolute path", "cat /etc/passwd"), ("awk exec", "awk 'BEGIN{system(\"id\")}'"),
                       ("find -exec", "find . -exec id ;"), ("proc environ", "cat /proc/self/environ")]:
        def denied(cmd=cmd):
            a = tool("shell", {"command": cmd}); assert "ERROR: ValueError" in a and "root:" not in a and "uid=" not in a, a; return a.split(": ", 1)[1][:70]
        check(f"sandbox: blocks {label}", denied)
    def read_escape():
        a = tool("read_file", {"path": "../etc/passwd"}); assert "Path outside sandbox" in a, a; return "Path outside sandbox"
    check("sandbox: read_file blocks traversal", read_escape)

    # 11. RAG
    def ingest():
        n = call("POST", "/rag/ingest", {"source": "e2e/kb.md", "text": "The Colband harness stores embeddings in pgvector. Tokens expire after sixty minutes."}, t())["chunks"]
        call("POST", "/rag/ingest", {"source": "e2e/other.md", "text": "Bananas are yellow fruit rich in potassium."}, t())
        assert n == 1; return f"chunks={n}"
    check("rag: ingest", ingest)
    def search():
        r = call("GET", "/rag/search?q=where%20are%20embeddings%20stored%20pgvector&k=2", token=t())["results"]
        assert r and r[0]["source"] == "e2e/kb.md", r; return f"top={r[0]['source']}"
    check("rag: semantic search ranks relevant chunk first", search)
    def rag_tool():
        a = tool("rag_search", {"query": "banana potassium", "k": 1}); assert "e2e/other.md" in a, a; return "rag_search tool via agent"
    check("rag: rag_search tool through agent loop", rag_tool)
    check("rag: empty text -> 422", lambda: call("POST", "/rag/ingest", {"source": "x", "text": "  "}, t(), expect=422) and "422")
    def rag_k():
        n = len(call("GET", "/rag/search?q=x&k=500", token=t())["results"]); assert n <= 10, n; return f"k=500 -> {n} results"
    check("rag: k is clamped", rag_k)

    # 12. MCP
    def mcp_add():
        r = call("POST", "/mcp/servers", {"name": f"demo-{int(time.time())}", "url": MCP_URL, "prefix": "demo"}, t())
        assert set(r["tools"]) >= {"demo_add", "demo_append_note"}, r; return f"tools={r['tools']}"
    check("mcp: register streamable-HTTP server", mcp_add)
    def mcp_dup():
        name = f"dup-{int(time.time())}"
        call("POST", "/mcp/servers", {"name": name, "url": MCP_URL, "prefix": "dup"}, t())
        call("POST", "/mcp/servers", {"name": name, "url": MCP_URL, "prefix": "dup"}, t(), expect=409); return "409"
    check("mcp: duplicate name -> 409", mcp_dup)
    check("mcp: unreachable server -> 502",
          lambda: call("POST", "/mcp/servers", {"name": "unreachable", "url": "http://127.0.0.1:9/mcp", "prefix": "x"}, t(), expect=502) and "502")
    def mcp_readonly():
        a = tool("demo_add", {"a": 2, "b": 40}); assert "42" in a, a; return a[:80]
    check("mcp: read-only tool executes", mcp_readonly)
    def mcp_gate():
        r = call("POST", "/chat", {"message": 'CALL demo_append_note {"text": "hi"}'}, t())
        assert r.get("pending_approvals"), r
        S["aid"], S["sid2"] = r["pending_approvals"][0]["id"], r["session_id"]; return f"pending approval {S['aid'][:8]}"
    check("approval: mutating MCP tool is gated", mcp_gate)
    def mcp_approve():
        assert call("POST", f"/approvals/{S['aid']}", {"approve": True}, t())["status"] == "approved"
        a = call("POST", "/chat", {"message": 'CALL demo_append_note {"text": "hi"}', "session_id": S["sid2"]}, t())["answer"]
        assert "notes=" in a, a; return a[:80]
    check("approval: admin-approved call executes once", mcp_approve)
    def mcp_single_use():
        r = call("POST", "/chat", {"message": 'CALL demo_append_note {"text": "hi"}', "session_id": S["sid2"]}, t())
        assert r.get("pending_approvals"), r; return "new approval required"
    check("approval: grant is single-use", mcp_single_use)
    summary()

if __name__ == "__main__":
    main()
