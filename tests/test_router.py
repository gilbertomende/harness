import pytest
from app.llm.router import router

def test_private_auto_uses_only_local():
    assert [p for p, _ in router.candidates("auto", private=True)] == ["ollama"]

def test_private_explicit_local_allowed():
    assert [p for p, _ in router.candidates("ollama", private=True)] == ["ollama"]

@pytest.mark.parametrize("provider", ["openrouter", "9router"])
def test_private_rejects_remote_provider(provider):
    with pytest.raises(PermissionError): router.candidates(provider, private=True)

def test_non_private_explicit_provider_unchanged():
    assert router.candidates("openrouter", model="m")[0] == ("openrouter", "m")
