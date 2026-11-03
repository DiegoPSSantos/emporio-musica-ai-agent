"""Conversa no terminal com modelo local e ferramentas de consulta controladas."""

import argparse
import json
import os
from pathlib import Path
from typing import Callable, Optional

from emporio.data import DEFAULT_DATA_DIR, DataValidationError, load_dataset
from emporio.ollama_client import ModelError, OllamaClient
from emporio.policies import PolicyIndexError, load_policies
from emporio.tools import TOOL_SCHEMAS, Toolbox
from emporio.text import normalize_text


SYSTEM_PROMPT = (Path(__file__).parent / "prompts" / "system.txt").read_text(encoding="utf-8")
SMALL_TALK = {"oi", "ola", "bom dia", "boa tarde", "boa noite", "obrigado", "obrigada",
              "muito obrigado", "muito obrigada", "tchau", "ate logo"}
SCOPE_RESPONSE = (
    "Meu atendimento é voltado à Empório da Música. Posso ajudar com instrumentos "
    "musicais, preços, estoque, pedidos e políticas da loja. Qual dessas informações você precisa?"
)


class Agent:
    def __init__(self, client, toolbox: Toolbox, on_tool_call: Optional[Callable[[str], None]] = None):
        self.client = client
        self.toolbox = toolbox
        self.on_tool_call = on_tool_call
        self.history = []
        self.last_tool_calls = []

    def reset(self) -> None:
        self.history.clear()
        self.last_tool_calls.clear()

    def ask(self, text: str) -> str:
        if not isinstance(text, str) or not text.strip() or len(text) > 2000:
            raise ValueError("Envie uma mensagem entre 1 e 2000 caracteres.")
        user_message = {"role": "user", "content": text.strip()}
        messages = [{"role": "system", "content": SYSTEM_PROMPT}, *self.history, user_message]
        self.last_tool_calls = []
        used = 0
        references = {}
        last_result = None
        for _ in range(6):
            message = self.client.chat(messages, TOOL_SCHEMAS)
            calls = message.get("tool_calls") or []
            if not isinstance(calls, list):
                raise ModelError("O modelo retornou chamadas de ferramentas inválidas.")
            if not calls:
                answer = message.get("content", "").strip()
                if not answer:
                    raise ModelError("O modelo não retornou uma resposta.")
                # Não entregar afirmações de atendimento sem nenhuma consulta no turno.
                if last_result is None and normalize_text(text) not in SMALL_TALK:
                    answer = SCOPE_RESPONSE
                elif last_result is not None and "error" in last_result:
                    code = last_result["error"]["code"]
                    if code in {"session_required", "order_not_found"}:
                        answer = last_result["error"]["message"]
                    else:
                        answer = "Não consegui concluir a consulta. Pode reformular a pergunta ou procurar a equipe da loja?"
                if references:
                    labels = []
                    for section_id, pages in sorted(references, key=lambda item: int(item[0])):
                        page_label = "página" if len(pages) == 1 else "páginas"
                        labels.append(f"manual, seção {section_id}, {page_label} {', '.join(map(str, pages))}")
                    answer += "\n\nFontes consultadas: " + "; ".join(labels) + "."
                self.history = [*self.history, user_message, {"role": "assistant", "content": answer}][-6:]
                while sum(len(item["content"]) for item in self.history) > 4000:
                    del self.history[:2]
                return answer
            if used + len(calls) > 8:
                raise ModelError("O modelo excedeu o limite de consultas. Reformule a pergunta.")
            # Validar o lote antes de executar qualquer chamada.
            for call in calls:
                function = call.get("function") if isinstance(call, dict) else None
                if not isinstance(function, dict) or not isinstance(function.get("name"), str):
                    raise ModelError("O modelo retornou uma chamada malformada.")
            messages.append(message)
            for call in calls:
                function = call["function"]
                name = function["name"]
                result = self.toolbox.execute(name, function.get("arguments", {}))
                last_result = result
                if name in {"search_policies", "get_policy_section"}:
                    sections = result.get("sections", []) if name == "search_policies" else [result.get("section")]
                    for section in sections:
                        if section is not None:
                            references[(section["section_id"], tuple(section["pages"]))] = True
                self.last_tool_calls.append(name)
                if self.on_tool_call:
                    self.on_tool_call(name)
                messages.append({"role": "tool", "tool_name": name,
                                 "content": json.dumps(result, ensure_ascii=False)})
                used += 1
        raise ModelError("O modelo não concluiu a resposta no limite de etapas. Reformule a pergunta.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Conversa com o agente local da Empório da Música.")
    parser.add_argument("--model", default=os.environ.get("OLLAMA_MODEL", "qwen3:4b-instruct"))
    parser.add_argument("--url", default=os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434"))
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--customer-id", type=int, help="Simula uma sessão identificada. Não é autenticação de produção.")
    parser.add_argument("--trace", action="store_true", help="Mostra os nomes das ferramentas chamadas.")
    parser.add_argument("--message", help="Executa uma única mensagem, sem modo interativo.")
    args = parser.parse_args()
    try:
        data = load_dataset(args.data_dir)
        load_policies(args.data_dir / "politicas_da_loja.json")
        if args.customer_id is not None and args.customer_id not in data.customers:
            raise ValueError("Cliente de demonstração não encontrado nos dados.")
        client = OllamaClient(args.model, args.url)
        trace = (lambda name: print(f"[consulta] {name}", flush=True)) if args.trace else None
        agent = Agent(client, Toolbox(args.data_dir, args.customer_id), trace)
    except (ValueError, DataValidationError, PolicyIndexError) as error:
        parser.exit(1, f"Erro de configuração: {error}\n")
    if args.message is not None:
        try:
            print(agent.ask(args.message))
        except (ModelError, ValueError) as error:
            parser.exit(1, f"Erro: {error}\n")
        return
    print(f"Empório da Música — modelo local: {args.model}")
    print("Digite /sair para encerrar ou /limpar para iniciar outra conversa.")
    if args.customer_id is not None:
        print("Sessão de cliente simulada para demonstração; não é autenticação de produção.")
    while True:
        try:
            text = input("Você: ").strip()
            if text == "/sair":
                break
            if text == "/limpar":
                agent.reset()
                print("Histórico da conversa limpo.")
                continue
            if not text:
                continue
            try:
                print("Assistente:", agent.ask(text))
            except (ModelError, ValueError) as error:
                print(f"Erro: {error}")
        except (EOFError, KeyboardInterrupt):
            print()
            break


if __name__ == "__main__":
    main()
