import os, threading, time, logging
from dataclasses import dataclass
from .adapters import OpenAICompatibleAdapter, GeminiAdapter, AnthropicAdapter, ProviderError
from .registry import ModelRegistry, ModelInfo

log=logging.getLogger("cri.llm")
class GatewayError(RuntimeError): pass
class CostLimitExceeded(GatewayError): pass

@dataclass(frozen=True)
class LLMResult:
    content: str
    usage: dict
    model: str
    provider: str
    tool_calls: object = None

@dataclass(frozen=True)
class ProviderConfig:
    name: str; base_url: str; api_key: str; model: str

@dataclass(frozen=True)
class GatewayConfig:
    provider: ProviderConfig
    fallback: ProviderConfig | None
    max_tokens: int=4096
    timeout: float=60
    retries: int=2
    max_cost_usd: float=5.0
    input_cost_per_million: float=0.0
    output_cost_per_million: float=0.0
    @classmethod
    def from_env(cls):
        def value(name, default=""):
            return os.getenv(name, default).strip()

        name = value("CRI_LLM_PROVIDER", "openai-compatible").lower() or "openai-compatible"
        base, key, model = (value("CRI_LLM_BASE_URL"), value("CRI_LLM_API_KEY"), value("CRI_LLM_MODEL"))
        if not all((base, key, model)):
            raise GatewayError("primary LLM provider configuration incomplete")
        primary = ProviderConfig(name, base, key, model)

        fallback_values = {
            "provider": value("CRI_LLM_FALLBACK_PROVIDER").lower(),
            "base_url": value("CRI_LLM_FALLBACK_BASE_URL"),
            "model": value("CRI_LLM_FALLBACK_MODEL"),
            "api_key": value("CRI_LLM_FALLBACK_API_KEY") or key,
        }
        configured = any((fallback_values["provider"], fallback_values["base_url"], fallback_values["model"]))
        if configured and not all((fallback_values["provider"], fallback_values["base_url"], fallback_values["model"], fallback_values["api_key"])):
            raise GatewayError("fallback LLM provider configuration incomplete")
        fallback = ProviderConfig(**fallback_values) if configured else None

        try:
            config = cls(
                primary, fallback,
                int(value("CRI_LLM_MAX_TOKENS", "4096")),
                float(value("CRI_LLM_TIMEOUT", "60")),
                int(value("CRI_LLM_RETRIES", "2")),
                float(value("CRI_LLM_MAX_COST_USD", "5")),
                float(value("CRI_LLM_INPUT_COST_PER_MILLION", "0")),
                float(value("CRI_LLM_OUTPUT_COST_PER_MILLION", "0")),
            )
        except ValueError as exc:
            raise GatewayError("invalid LLM gateway numeric configuration") from exc
        config.validate()
        return config

    def validate(self, custom_provider_names=()):
        supported = {"openrouter", "openai-compatible", "openai", "gemini", "anthropic", *custom_provider_names}
        for provider in (self.provider, self.fallback):
            if provider is None:
                continue
            if provider.name not in supported:
                raise GatewayError("unsupported LLM provider")
            if not all(isinstance(v, str) and v.strip() for v in (provider.name, provider.base_url, provider.api_key, provider.model)):
                raise GatewayError("incomplete LLM provider configuration")
            if not provider.base_url.startswith("https://"):
                raise GatewayError("LLM provider endpoint must use HTTPS")
        if not isinstance(self.max_tokens, int) or not 1 <= self.max_tokens <= 131072:
            raise GatewayError("LLM max_tokens must be between 1 and 131072")
        if not isinstance(self.timeout, (int, float)) or not 1 <= self.timeout <= 300:
            raise GatewayError("LLM timeout must be between 1 and 300 seconds")
        if not isinstance(self.retries, int) or not 0 <= self.retries <= 5:
            raise GatewayError("LLM retries must be between 0 and 5")
        for rate in (self.max_cost_usd, self.input_cost_per_million, self.output_cost_per_million):
            if not isinstance(rate, (int, float)) or rate < 0:
                raise GatewayError("LLM cost settings must be non-negative numbers")

