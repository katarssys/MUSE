"""Provider-neutral model contract and explicit configuration. No default provider."""
from dataclasses import dataclass, field
import os
from typing import Protocol
from urllib.parse import urlsplit

class ModelNotConnected(RuntimeError):
    pass

class ModelProviderError(RuntimeError):
    pass

@dataclass(frozen=True)
class ModelConfig:
    provider: str
    model: str
    endpoint: str
    family: str = "meta_llama"
    temperature: float = 0.0
    max_output_tokens: int = 2048
    max_model_calls: int = 8
    max_tool_calls: int = 8
    max_context_chars: int = 24000
    workflow_timeout_ms: int = 60000
    request_timeout_s: float = 15.0

    def __post_init__(self):
        url = urlsplit(self.endpoint)
        if url.scheme != "https" or not url.hostname or url.username or url.password or url.query or url.fragment:
            raise ValueError("An explicit HTTPS chat-completions endpoint without credentials/query is required")
        if not self.provider or not self.model or self.family not in ("meta_llama", "meta_muse"):
            raise ValueError("Explicit provider and model required; family must be meta_llama or meta_muse")
        if not all(type(v) is int and v > 0 for v in (self.max_output_tokens,self.max_model_calls,self.max_tool_calls,self.max_context_chars,self.workflow_timeout_ms)):
            raise ValueError("Invalid limits")
        if not 0 <= self.temperature <= 2 or not 0 < self.request_timeout_s <= 60:
            raise ValueError("Invalid generation settings")

    @classmethod
    def from_environment(cls):
        names = ("MUSE_MODEL_PROVIDER", "MUSE_MODEL_ID", "MUSE_MODEL_ENDPOINT", "MUSE_MODEL_FAMILY")
        if not all(os.environ.get(k) for k in names):
            raise ModelNotConnected("MODEL_NOT_CONNECTED")
        if not os.environ.get("MUSE_MODEL_API_KEY"):
            raise ModelNotConnected("MODEL_NOT_CONNECTED")
        return cls(provider=os.environ[names[0]],model=os.environ[names[1]],
                   endpoint=os.environ[names[2]],family=os.environ[names[3]])

    def public_settings(self):
        # Endpoint/credential never enter prompts, traces or manifests.
        return {k:v for k,v in self.__dict__.items() if k != "endpoint"}

@dataclass
class ModelResponse:
    text: str = ""
    structured_output: dict | None = None
    usage: dict | None = None
    latency_ms: float | None = None
    provider_metadata: dict = field(default_factory=dict)
    estimated_cost: float | None = None

class ModelClient(Protocol):
    config: ModelConfig
    def generate(self, messages: list[dict], schema: dict, *, timeout_s: float) -> ModelResponse: ...
