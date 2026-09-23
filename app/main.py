from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy import select
from app.config import settings
from app.logging_config import setup_logging
from app.db.core import init_db, SessionLocal
from app.db.models import MCPServer
from app.auth import current_user, require_admin, create_token, Principal
from app.agent.loop import run_agent
from app.rag.service import ingest, search
from app.mcp_client.client import import_mcp_server
import app.tools.sandbox, app.tools.rag_tool
setup_logging()
@asynccontextmanager
async def lifespan(app):
    await init_db()
    async with SessionLocal() as db:
        servers=(await db.execute(select(MCPServer).where(MCPServer.enabled==True))).scalars().all()
    for s in servers:
        try: await import_mcp_server(s.url,s.prefix)
        except Exception: pass
    yield
app=FastAPI(title="AI Harness Stage",version="0.2.0",lifespan=lifespan)
class LoginIn(BaseModel): username:str; password:str
class ChatIn(BaseModel): message:str; session_id:str|None=None; provider:str|None=None; model:str|None=None; private:bool=False; approved:bool=False
class IngestIn(BaseModel): source:str; text:str
class MCPIn(BaseModel): name:str; url:str; prefix:str="mcp"
@app.get("/health")
async def health(): return {"status":"ok","env":settings.app_env,"version":"0.2.0"}
@app.post("/auth/login")
async def login(b:LoginIn):
    if b.username!=settings.admin_username or b.password!=settings.admin_password: raise HTTPException(401,"Invalid credentials")
    return {"access_token":create_token(b.username,"admin"),"token_type":"bearer"}
@app.post("/chat")
async def chat(b:ChatIn,u:Principal=Depends(current_user)):
    try:return await run_agent(b.message,b.session_id,b.provider,b.model,u.sub,u.role,b.private,b.approved)
    except Exception as e:raise HTTPException(500,str(e))
@app.post("/rag/ingest")
async def rag_ingest(b:IngestIn,u=Depends(current_user)): return {"chunks":await ingest(b.source,b.text)}
@app.get("/rag/search")
async def rag_search(q:str,k:int=5,u=Depends(current_user)): return {"results":await search(q,min(max(k,1),10))}
@app.post("/mcp/servers")
async def add_mcp(b:MCPIn,u=Depends(require_admin)):
    tools=await import_mcp_server(b.url,b.prefix)
    async with SessionLocal() as db: db.add(MCPServer(name=b.name,url=b.url,prefix=b.prefix));await db.commit()
    return {"name":b.name,"tools":tools}
@app.get("/mcp/servers")
async def list_mcp(u=Depends(current_user)):
    async with SessionLocal() as db: rows=(await db.execute(select(MCPServer))).scalars().all()
    return [{"name":r.name,"url":r.url,"prefix":r.prefix,"enabled":r.enabled} for r in rows]
