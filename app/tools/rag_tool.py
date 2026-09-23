import json
from app.rag.service import search
from app.tools.registry import registry

async def rag_search(query: str, k: int = 5):
    return json.dumps(await search(query, k), ensure_ascii=False)

registry.register("rag_search","Semantic search over the private knowledge base",
 {"type":"object","properties":{"query":{"type":"string"},"k":{"type":"integer","minimum":1,"maximum":10}},"required":["query"]},
 rag_search)
