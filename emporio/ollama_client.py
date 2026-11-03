"""Minimal HTTP client for the local Ollama API."""

import json
import socket
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener


class ModelError(RuntimeError):
    """The local model could not produce a usable response."""


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class OllamaClient:
    def __init__(self, model="qwen3:4b-instruct", base_url="http://127.0.0.1:11434", timeout=120):
        parsed = urlparse(base_url)
        port = parsed.port
        if (parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
                or parsed.username or parsed.password or parsed.path not in {"", "/"}
                or parsed.query or parsed.fragment or port == 0):
            raise ValueError("Use a local Ollama HTTP address without credentials or paths.")
        if not model.strip() or "cloud" in model.casefold():
            raise ValueError("Choose a local model without a cloud designation.")
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        # Local requests must not use proxies or follow redirects.
        self._opener = build_opener(ProxyHandler({}), _NoRedirect())

    def chat(self, messages: list[dict], tools: list[dict]) -> dict:
        payload = {"model": self.model, "messages": messages, "tools": tools,
                   "stream": False, "think": False, "keep_alive": "5m",
                   "options": {"temperature": 0, "num_ctx": 8192, "num_predict": 1024}}
        request = Request(self.base_url + "/api/chat",
                          data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                          headers={"Content-Type": "application/json"}, method="POST")
        try:
            with self._opener.open(request, timeout=self.timeout) as response:
                result = json.load(response)
        except HTTPError as error:
            if error.code == 404:
                raise ModelError(f"Model not found. Run: ollama pull {self.model}") from None
            raise ModelError(f"Ollama rejected the request (HTTP {error.code}).") from None
        except (URLError, TimeoutError, socket.timeout, OSError):
            raise ModelError("Ollama did not respond. Check that 'ollama serve' is running and try again.") from None
        except (ValueError, UnicodeError):
            raise ModelError("Ollama returned an invalid JSON response.") from None
        if not isinstance(result, dict) or not isinstance(result.get("message"), dict) or not result.get("done"):
            raise ModelError("Incomplete or invalid Ollama response.")
        if result.get("done_reason") == "length":
            raise ModelError("The model reached the output limit; make your question more specific.")
        message = result["message"]
        if message.get("role") != "assistant" or not isinstance(message.get("content", ""), str):
            raise ModelError("Invalid model message.")
        content = message.get("content", "")
        # Some models emit these markers inside content even with think=false.
        if "</think>" in content:
            content = content.rsplit("</think>", 1)[-1].strip()
        if "<think>" in content:
            raise ModelError("The model did not produce a usable final answer.")
        return {"role": "assistant", "content": content,
                "tool_calls": message.get("tool_calls", [])}
