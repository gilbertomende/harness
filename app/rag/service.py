from sqlalchemy import select
from app.db.core import SessionLocal
from app.db.models import DocumentChunk
from app.llm.router import router
from app.config import settings

def chunks(text: str, size=1200, overlap=150):
    out=[]; i=0
    while i < len(text):
        out.append(text[i:i+size]); i += max(1, size-overlap)
    return out

async def ingest(source: str, text: str):
    parts = chunks(text); provider = router.get(settings.embed_provider)
    vectors = await provider.embed(model=settings.embed_model, texts=parts)
    async with SessionLocal() as db:
        for c, v in zip(parts, vectors): db.add(DocumentChunk(source=source, content=c, embedding=v))
        await db.commit()
    return len(parts)

async def search(query: str, k=5):
    provider = router.get(settings.embed_provider)
    qv = (await provider.embed(model=settings.embed_model, texts=[query]))[0]
    async with SessionLocal() as db:
        stmt = select(DocumentChunk).order_by(DocumentChunk.embedding.cosine_distance(qv)).limit(k)
        rows = (await db.execute(stmt)).scalars().all()
    return [{"source":r.source,"content":r.content} for r in rows]
