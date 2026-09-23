import uuid
from sqlalchemy import String, Text, DateTime, ForeignKey, func, Boolean, JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from pgvector.sqlalchemy import Vector
class Base(DeclarativeBase): pass
class Session(Base):
    __tablename__="sessions"; id:Mapped[str]=mapped_column(String,primary_key=True,default=lambda:str(uuid.uuid4())); owner:Mapped[str]=mapped_column(String,index=True,default="anonymous"); created_at:Mapped[object]=mapped_column(DateTime(timezone=True),server_default=func.now())
class Message(Base):
    __tablename__="messages"; id:Mapped[str]=mapped_column(String,primary_key=True,default=lambda:str(uuid.uuid4())); session_id:Mapped[str]=mapped_column(ForeignKey("sessions.id",ondelete="CASCADE"),index=True); role:Mapped[str]=mapped_column(String(32)); content:Mapped[str]=mapped_column(Text); created_at:Mapped[object]=mapped_column(DateTime(timezone=True),server_default=func.now())
class DocumentChunk(Base):
    __tablename__="document_chunks"; id:Mapped[str]=mapped_column(String,primary_key=True,default=lambda:str(uuid.uuid4())); source:Mapped[str]=mapped_column(String(512),index=True); content:Mapped[str]=mapped_column(Text); embedding:Mapped[list]=mapped_column(Vector(768))
class MCPServer(Base):
    __tablename__="mcp_servers"; id:Mapped[str]=mapped_column(String,primary_key=True,default=lambda:str(uuid.uuid4())); name:Mapped[str]=mapped_column(String(100),unique=True); url:Mapped[str]=mapped_column(String(1024)); prefix:Mapped[str]=mapped_column(String(64)); enabled:Mapped[bool]=mapped_column(Boolean,default=True); created_at:Mapped[object]=mapped_column(DateTime(timezone=True),server_default=func.now())
class AuditEvent(Base):
    __tablename__="audit_events"; id:Mapped[str]=mapped_column(String,primary_key=True,default=lambda:str(uuid.uuid4())); actor:Mapped[str]=mapped_column(String,index=True); action:Mapped[str]=mapped_column(String,index=True); detail:Mapped[dict]=mapped_column(JSON,default=dict); created_at:Mapped[object]=mapped_column(DateTime(timezone=True),server_default=func.now())
class ToolApproval(Base):
    __tablename__="tool_approvals"; id:Mapped[str]=mapped_column(String,primary_key=True,default=lambda:str(uuid.uuid4())); session_id:Mapped[str]=mapped_column(ForeignKey("sessions.id",ondelete="CASCADE"),index=True); requested_by:Mapped[str]=mapped_column(String,index=True); tool:Mapped[str]=mapped_column(String(200)); args:Mapped[str]=mapped_column(Text); status:Mapped[str]=mapped_column(String(16),index=True,default="pending"); decided_by:Mapped[str|None]=mapped_column(String,nullable=True); created_at:Mapped[object]=mapped_column(DateTime(timezone=True),server_default=func.now()); decided_at:Mapped[object|None]=mapped_column(DateTime(timezone=True),nullable=True)
