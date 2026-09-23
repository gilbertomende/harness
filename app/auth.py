from datetime import datetime, timedelta, timezone
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from app.config import settings

bearer = HTTPBearer(auto_error=False)
class Principal(BaseModel):
    sub: str
    role: str = "user"

def create_token(sub: str, role: str = "admin"):
    now = datetime.now(timezone.utc)
    payload = {"sub": sub, "role": role, "iat": now, "exp": now + timedelta(minutes=settings.access_token_minutes)}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)

def current_user(creds: HTTPAuthorizationCredentials = Depends(bearer)) -> Principal:
    if not creds: raise HTTPException(401, "Bearer token required")
    try:
        p = jwt.decode(creds.credentials, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        return Principal(sub=p["sub"], role=p.get("role","user"))
    except Exception: raise HTTPException(401, "Invalid or expired token")

def require_admin(user: Principal = Depends(current_user)):
    if user.role != "admin": raise HTTPException(403, "Admin role required")
    return user
