import pytest
from cri.llm.gateway import GatewayConfig, ProviderConfig, UniversalLLMGateway, CostLimitExceeded
from cri.llm.adapters import ProviderError

class FakeAdapter:
    def __init__(self, outcomes): self.outcomes=list(outcomes); self.calls=0
    def complete(self,*args):
        self.calls+=1; item=self.outcomes.pop(0)
        if isinstance(item,Exception): raise item
        return item

def config(fallback=None, ceiling=5):
    return GatewayConfig(ProviderConfig("primary","https://primary.test/v1","x"*32,"p-model"),fallback,100,1,1,ceiling,1,1)

def result(tokens=100):
    return {"content":"ok","usage":{"prompt_tokens":tokens,"completion_tokens":0,"total_tokens":tokens},"model":"m","provider":"fake"}

def test_gateway_normalizes_and_audits_without_prompt_or_secret():
    events=[]
    class Audit:
        def add(self,*args): events.append(args)
    adapter=FakeAdapter([result()])
    g=UniversalLLMGateway(config(),adapters={"primary":adapter},audit=Audit())
    out=g.complete([{"role":"user","content":"private prompt"}],actor="unit")
    assert (out.content,out.provider,out.model)==("ok","primary","m")
    assert "private prompt" not in repr(events) and "x"*32 not in repr(events)

def test_gateway_fallback_after_provider_failure():
    fb=ProviderConfig("backup","https://backup.test/v1","y"*32,"b-model")
    primary=FakeAdapter([ProviderError("unavailable",503,True),ProviderError("unavailable",503,True)])
    backup=FakeAdapter([result()])
    g=UniversalLLMGateway(config(fb),adapters={"primary":primary,"backup":backup},sleeper=lambda _:None)
    assert g.complete([{"role":"user","content":"x"}]).provider=="backup"
    assert primary.calls==2 and backup.calls==1

def test_gateway_cost_ceiling_blocks_next_completion():
    adapter=FakeAdapter([result(600000),result(1)])
    g=UniversalLLMGateway(config(ceiling=0.5),adapters={"primary":adapter})
    with pytest.raises(CostLimitExceeded): g.complete([{"role":"user","content":"x"}])

def test_model_registry_metadata_and_validation():
    from cri.llm.registry import ModelInfo, ModelRegistry
    registry=ModelRegistry(); info=ModelInfo("provider","model",8192,2048,True,True)
    registry.register(info)
    assert registry.get("provider","model")==info
    with pytest.raises(ValueError): registry.register(ModelInfo("","bad"))

def test_gateway_retries_only_retryable_provider_error():
    adapter=FakeAdapter([ProviderError("temporary",503,True),result()])
    delays=[]
    g=UniversalLLMGateway(config(),adapters={"primary":adapter},sleeper=delays.append)
    assert g.complete([{"role":"user","content":"x"}]).content=="ok"
    assert adapter.calls==2 and delays==[1]

def test_gateway_health_state_is_metadata_only():
    adapter=FakeAdapter([result()])
    g=UniversalLLMGateway(config(),adapters={"primary":adapter})
    g.complete([{"role":"user","content":"x"}])
    assert g.health.snapshot()["primary"]["healthy"] is True

def test_openai_compatible_adapter_normalizes_response():
    import json
    from cri.llm.adapters import OpenAICompatibleAdapter
    class Response:
        def __enter__(self): return self
        def __exit__(self,*a): return False
        def read(self): return json.dumps({"model":"m","choices":[{"message":{"content":"hello","tool_calls":[{"id":"1"}]}}],"usage":{"prompt_tokens":2,"completion_tokens":3,"total_tokens":5}}).encode()
    adapter=OpenAICompatibleAdapter("k"*32,"m","https://provider.test/v1",opener=lambda *a,**k:Response())
    out=adapter.complete([{"role":"user","content":"x"}],20)
    assert out["content"]=="hello" and out["usage"]["total_tokens"]==5 and out["tool_calls"]

def test_gemini_adapter_normalizes_response():
    import json
    from cri.llm.adapters import GeminiAdapter
    class Response:
        def __enter__(self): return self
        def __exit__(self,*a): return False
        def read(self): return json.dumps({"candidates":[{"content":{"parts":[{"text":"hello"}]}}],"usageMetadata":{"promptTokenCount":2,"candidatesTokenCount":3,"totalTokenCount":5}}).encode()
    adapter=GeminiAdapter("k"*32,"gemini-test","https://gemini.test/v1beta/models",opener=lambda *a,**k:Response())
    out=adapter.complete([{"role":"user","content":"x"}],20)
    assert out["content"]=="hello" and out["usage"]["total_tokens"]==5

