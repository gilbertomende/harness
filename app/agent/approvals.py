"""Server-side approval for mutating tool calls.

An approval is bound to one exact (session, tool, arguments) call, can only be granted by an
admin through the API, and is consumed by a single execution. Clients can no longer self-approve.
"""
import json
from datetime import datetime, timezone
from sqlalchemy import select, update
from app.db.core import SessionLocal
from app.db.models import ToolApproval, AuditEvent

def canonical_args(args) -> str:
    return json.dumps(args, sort_keys=True, ensure_ascii=False, separators=(",", ":"))

async def consume_or_request(session_id: str, owner: str, tool: str, args) -> tuple[bool, str | None]:
    """Return (approved, pending_id). Consumes a matching approved grant, else creates/reuses a pending one."""
    a = canonical_args(args)
    async with SessionLocal() as db:
        base = select(ToolApproval).where(ToolApproval.session_id==session_id, ToolApproval.tool==tool, ToolApproval.args==a)
        grant = (await db.execute(base.where(ToolApproval.status=="approved").limit(1))).scalars().first()
        # Conditional UPDATE so a single grant can never be consumed by two concurrent calls.
        if grant and (await db.execute(update(ToolApproval).where(ToolApproval.id==grant.id, ToolApproval.status=="approved").values(status="used"))).rowcount == 1:
            db.add(AuditEvent(actor=owner, action="tool_approval_used", detail={"approval_id": grant.id, "tool": tool}))
            await db.commit()
            return True, None
        pending = (await db.execute(base.where(ToolApproval.status=="pending").limit(1))).scalars().first()
        if not pending:
            pending = ToolApproval(session_id=session_id, requested_by=owner, tool=tool, args=a, status="pending")
            db.add(pending); await db.flush()
            db.add(AuditEvent(actor=owner, action="tool_approval_requested", detail={"approval_id": pending.id, "tool": tool}))
            await db.commit()
        return False, pending.id

async def decide(approval_id: str, approver: str, approve: bool) -> ToolApproval | None:
    async with SessionLocal() as db:
        obj = await db.get(ToolApproval, approval_id)
        if not obj or obj.status != "pending": return None
        obj.status = "approved" if approve else "rejected"
        obj.decided_by = approver; obj.decided_at = datetime.now(timezone.utc)
        db.add(AuditEvent(actor=approver, action=f"tool_approval_{obj.status}", detail={"approval_id": obj.id, "tool": obj.tool}))
        await db.commit()
        return obj

async def list_pending():
    async with SessionLocal() as db:
        rows = (await db.execute(select(ToolApproval).where(ToolApproval.status=="pending").order_by(ToolApproval.created_at))).scalars().all()
    return [{"id":r.id,"session_id":r.session_id,"requested_by":r.requested_by,"tool":r.tool,"args":json.loads(r.args)} for r in rows]
