import json, logging
from sqlalchemy import select
from app.config import settings
from app.db.core import SessionLocal
from app.db.models import Session as DBSession, Message, AuditEvent
from app.llm.router import router
from app.tools.registry import registry
log=logging.getLogger("agent")
SYSTEM='''You are an AI agent operating through a controlled harness. Use tools only when needed. Use rag_search for private knowledge. Never claim an action succeeded unless its tool result confirms it. If a tool returns APPROVAL_REQUIRED, stop and tell the user approval is required.'''
async def ensure_session(session_id, owner):
    async with SessionLocal() as db:
        if session_id:
            obj=await db.get(DBSession,session_id)
            if obj and obj.owner==owner:return obj.id
        obj=DBSession(owner=owner);db.add(obj);await db.commit();await db.refresh(obj);return obj.id
async def run_agent(user_text,session_id=None,provider=None,model=None,owner="anonymous",role="user",private=False,approved=False):
    sid=await ensure_session(session_id,owner); requested=provider or settings.default_provider
    async with SessionLocal() as db:
        db.add(Message(session_id=sid,role="user",content=user_text));db.add(AuditEvent(actor=owner,action="chat",detail={"session_id":sid}));await db.commit()
        hist=(await db.execute(select(Message).where(Message.session_id==sid).order_by(Message.created_at))).scalars().all()
    messages=[{"role":"system","content":SYSTEM}]+[{"role":m.role,"content":m.content} for m in hist]
    used_provider=used_model=None
    for step in range(settings.max_agent_steps):
        r,used_provider,used_model=await router.chat(requested=requested,model=model,messages=messages,tools=registry.specs(role),private=private)
        msg=r.choices[0].message
        if not msg.tool_calls:
            answer=msg.content or ""
            async with SessionLocal() as db: db.add(Message(session_id=sid,role="assistant",content=answer));await db.commit()
            return {"session_id":sid,"answer":answer,"provider":used_provider,"model":used_model}
        messages.append({"role":"assistant","content":msg.content,"tool_calls":[{"id":tc.id,"type":"function","function":{"name":tc.function.name,"arguments":tc.function.arguments}} for tc in msg.tool_calls]})
        for tc in msg.tool_calls:
            try: result=await registry.execute(tc.function.name,json.loads(tc.function.arguments or "{}"),role=role,approved=approved)
            except Exception as e: result=f"ERROR: {type(e).__name__}: {e}"
            messages.append({"role":"tool","tool_call_id":tc.id,"content":str(result)})
    raise RuntimeError("Maximum agent steps exceeded")
