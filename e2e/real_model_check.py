#!/usr/bin/env python3
"""Homologation against REAL models (Ollama, and optionally OpenRouter/9Router).

Run on a machine that can pull models, with the plain stack (no compose.e2e.yaml):
  docker compose --profile local-model up -d
  docker compose exec ollama ollama pull qwen3:8b
  docker compose exec ollama ollama pull nomic-embed-text
  python3 e2e/real_model_check.py [--provider ollama|9router|openrouter]
Model answers are not deterministic, so checks look for effects, not exact text.
"""
import argparse, json, pathlib, sys, time
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import smoke
from smoke import call, check, env, summary

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--base", default="http://127.0.0.1:8000"); ap.add_argument("--provider", default="ollama")
    a = ap.parse_args(); smoke.BASE = a.base.rstrip("/"); smoke.wait_healthy()
    t = call("POST", "/auth/login", {"username": env("ADMIN_USERNAME"), "password": env("ADMIN_PASSWORD")})["access_token"]
    marker = f"homolog-{int(time.time())}.txt"
    pathlib.Path("workspace", marker).write_text("codeword: TANGERINE\n")

    def plain():
        r = call("POST", "/chat", {"message": "Reply with the single word: pong", "provider": a.provider}, t)
        assert r["provider"] == a.provider and r["answer"].strip(), r; return f"{r['provider']}/{r['model']}: {r['answer'][:60]!r}"
    check(f"{a.provider}: chat", plain)
    def tools():
        r = call("POST", "/chat", {"provider": a.provider, "message": f"Use the read_file tool to read '{marker}' in the sandbox and tell me the codeword."}, t)
        assert "TANGERINE" in r["answer"].upper(), r; return "model called read_file and used its result"
    check(f"{a.provider}: tool calling (read_file)", tools)
    def rag():
        call("POST", "/rag/ingest", {"source": "homolog/policy.md", "text": "The Colband harness retention policy keeps audit events for 400 days."}, t)
        r = call("GET", "/rag/search?q=how%20long%20are%20audit%20events%20kept&k=3", token=t)["results"]
        assert r and r[0]["source"] == "homolog/policy.md", r; return "nomic-embed-text + pgvector ranking"
    check("ollama: embeddings + RAG search", rag)
    def private():
        r = call("POST", "/chat", {"message": "Say ok", "private": True}, t); assert r["provider"] == "ollama", r; return "private stays on ollama"
    check("private routing", private)
    pathlib.Path("workspace", marker).unlink(missing_ok=True)
    summary()

if __name__ == "__main__":
    main()
