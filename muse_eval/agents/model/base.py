"""Provider-neutral model contract and explicit configuration. No default provider."""
from dataclasses import dataclass, field
import os
from typing import Protocol
from urllib.parse import urlsplit

class ModelNotConnected(RuntimeError):
    pass

class ModelProviderError(RuntimeError):
    # Provider-controlled strings are never diagnostics unless explicitly known.
    SAFE_TAGS = frozenset({
        "invalid_request_error", "authentication_error", "permission_error",
        "rate_limit_error", "server_error", "api_error", "validation_error",
        "invalid_api_key", "rate_limit_exceeded", "context_length_exceeded",
        "model_not_found", "invalid_model", "permission_denied", "insufficient_quota",
        "invalid_json_schema", "invalid_schema", "unsupported_schema",
        "unsupported_response_format", "unsupported_parameter", "invalid_parameter",
        "json_schema_validation_error", "bad_request",
        "framing_invalid_json", "framing_no_object", "framing_root_not_object",
        "framing_trailing_content", "shape_root_not_object", "shape_choices_missing",
        "shape_choices_empty", "shape_choice_not_object", "shape_message_missing",
        "shape_content_missing", "shape_content_not_string", "shape_content_null",
        "shape_content_array", "shape_content_object", "shape_content_other",
        "shape_content_null_length", "shape_content_null_tool_calls",
        "shape_content_null_content_filter", "shape_content_null_stop", "shape_content_null_other",
    })

    SAFE_CATEGORIES = frozenset({
        "timeout", "url_error", "connection_error", "response_json_invalid",
        "response_shape_invalid", "http_error", "framing_invalid",
        "model_mismatch", "response_too_large", "redirect_rejected",
    })

    def __init__(self, message, *, http_status=None, error_type=None, error_code=None, category=None):
        super().__init__(message)
        self.category = category if isinstance(category,str) and category in self.SAFE_CATEGORIES else None
        self.http_status = http_status if type(http_status) is int and 100 <= http_status <= 599 else None
        self.error_type = error_type if isinstance(error_type,str) and error_type in self.SAFE_TAGS else None
        self.error_code = (error_code if isinstance(error_code,str) and error_code in self.SAFE_TAGS
                           or type(error_code) is int and 0 <= error_code <= 999999 else None)

    def safe_diagnostics(self):
        return {"category":self.category,"http_status":self.http_status,"error_type":self.error_type,"error_code":self.error_code}

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
    request_timeout_s: float = 30.0

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