class CostLimiter:
    """Process-local conservative budget counter. Use one gateway worker or inject shared durable limiter."""
    def __init__(self, ceiling): self.ceiling=ceiling; self.spent=0.0; self.lock=threading.Lock()
    def charge(self, usage, input_rate, output_rate):
        cost=(usage.get("prompt_tokens",0)*input_rate+usage.get("completion_tokens",0)*output_rate)/1_000_000
        with self.lock:
            if self.spent+cost > self.ceiling: raise CostLimitExceeded("configured LLM cost ceiling reached")
            self.spent+=cost
            return self.spent

class HealthChecker:
    def __init__(self): self._state={}; self._lock=threading.Lock()
    def record(self, provider, healthy):
        with self._lock: self._state[provider]={"healthy":bool(healthy),"checked_at":time.time()}
    def snapshot(self):
        with self._lock: return {k:dict(v) for k,v in self._state.items()}

class UniversalLLMGateway:
    def __init__(self, config=None, adapters=None, audit=None, registry=None, sleeper=time.sleep):
        self.config=config or GatewayConfig.from_env(); self.adapters=adapters or {}; self.config.validate(self.adapters.keys()); self.audit=audit; self.sleeper=sleeper
        self.registry=registry or ModelRegistry(); self.health=HealthChecker(); self.cost=CostLimiter(self.config.max_cost_usd)
        for c in (self.config.provider,self.config.fallback):
            if c: self.registry.register(ModelInfo(c.name,c.model))
    def _adapter(self,c):
        if c.name in self.adapters: return self.adapters[c.name]
        classes={"openrouter":OpenAICompatibleAdapter,"openai":OpenAICompatibleAdapter,"openai-compatible":OpenAICompatibleAdapter,"gemini":GeminiAdapter,"anthropic":AnthropicAdapter}
        cls=classes.get(c.name)
        if cls is None: raise GatewayError("unsupported LLM provider")
        return cls(c.api_key,c.model,c.base_url,self.config.timeout)
    def _request_provider(self,c,messages,json_mode,tools):
        adapter=self._adapter(c)
        for attempt in range(self.config.retries+1):
            try:
                raw=adapter.complete(messages,self.config.max_tokens,json_mode,tools)
                if not isinstance(raw,dict) or not isinstance(raw.get("content"),str) or not isinstance(raw.get("usage"),dict): raise GatewayError("normalized provider response invalid")
                raw["provider"]=c.name; raw["model"]=raw.get("model") or c.model
                self.cost.charge(raw["usage"],self.config.input_cost_per_million,self.config.output_cost_per_million)
                self.health.record(c.name,True)
                return LLMResult(raw["content"],raw["usage"],raw["model"],raw["provider"],raw.get("tool_calls"))
            except ProviderError as exc:
                if not exc.retryable or attempt>=self.config.retries: raise
                self.sleeper(min(2**attempt,8))
        raise GatewayError("provider retries exhausted")
    def complete(self,messages,*,json_mode=False,tools=None,actor="system"):
        if not isinstance(messages,list) or not messages or len(messages)>100: raise ValueError("messages must be a non-empty bounded list")
        for message in messages:
            if not isinstance(message, dict) or message.get("role") not in {"system", "user", "assistant", "tool"}:
                raise ValueError("each message must have a supported role")
            content = message.get("content", "")
            if not isinstance(content, (str, list)) or len(str(content)) > 20000:
                raise ValueError("message content must be bounded text or structured content")
        providers=[self.config.provider]+([self.config.fallback] if self.config.fallback else [])
        failures=[]
        for c in providers:
            try:
                result=self._request_provider(c,messages,json_mode,tools)
            except CostLimitExceeded:
                self._audit("llm.request.denied.cost_limit",actor,{})
                raise
            except Exception as exc:
                self.health.record(c.name,False); failures.append(type(exc).__name__)
                self._audit("llm.provider.failed",actor,{"provider":c.name,"error_type":type(exc).__name__})
                continue
            # Audit failure is not treated as provider failure and must not trigger a duplicate fallback request.
            self._audit("llm.request.succeeded",actor,{"provider":result.provider,"model":result.model,"total_tokens":result.usage.get("total_tokens",0)})
            return result
        raise GatewayError("all configured LLM providers failed: "+", ".join(failures))
    def _audit(self,event,actor,details):
        if self.audit is not None: self.audit.add(event,actor,details)
