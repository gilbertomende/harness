"""Deterministic OpenAI-compatible stub used ONLY for local homologation (compose.e2e.yaml).

It lets the harness be exercised end to end (agent loop, tool calling, sessions, RAG, MCP)
without downloading model weights. It is not a model: behaviour is scripted.

Chat rules (applied to the conversation sent by the harness):
  * last message is a tool result      -> answer "TOOL_RESULT[<tool_call_id>]: <content>"
  * last user message "CALL <tool> <json-args>" and that tool is offered -> emit a tool call
  * otherwise                          -> "ECHO: <text> | user_turns=<n>" (n proves history was sent)
Embeddings: 768-dim hashed bag-of-words, L2-normalised, so texts sharing words are close.
"""
import hashlib, json, math, re, time, uuid
from fastapi import FastAPI, Request

DIM = 768
app = FastAPI(title="fake-llm")

def embed(text: str) -> list[float]:
    v = [0.0] * DIM
    for tok in re.findall(r"\w+", text.lower()):
        h = int.from_bytes(hashlib.sha256(tok.encode()).digest()[:8], "big")
        v[h % DIM] += 1.0 if (h >> 63) == 0 else -1.0
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]

def completion(model: str, message: dict, finish: str) -> dict:
    return {"id": f"chatcmpl-{uuid.uuid4().hex[:12]}", "object": "chat.completion", "created": int(time.time()),
            "model": model, "choices": [{"index": 0, "message": message, "finish_reason": finish}],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}}

@app.get("/v1/models")
async def models():
    return {"object": "list", "data": [{"id": "fake-chat", "object": "model"}, {"id": "fake-embed", "object": "model"}]}

@app.post("/v1/chat/completions")
async def chat(req: Request):
    body = await req.json()
    model, msgs = body.get("model", "fake-chat"), body.get("messages", [])
    offered = {t["function"]["name"] for t in body.get("tools") or []}
    last = msgs[-1] if msgs else {"role": "user", "content": ""}
    if last.get("role") == "tool":
        return completion(model, {"role": "assistant", "content": f"TOOL_RESULT[{last.get('tool_call_id')}]: {last.get('content')}"}, "stop")
    text = last.get("content") or ""
    m = re.match(r"^CALL (\S+)(?: (.*))?$", text.strip(), re.S)
    if m and m.group(1) in offered:
        call = {"id": f"call_{uuid.uuid4().hex[:8]}", "type": "function",
                "function": {"name": m.group(1), "arguments": m.group(2) or "{}"}}
        return completion(model, {"role": "assistant", "content": None, "tool_calls": [call]}, "tool_calls")
    if m:
        return completion(model, {"role": "assistant", "content": f"TOOL_NOT_OFFERED: {m.group(1)}"}, "stop")
    turns = sum(1 for x in msgs if x.get("role") == "user")
    return completion(model, {"role": "assistant", "content": f"ECHO: {text} | user_turns={turns}"}, "stop")

@app.post("/v1/embeddings")
async def embeddings(req: Request):
    body = await req.json()
    inputs = body.get("input") or []
    inputs = [inputs] if isinstance(inputs, str) else inputs
    return {"object": "list", "model": body.get("model", "fake-embed"),
            "data": [{"object": "embedding", "index": i, "embedding": embed(t)} for i, t in enumerate(inputs)],
            "usage": {"prompt_tokens": 0, "total_tokens": 0}}
