"""Cliente HTTP mínimo para a API local do Ollama."""

import json
import socket
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener


class ModelError(RuntimeError):
    """O modelo local não conseguiu fornecer uma resposta utilizável."""


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
            raise ValueError("Use o endereço HTTP local do Ollama, sem credenciais ou caminhos.")
        if not model.strip() or "cloud" in model.casefold():
            raise ValueError("Escolha um modelo local, sem indicação cloud.")
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        # A comunicação local não deve passar por proxies ou seguir redirecionamentos.
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
                raise ModelError(f"Modelo não encontrado. Execute: ollama pull {self.model}") from None
            raise ModelError(f"O Ollama recusou a solicitação (HTTP {error.code}).") from None
        except (URLError, TimeoutError, socket.timeout, OSError):
            raise ModelError("O Ollama não respondeu. Confira se 'ollama serve' está ativo e tente novamente.") from None
        except (ValueError, UnicodeError):
            raise ModelError("O Ollama retornou uma resposta que não é JSON válido.") from None
        if not isinstance(result, dict) or not isinstance(result.get("message"), dict) or not result.get("done"):
            raise ModelError("Resposta incompleta ou inválida do Ollama.")
        if result.get("done_reason") == "length":
            raise ModelError("O modelo atingiu o limite de saída; reformule a pergunta de forma mais específica.")
        message = result["message"]
        if message.get("role") != "assistant" or not isinstance(message.get("content", ""), str):
            raise ModelError("Mensagem inválida do modelo.")
        content = message.get("content", "")
        # Alguns modelos ainda emitem essas marcas dentro de content, mesmo com think=false.
        if "</think>" in content:
            content = content.rsplit("</think>", 1)[-1].strip()
        if "<think>" in content:
            raise ModelError("O modelo não concluiu uma resposta final utilizável.")
        return {"role": "assistant", "content": content,
                "tool_calls": message.get("tool_calls", [])}
