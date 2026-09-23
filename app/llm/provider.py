from openai import AsyncOpenAI

class OpenAICompatible:
    def __init__(self, base_url: str, api_key: str):
        self.client = AsyncOpenAI(base_url=base_url, api_key=api_key or "not-set")

    async def chat(self, *, model, messages, tools=None):
        kwargs = {"model": model, "messages": messages}
        if tools: kwargs["tools"] = tools
        return await self.client.chat.completions.create(**kwargs)

    async def embed(self, *, model, texts):
        r = await self.client.embeddings.create(model=model, input=texts)
        return [x.embedding for x in r.data]