def test_anthropic_adapter_normalizes_response():
    import json
    from cri.llm.adapters import AnthropicAdapter
    class Response:
        def __enter__(self): return self
        def __exit__(self,*a): return False
        def read(self): return json.dumps({"model":"claude-test","content":[{"type":"text","text":"hello"}],"usage":{"input_tokens":2,"output_tokens":3}}).encode()
    adapter=AnthropicAdapter("k"*32,"claude-test","https://anthropic.test/v1",opener=lambda *a,**k:Response())
    out=adapter.complete([{"role":"system","content":"rules"},{"role":"user","content":"x"}],20)
    assert out["content"]=="hello" and out["usage"]["total_tokens"]==5

def test_provider_adapter_rejects_http_auth_error_without_retry():
    from urllib.error import HTTPError
    from cri.llm.adapters import OpenAICompatibleAdapter, ProviderError
    def fail(*a,**k): raise HTTPError("https://provider.test",401,"unauthorized",None,None)
    adapter=OpenAICompatibleAdapter("k"*32,"m","https://provider.test/v1",opener=fail)
    with pytest.raises(ProviderError) as err: adapter.complete([{"role":"user","content":"x"}],10)
    assert err.value.status==401 and not err.value.retryable


def test_gateway_rejects_partial_fallback_configuration(monkeypatch):
    from cri.llm.gateway import GatewayError
    monkeypatch.setenv("CRI_LLM_PROVIDER", "openai-compatible")
    monkeypatch.setenv("CRI_LLM_BASE_URL", "https://provider.test/v1")
    monkeypatch.setenv("CRI_LLM_API_KEY", "k" * 32)
    monkeypatch.setenv("CRI_LLM_MODEL", "model")
    monkeypatch.setenv("CRI_LLM_FALLBACK_PROVIDER", "gemini")
    monkeypatch.setenv("CRI_LLM_FALLBACK_BASE_URL", "")
    monkeypatch.setenv("CRI_LLM_FALLBACK_MODEL", "")
    with pytest.raises(GatewayError, match="fallback.*incomplete"):
        GatewayConfig.from_env()


def test_gateway_defaults_empty_provider_and_validates_numeric_settings(monkeypatch):
    from cri.llm.gateway import GatewayError
    monkeypatch.setenv("CRI_LLM_PROVIDER", "")
    monkeypatch.setenv("CRI_LLM_BASE_URL", "https://provider.test/v1")
    monkeypatch.setenv("CRI_LLM_API_KEY", "k" * 32)
    monkeypatch.setenv("CRI_LLM_MODEL", "model")
    monkeypatch.setenv("CRI_LLM_RETRIES", "-1")
    with pytest.raises(GatewayError, match="retries"):
        GatewayConfig.from_env()


def test_gateway_rejects_oversized_or_invalid_message_shapes():
    g = UniversalLLMGateway(config(), adapters={"primary": FakeAdapter([result()])})
    with pytest.raises(ValueError):
        g.complete([{"role": "root", "content": "x"}])
    with pytest.raises(ValueError):
        g.complete([{"role": "user", "content": "x" * 20001}])


def test_gemini_rejects_generic_tool_schema_instead_of_silently_ignoring():
    from cri.llm.adapters import GeminiAdapter, ProviderError
    adapter = GeminiAdapter("k" * 32, "m", "https://gemini.test/v1beta/models", opener=lambda *a, **k: None)
    with pytest.raises(ProviderError, match="tool schemas"):
        adapter.complete([{"role": "user", "content": "x"}], 10, tools=[{"type": "function"}])


def test_anthropic_rejects_generic_tool_schema_instead_of_forwarding_wrong_shape():
    from cri.llm.adapters import AnthropicAdapter, ProviderError
    adapter = AnthropicAdapter("k" * 32, "m", "https://anthropic.test/v1", opener=lambda *a, **k: None)
    with pytest.raises(ProviderError, match="provider-native"):
        adapter.complete([{"role": "user", "content": "x"}], 10, tools=[{"type": "function"}])


def test_gateway_rejects_invalid_direct_config():
    from cri.llm.gateway import GatewayError
    valid_provider = ProviderConfig("openai-compatible", "https://provider.test/v1", "k" * 32, "model")
    invalid = GatewayConfig(valid_provider, None, max_tokens=0)
    with pytest.raises(GatewayError, match="max_tokens"):
        UniversalLLMGateway(invalid)


def test_developer_injected_opener_uses_selected_provider_adapter(monkeypatch):
    from cri.agents.developer import Developer
    from cri.llm.adapters import GeminiAdapter
    monkeypatch.setenv("CRI_LLM_PROVIDER", "gemini")
    monkeypatch.setenv("CRI_LLM_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/models")
    monkeypatch.setenv("CRI_LLM_API_KEY", "k" * 32)
    monkeypatch.setenv("CRI_LLM_MODEL", "gemini-test")
    developer = Developer(opener=lambda *args, **kwargs: None)
    assert isinstance(developer.gateway._adapter(developer.gateway.config.provider), GeminiAdapter)
