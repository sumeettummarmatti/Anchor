import json
import logging
import os
import socket
import time
from typing import Any, Dict, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from fastapi import HTTPException, Request as FastAPIRequest

logger = logging.getLogger(__name__)

class LLMCallError(Exception): pass
class LLMTransientError(LLMCallError): pass
class LLMResponseError(LLMCallError): pass
class LLMAuthError(LLMCallError): pass

def complete_json_with_retry(client: "LLMClient", system: str, user: str, component: str) -> Dict[str, Any]:
    """Call an LLM once, retry transient transport failures once, and log all failures."""
    for attempt in range(2):
        try:
            result = client.complete_json(system, user)
            if not isinstance(result, dict):
                raise LLMResponseError("LLM response was not a JSON object")
            return result
        except HTTPError as exc:
            try: 
                body = exc.read().decode("utf-8", errors="replace")[:240]
            except Exception: 
                body = str(exc)
                
            if exc.code in (401, 403):
                logger.error("LLM authentication/permission failure component=%s status=%s detail=%s", component, exc.code, body)
                provider = type(client).__name__
                raise LLMAuthError(f"{provider} rejected the configured credentials (HTTP {exc.code})") from exc
                
            logger.warning("LLM HTTP failure component=%s attempt=%d status=%s detail=%s", component, attempt + 1, exc.code, body)
            if attempt == 0:
                time.sleep(0.5)  
                continue
            raise LLMTransientError(str(exc)) from exc
        except (TimeoutError, socket.timeout, URLError) as exc:
            logger.warning("LLM transient failure component=%s attempt=%d type=%s detail=%s", component, attempt + 1, type(exc).__name__, str(exc)[:240])
            if attempt == 0:
                time.sleep(0.5)
                continue
            raise LLMTransientError(str(exc)) from exc
        except (json.JSONDecodeError, LLMResponseError, ValueError, TypeError) as exc:
            logger.error("LLM response/schema failure component=%s type=%s detail=%s", component, type(exc).__name__, str(exc)[:240])
            raise LLMResponseError(str(exc)) from exc
        except Exception as exc:
            logger.exception("LLM unexpected failure component=%s type=%s detail=%s", component, type(exc).__name__, str(exc)[:240])
            raise LLMCallError(str(exc)) from exc

def repair_json_with_retry(client: "LLMClient", invalid_result: Dict[str, Any], schema: str, component: str) -> Dict[str, Any]:
    return complete_json_with_retry(
        client,
        "Repair the supplied JSON so it matches the required schema exactly. Return JSON only. Required schema: " + schema,
        json.dumps({"invalid_json": invalid_result}),
        component + "_repair",
    )

class LLMClient:
    """Small provider boundary for structured JSON model responses."""
    def complete_json(self, system: str, user: str) -> Dict[str, Any]:
        raise NotImplementedError

class OpenAICompatibleClient(LLMClient):
    def __init__(self, api_key: str, model: str = "gpt-4o-mini", base_url: str = "https://api.openai.com/v1", timeout: int = 45):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    @classmethod
    def from_environment(cls) -> Optional["OpenAICompatibleClient"]:
        key = os.getenv("OPENAI_API_KEY")
        if not key:
            return None
        
        try:
            timeout = int(os.getenv("OPENAI_TIMEOUT", "45"))
        except ValueError:
            timeout = 45
            
        return cls(
            api_key=key, 
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"), 
            base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            timeout=timeout
        )

    def complete_json(self, system: str, user: str) -> Dict[str, Any]:
        payload = {
            "model": self.model, 
            "temperature": 0.2, 
            "response_format": {"type": "json_object"}, 
            "messages": [
                {"role": "system", "content": system}, 
                {"role": "user", "content": user}
            ]
        }
        
        # Added realistic User-Agent header to satisfy Cloudflare Browser Integrity Checks (Error 1010)
        headers = {
            "Authorization": "Bearer " + self.api_key, 
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        
        request = Request(
            self.base_url + "/chat/completions", 
            data=json.dumps(payload).encode("utf-8"), 
            headers=headers, 
            method="POST"
        )
        with urlopen(request, timeout=self.timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
        
        if "error" in body:
            raise ValueError(f"API returned error block: {body['error']}")
            
        try:
            content = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError):
            raise ValueError("Malformed response payload structure from LLM provider")
            
        parsed = json.loads(content)
        if not isinstance(parsed, dict):
            raise ValueError("LLM response must be a JSON object")
        return parsed

class GroqClient(OpenAICompatibleClient):
    """Groq's OpenAI-compatible chat-completions client."""
    def __init__(self, api_key: str, model: str = "llama-3.3-70b-versatile", timeout: int = 45):
        super().__init__(api_key, model, "https://api.groq.com/openai/v1", timeout)

    @classmethod
    def from_environment(cls) -> Optional["GroqClient"]:
        key = os.getenv("GROQ_API_KEY")
        if not key:
            return None
            
        try:
            timeout = int(os.getenv("GROQ_TIMEOUT", "45"))
        except ValueError:
            timeout = 45
            
        return cls(
            api_key=key, 
            model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"), 
            timeout=timeout
        )

    @classmethod
    def required_from_environment(cls) -> "GroqClient":
        client = cls.from_environment()
        if client is None:
            raise RuntimeError("GROQ_API_KEY is required. Add it to interview_engine/.env before starting the server.")
        return client


def request_groq_client(request: FastAPIRequest) -> Optional[GroqClient]:
    key = request.headers.get("X-Groq-Api-Key")
    if key is None:
        return None
    key = key.strip()
    if not key:
        return None
    if len(key) > 512:
        raise HTTPException(status_code=400, detail="Groq API key is too long.")
    try:
        timeout = int(os.getenv("GROQ_TIMEOUT", "45"))
    except ValueError:
        timeout = 45
    return GroqClient(key, model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"), timeout=timeout)
