from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select
from app.config import settings, insecure_settings
from app.logging_config import setup_logging
from app.db.core import init_db, SessionLocal
from app.db.models import MCPServer
from app.auth import current_user, require_admin, create_token, check_password, Principal
from app.agent.loop import run_agent
from app.llm.router import ProvidersUnavailable
from app.agent.approvals import decide, list_pending
from app.rag.service import ingest, search
from app.mcp_client.client import import_mcp_server
import logging
import app.tools.sandbox, app.tools.rag_tool
setup_logging()
log=logging.getLogger("main")
@asynccontextmanager
async def lifespan(app):
    bad=insecure_settings(settings)
    if bad: raise RuntimeError("Refusing to start with insecure settings; set: "+", ".join(bad))
    await init_db()
    async with SessionLocal() as db:
        servers=(await db.execute(select(MCPServer).where(MCPServer.enabled==True))).scalars().all()
    for s in servers:
        try: await import_mcp_server(s.url,s.prefix)
        except Exception: log.exception("mcp_import_failed name=%s url=%s",s.name,s.url)
    yield
app=FastAPI(title="AI Harness Stage",version="0.2.0",lifespan=lifespan)
class LoginIn(BaseModel): username:str; password:str
class ChatIn(BaseModel): message:str; session_id:str|None=None; provider:str|None=None; model:str|None=None; private:bool=False
class IngestIn(BaseModel): source:str=Field(min_length=1,max_length=512); text:str=Field(min_length=1,max_length=2_000_000)
class ApprovalIn(BaseModel): approve:bool=True
class MCPIn(BaseModel): name:str=Field(min_length=1,max_length=100); url:str=Field(min_length=1,max_length=1024); prefix:str=Field(default="mcp",pattern=r"^[A-Za-z0-9_]{1,64}$")
@app.get("/health")
async def health(): return {"status":"ok","env":settings.app_env,"version":"0.2.0"}
@app.post("/auth/login")
async def login(b:LoginIn):
    if not check_password(b.username,b.password): raise HTTPException(401,"Invalid credentials")
    return {"access_token":create_token(b.username,"admin"),"token_type":"bearer"}
@app.post("/chat")
async def chat(b:ChatIn,u:Principal=Depends(current_user)):
    try:return await run_agent(b.message,b.session_id,b.provider,b.model,u.sub,u.role,b.private)
    except PermissionError as e:raise HTTPException(403,str(e))
    except ProvidersUnavailable as e:raise HTTPException(503,str(e))
    except Exception as e:raise HTTPException(500,str(e))
@app.get("/approvals")
async def approvals(u=Depends(require_admin)): return await list_pending()
@app.post("/approvals/{approval_id}")
async def approve(approval_id:str,b:ApprovalIn,u:Principal=Depends(require_admin)):
    obj=await decide(approval_id,u.sub,b.approve)
    if not obj: raise HTTPException(404,"Pending approval not found")
    return {"id":obj.id,"status":obj.status,"tool":obj.tool}
@app.post("/rag/ingest")
async def rag_ingest(b:IngestIn,u=Depends(current_user)):
    try: return {"chunks":await ingest(b.source,b.text)}
    except ProvidersUnavailable as e: raise HTTPException(503,str(e))
    except ValueError as e: raise HTTPException(422,str(e))
@app.get("/rag/search")
async def rag_search(q:str,k:int=5,u=Depends(current_user)):
    try: return {"results":await search(q,k)}
    except ProvidersUnavailable as e: raise HTTPException(503,str(e))
@app.post("/mcp/servers")
async def add_mcp(b:MCPIn,u=Depends(require_admin)):
    async with SessionLocal() as db:
        if (await db.execute(select(MCPServer).where(MCPServer.name==b.name))).scalars().first(): raise HTTPException(409,"MCP server name already registered")
    try: tools=await import_mcp_server(b.url,b.prefix)
    except Exception as e:
        log.warning("mcp_register_failed name=%s url=%s error=%s",b.name,b.url,e); raise HTTPException(502,f"Could not reach MCP server: {type(e).__name__}")
    try:
        async with SessionLocal() as db: db.add(MCPServer(name=b.name,url=b.url,prefix=b.prefix));await db.commit()
    except IntegrityError: raise HTTPException(409,"MCP server name already registered")
    return {"name":b.name,"tools":tools}
@app.get("/mcp/servers")
async def list_mcp(u=Depends(current_user)):
    async with SessionLocal() as db: rows=(await db.execute(select(MCPServer))).scalars().all()
    return [{"name":r.name,"url":r.url,"prefix":r.prefix,"enabled":r.enabled} for r in rows]
