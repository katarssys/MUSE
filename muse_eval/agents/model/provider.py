"""Optional standard chat-completions transport; no provider/endpoint is assumed.

Not verified against a real Meta provider in this environment. User must supply a
provider-confirmed endpoint/model supporting JSON schema chat responses.
"""
import json
import os
from time import perf_counter
from urllib import request, error
from .base import ModelConfig, ModelResponse, ModelNotConnected, ModelProviderError

class _NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Never forward an authorization header to another destination.
        raise ModelProviderError("MODEL_PROVIDER_REDIRECT_REJECTED")

class ChatCompletionsClient:
    def __init__(self, config, api_key):
        self.config = config
        self._api_key = api_key
        if not api_key:
            raise ModelNotConnected("MODEL_NOT_CONNECTED")

    @classmethod
    def from_environment(cls):
        return cls(ModelConfig.from_environment(),os.environ["MUSE_MODEL_API_KEY"])

    def generate(self, messages, schema, *, timeout_s):
        payload = {"model":self.config.model,"messages":messages,"temperature":self.config.temperature,
                   "max_tokens":self.config.max_output_tokens,
                   "response_format":{"type":"json_schema","json_schema":{"name":"agent_decision","strict":True,"schema":schema}}}
        req=request.Request(self.config.endpoint,data=json.dumps(payload,allow_nan=False).encode(),
                            headers={"Content-Type":"application/json","Authorization":"Bearer "+self._api_key},method="POST")
        started=perf_counter()
        try:
            # Default proxy handling and TLS CA verification stay enabled.
            with request.build_opener(_NoRedirect()).open(req,timeout=timeout_s) as response:
                raw=response.read(1024*1024+1)
            if len(raw)>1024*1024:
                raise ModelProviderError("MODEL_PROVIDER_RESPONSE_TOO_LARGE")
            data=json.loads(raw,parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))
            content=data["choices"][0]["message"]["content"]
            if not isinstance(content,str):
                raise ValueError("No text response")
            returned_model=data.get("model")
            if returned_model is not None and returned_model!=self.config.model:
                raise ModelProviderError("MODEL_PROVIDER_MODEL_MISMATCH")
            usage=data.get("usage")
            counts={}
            for target,source in (("input_tokens","prompt_tokens"),("output_tokens","completion_tokens")):
                value=usage.get(source) if isinstance(usage,dict) else None
                counts[target]=value if type(value) is int and value>=0 else None
            return ModelResponse(content,usage=counts,latency_ms=(perf_counter()-started)*1000,
                                 provider_metadata={"provider":self.config.provider,"model":self.config.model},estimated_cost=None)
        except ModelProviderError:
            raise
        except (error.HTTPError,error.URLError,OSError,ValueError,KeyError,IndexError,TypeError):
            # Do not export provider bodies, headers, raw text or exception messages.
            raise ModelProviderError("MODEL_PROVIDER_REQUEST_FAILED") from None
