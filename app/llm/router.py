import logging, time
from app.config import settings
from app.llm.provider import OpenAICompatible
log = logging.getLogger("model_router")
LOCAL_PROVIDERS = ("ollama",)
KEY_REQUIRED = {"openrouter"}  # hosted providers that always reject requests without an API key

class ProvidersUnavailable(RuntimeError):
    """No configured provider could serve the request (infrastructure, not a client error)."""

class Router:
    def __init__(self):
        self.providers = {
            "ollama": OpenAICompatible(settings.ollama_base_url, settings.ollama_api_key),
            "openrouter": OpenAICompatible(settings.openrouter_base_url, settings.openrouter_api_key),
            "9router": OpenAICompatible(settings.router9_base_url, settings.router9_api_key),
        }
        self.models = {"ollama":settings.ollama_model,"openrouter":settings.openrouter_model,"9router":settings.router9_model}
        self.keys = {"ollama":settings.ollama_api_key,"openrouter":settings.openrouter_api_key,"9router":settings.router9_api_key}

    def configured(self, name):
        return bool(self.models.get(name)) and (name not in KEY_REQUIRED or bool(self.keys.get(name)))

    def get(self, name):
        if name not in self.providers: raise ValueError(f"Unknown provider: {name}")
        return self.providers[name]

    def candidates(self, requested="auto", model=None, private=False):
        local_only = private or not settings.cloud_providers_enabled
        if local_only and requested not in ("auto", *LOCAL_PROVIDERS):
            why = "Private requests" if private else "Cloud providers are disabled (CLOUD_PROVIDERS_ENABLED=false); requests"
            raise PermissionError(f"{why} may only use local providers: {', '.join(LOCAL_PROVIDERS)}")
        if requested != "auto":
            self.get(requested)
            if requested in KEY_REQUIRED and not self.keys.get(requested):
                raise ProvidersUnavailable(f"{requested}: API key not configured")
            return [(requested, model or self.models.get(requested) or settings.default_model)]
        order = list(LOCAL_PROVIDERS) if local_only else ["ollama","9router","openrouter"]
        found = [(p, model or self.models[p]) for p in order if self.configured(p)]
        if not found: raise ProvidersUnavailable("No model provider configured")
        return found

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
        raise ProvidersUnavailable("All model providers failed: " + " | ".join(errors))
router=Router()
