"""Provider-neutral LLM gateway. Credentials and routing remain server-owned."""
from .gateway import UniversalLLMGateway, GatewayConfig, LLMResult, GatewayError, CostLimitExceeded, ProviderConfig
from .registry import ModelRegistry, ModelInfo
__all__ = ["UniversalLLMGateway", "GatewayConfig", "LLMResult", "GatewayError", "CostLimitExceeded", "ProviderConfig", "ModelRegistry", "ModelInfo"]
