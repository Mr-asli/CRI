from dataclasses import dataclass

@dataclass(frozen=True)
class ModelInfo:
    provider: str
    model: str
    context_tokens: int = 32768
    max_output_tokens: int = 4096
    json_mode: bool = False
    tools: bool = False

class ModelRegistry:
    def __init__(self): self._models = {}
    def register(self, info: ModelInfo):
        if not info.provider or not info.model or info.context_tokens < 1 or info.max_output_tokens < 1:
            raise ValueError("invalid model metadata")
        self._models[(info.provider, info.model)] = info
    def get(self, provider, model): return self._models.get((provider, model))
    def all(self): return tuple(self._models.values())
