from sqlalchemy import select
from app.db.core import SessionLocal
from app.db.models import DocumentChunk, EMBEDDING_DIM
from app.llm.router import router, ProvidersUnavailable
from app.config import settings

def chunks(text: str, size=1200, overlap=150):
    out=[]; i=0
    while i < len(text):
        out.append(text[i:i+size]); i += max(1, size-overlap)
    return [c for c in out if c.strip()]

async def embed(texts: list[str]) -> list[list[float]]:
    """Embed via the configured provider; backend failures and dimension mismatches become ProvidersUnavailable."""
    try:
        vectors = await router.get(settings.embed_provider).embed(model=settings.embed_model, texts=texts)
    except Exception as e:
        raise ProvidersUnavailable(f"Embedding provider {settings.embed_provider} failed ({settings.embed_model}): {e}") from e
    if len(vectors) != len(texts) or any(len(v) != EMBEDDING_DIM for v in vectors):
        dims = sorted({len(v) for v in vectors})
        raise ProvidersUnavailable(f"Embedding model {settings.embed_model} returned dims {dims}; document_chunks expects {EMBEDDING_DIM}")
    return vectors

async def ingest(source: str, text: str):
    parts = chunks(text)
    if not parts: raise ValueError("Nothing to ingest: text is empty")
    vectors = await embed(parts)
    async with SessionLocal() as db:
        for c, v in zip(parts, vectors): db.add(DocumentChunk(source=source, content=c, embedding=v))
        await db.commit()
    return len(parts)

async def search(query: str, k=5):
    k = min(max(int(k), 1), 10)
    qv = (await embed([query]))[0]
    async with SessionLocal() as db:
        stmt = select(DocumentChunk).order_by(DocumentChunk.embedding.cosine_distance(qv)).limit(k)
        rows = (await db.execute(stmt)).scalars().all()
    return [{"source":r.source,"content":r.content} for r in rows]
