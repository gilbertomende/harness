import pytest
from app.llm.router import router, ProvidersUnavailable

@pytest.fixture
def keys(monkeypatch):
    monkeypatch.setitem(router.keys, "openrouter", "sk-test")
    monkeypatch.setitem(router.models, "9router", "")

def test_private_auto_uses_only_local():
    assert [p for p, _ in router.candidates("auto", private=True)] == ["ollama"]

def test_private_explicit_local_allowed():
    assert [p for p, _ in router.candidates("ollama", private=True)] == ["ollama"]

@pytest.mark.parametrize("provider", ["openrouter", "9router"])
def test_private_rejects_remote_provider(provider):
    with pytest.raises(PermissionError): router.candidates(provider, private=True)

def test_non_private_explicit_provider_unchanged(keys):
    assert router.candidates("openrouter", model="m")[0] == ("openrouter", "m")

def test_auto_skips_openrouter_without_key(monkeypatch):
    monkeypatch.setitem(router.keys, "openrouter", "")
    assert "openrouter" not in [p for p, _ in router.candidates("auto")]

def test_auto_includes_openrouter_with_key(keys):
    assert [p for p, _ in router.candidates("auto")] == ["ollama", "openrouter"]

def test_explicit_keyless_openrouter_fails_fast(monkeypatch):
    monkeypatch.setitem(router.keys, "openrouter", "")
    with pytest.raises(ProvidersUnavailable): router.candidates("openrouter")

def test_unknown_provider_rejected():
    with pytest.raises(ValueError): router.candidates("nope")

def test_nothing_configured_is_unavailable(monkeypatch):
    for p in router.models: monkeypatch.setitem(router.models, p, "")
    with pytest.raises(ProvidersUnavailable): router.candidates("auto")

def test_clients_have_bounded_timeout_and_retries():
    from app.config import settings
    for p in router.providers.values():
        assert p.client.timeout == settings.llm_timeout_seconds
        assert p.client.max_retries == settings.llm_max_retries
