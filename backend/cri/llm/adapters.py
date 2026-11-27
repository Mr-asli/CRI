"""HTTP provider adapters; all return the gateway's normalized response shape."""
import json
from urllib.parse import quote
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

class ProviderError(RuntimeError):
    def __init__(self, message, status=None, retryable=False):
        super().__init__(message); self.status=status; self.retryable=retryable

class BaseAdapter:
    def __init__(self, api_key, model, base_url, timeout=60, opener=urlopen):
        self.api_key, self.model = api_key, model
        self.base_url, self.timeout, self.opener = base_url.rstrip("/"), timeout, opener
        if not self.api_key or not self.model or not self.base_url.startswith("https://"):
            raise ValueError("provider requires API key, model and HTTPS base URL")
    def _post(self, url, payload, headers):
        request = Request(url, data=json.dumps(payload).encode(), headers={**headers, "Content-Type":"application/json"}, method="POST")
        try:
            with self.opener(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            retryable = exc.code in (408, 425, 429, 500, 502, 503, 504)
            exc.close()
            raise ProviderError("provider HTTP request failed", exc.code, retryable) from None
        except (URLError, TimeoutError, OSError) as exc:
            raise ProviderError("provider transport failed", None, True) from None
        except (ValueError, UnicodeError) as exc:
            raise ProviderError("provider returned invalid JSON") from None

class OpenAICompatibleAdapter(BaseAdapter):
    provider = "openai-compatible"
    def complete(self, messages, max_tokens, json_mode=False, tools=None):
        payload={"model":self.model,"messages":messages,"max_tokens":max_tokens,"temperature":0.1}
        if json_mode: payload["response_format"]={"type":"json_object"}
        if tools: payload["tools"]=tools
        data=self._post(self.base_url if self.base_url.endswith("/chat/completions") else self.base_url+"/chat/completions", payload, {"Authorization":"Bearer "+self.api_key})
        try:
            choice=data["choices"][0]["message"]
            content=choice.get("content") or ""
            calls=choice.get("tool_calls")
            usage=data.get("usage") or {}
            return {"content":content,"usage":{"prompt_tokens":int(usage.get("prompt_tokens",0)),"completion_tokens":int(usage.get("completion_tokens",0)),"total_tokens":int(usage.get("total_tokens",0))},"model":data.get("model",self.model),"provider":self.provider,"tool_calls":calls}
        except (KeyError,IndexError,TypeError,ValueError): raise ProviderError("provider response schema invalid") from None

class GeminiAdapter(BaseAdapter):
    provider = "gemini"
    def complete(self, messages, max_tokens, json_mode=False, tools=None):
        if tools:
            raise ProviderError("Gemini tool schemas are not supported by this adapter", retryable=False)
        contents=[]; system=[]
        for m in messages:
            if m.get("role")=="system": system.append(m.get("content","")); continue
            contents.append({"role":"model" if m.get("role")=="assistant" else "user","parts":[{"text":str(m.get("content",""))}]})
        payload={"contents":contents,"generationConfig":{"maxOutputTokens":max_tokens,"temperature":0.1}}
        if system: payload["systemInstruction"]={"parts":[{"text":"\n".join(system)}]}
        if json_mode: payload["generationConfig"]["responseMimeType"]="application/json"
        base=self.base_url
        if base.endswith("/models"): url=base+"/"+self.model+":generateContent?key="+quote(self.api_key,safe="")
        else: url=base+":"+"generateContent?key="+quote(self.api_key,safe="")
        data=self._post(url,payload,{})
        try:
            content="".join(p.get("text","") for p in data["candidates"][0]["content"]["parts"])
            u=data.get("usageMetadata",{})
            return {"content":content,"usage":{"prompt_tokens":int(u.get("promptTokenCount",0)),"completion_tokens":int(u.get("candidatesTokenCount",0)),"total_tokens":int(u.get("totalTokenCount",0))},"model":self.model,"provider":self.provider,"tool_calls":None}
        except (KeyError,IndexError,TypeError,ValueError): raise ProviderError("Gemini response schema invalid") from None

class AnthropicAdapter(BaseAdapter):
    provider = "anthropic"
    def complete(self, messages, max_tokens, json_mode=False, tools=None):
        if tools:
            raise ProviderError("Anthropic requires provider-native tool schemas; generic tools are not supported", retryable=False)
        system="\n".join(str(m.get("content","")) for m in messages if m.get("role")=="system")
        msgs=[m for m in messages if m.get("role")!="system"]
        payload={"model":self.model,"max_tokens":max_tokens,"messages":msgs}
        if system: payload["system"]=system
        if tools: payload["tools"]=tools
        data=self._post(self.base_url if self.base_url.endswith("/messages") else self.base_url+"/messages",payload,{"x-api-key":self.api_key,"anthropic-version":"2023-06-01"})
        try:
            content="".join(x.get("text","") for x in data.get("content",[]) if x.get("type")=="text")
            u=data.get("usage",{})
            return {"content":content,"usage":{"prompt_tokens":int(u.get("input_tokens",0)),"completion_tokens":int(u.get("output_tokens",0)),"total_tokens":int(u.get("input_tokens",0))+int(u.get("output_tokens",0))},"model":data.get("model",self.model),"provider":self.provider,"tool_calls":[x for x in data.get("content",[]) if x.get("type")=="tool_use"] or None}
        except (TypeError,ValueError): raise ProviderError("Anthropic response schema invalid") from None
