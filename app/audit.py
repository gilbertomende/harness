"""Security audit events (SECURITY.md §10). Never pass prompts, secrets or raw tool arguments here:
use identifiers and hashes (see args_digest)."""
import hashlib, json, logging
from app.db.core import SessionLocal
from app.db.models import AuditEvent
log = logging.getLogger("audit")

def args_digest(args) -> str:
    return hashlib.sha256(json.dumps(args, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()[:16]

async def audit(actor: str, action: str, **detail):
    try:
        async with SessionLocal() as db:
            db.add(AuditEvent(actor=actor, action=action, detail=detail)); await db.commit()
    except Exception:  # auditing must not break the request, but a lost event must be visible
        log.exception("audit_write_failed action=%s actor=%s", action, actor)
