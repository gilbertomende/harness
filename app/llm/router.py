import logging, time
from app.config import settings
from app.llm.provider import OpenAICompatible
log = logging.getLogger("model_router")
LOCAL_PROVIDERS = ("ollama",)

class Router:
    def __init__(self):
        self.providers = {
            "ollama": OpenAICompatible(settings.ollama_base_url, settings.ollama_api_key),
            "openrouter": OpenAICompatible(settings.openrouter_base_url, settings.openrouter_api_key),
            "9router": OpenAICompatible(settings.router9_base_url, settings.router9_api_key),
        }
        self.models = {"ollama":settings.ollama_model,"openrouter":settings.openrouter_model,"9router":settings.router9_model}

    def get(self, name):
        if name not in self.providers: raise ValueError(f"Unknown provider: {name}")
        return self.providers[name]

    def candidates(self, requested="auto", model=None, private=False):
        if private and requested not in ("auto", *LOCAL_PROVIDERS):
            raise PermissionError(f"Private requests may only use local providers: {', '.join(LOCAL_PROVIDERS)}")
        if requested != "auto": return [(requested, model or self.models.get(requested) or settings.default_model)]
        order = list(LOCAL_PROVIDERS) if private else ["ollama","9router","openrouter"]
        return [(p, model or self.models[p]) for p in order if self.models.get(p)]

    async def chat(self, *, requested="auto", model=None, messages, tools=None, private=False):
        errors=[]
        for provider, selected_model in self.candidates(requested, model, private):
            started=time.monotonic()
            try:
                result=await self.get(provider).chat(model=selected_model,messages=messages,tools=tools)
                log.info("provider=%s model=%s latency_ms=%d",provider,selected_model,int((time.monotonic()-started)*1000))
                return result, provider, selected_model
            except Exception as e:
                errors.append(f"{provider}: {e}"); log.warning("provider_failed=%s error=%s",provider,e)
        raise RuntimeError("All model providers failed: " + " | ".join(errors))
router=Router()
