"""Registra conversas reais com o agente local, sem reescrever suas respostas."""

import argparse
import os
import platform
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Optional
from zoneinfo import ZoneInfo

from emporio.agent import Agent
from emporio.data import load_dataset
from emporio.ollama_client import ModelError, OllamaClient
from emporio.policies import load_policies
from emporio.tools import Toolbox


PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Scenario:
    slug: str
    title: str
    purpose: str
    messages: tuple[str, ...]
    customer_id: Optional[int] = None


SCENARIOS = (
    Scenario("01_catalogo", "Catálogo e continuação da conversa",
             "Buscar violões por orçamento e consultar uma condição de pagamento na continuação.",
             ("Quais violões disponíveis custam até R$ 1000?",
              "E o Yamaha C40 pagando no PIX?")),
    Scenario("02_promocao_pix", "Promoção e pagamento por PIX",
             "Demonstrar a consulta de preço e a regra de não acumulação de descontos.",
             ("Quanto custa o produto 121 pagando no PIX?",
              "Esse desconto pode ser acumulado com os 5% do PIX?")),
    Scenario("03_politicas", "Horário e condições de devolução",
             "Recuperar políticas com referências e preservar condições para uma devolução.",
             ("Que horas vocês abrem aos sábados?",
              "Comprei pela internet e recebi há 3 dias. Posso devolver?")),
    Scenario("04_pedidos", "Pedidos e isolamento da sessão",
             "Consultar um pedido autorizado e tentar consultar outro cliente, sem revelar seus dados.",
             ("Qual é o status do pedido 1?", "E o pedido 2?"), customer_id=3),
    Scenario("05_escopo", "Perguntas fora do escopo e acessórios",
             "Observar a orientação de escopo e o atendimento a uma solicitação de acessórios.",
             ("Qual é a capital da França?", "Vocês vendem cabos para guitarra?")),
)


def revision() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], cwd=PROJECT_ROOT,
            check=True, capture_output=True, text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "não disponível"


def record(scenario: Scenario, directory: Path, model: str, url: str) -> int:
    started = datetime.now(ZoneInfo("America/Sao_Paulo")).isoformat(timespec="seconds")
    parts = [
        f"# {scenario.title}",
        "Registro automático de uma conversa real com a aplicação. As respostas abaixo não foram editadas.",
        f"Objetivo do cenário: {scenario.purpose}",
        f"- Início: {started}\n- Modelo solicitado: `{model}`\n"
        f"- Python: {platform.python_version()}\n- Commit da aplicação: `{revision()}`\n"
        f"- Cliente da sessão simulada: {scenario.customer_id if scenario.customer_id is not None else 'nenhum'}",
        "O objetivo do cenário não representa uma aprovação do resultado. "
        "As respostas incluem as proteções e referências acrescentadas pela aplicação. "
        "As ferramentas podem ser acionadas pelo modelo ou pela recuperação determinística da aplicação. "
        "Tempos são observações desta execução, sem caracterizar um benchmark.",
    ]
    agent = Agent(OllamaClient(model, url), Toolbox(customer_id=scenario.customer_id))
    errors = 0
    for number, message in enumerate(scenario.messages, start=1):
        print(f"{scenario.slug}: mensagem {number}/{len(scenario.messages)}", flush=True)
        started_turn = perf_counter()
        try:
            response = agent.ask(message)
            label = "Assistente"
        except (ModelError, ValueError) as error:
            response = str(error)
            label = "Erro da aplicação"
            errors += 1
        elapsed = perf_counter() - started_turn
        tools = ", ".join(f"`{name}`" for name in agent.last_tool_calls) or "nenhuma"
        parts.extend([
            f"## Mensagem {number}",
            f"**Cliente:** {message}",
            f"Ferramentas acionadas: {tools}. Tempo observado: {elapsed:.2f} s.",
            f"**{label}:**\n\n{response}",
        ])
    (directory / f"{scenario.slug}.md").write_text("\n\n".join(parts) + "\n", encoding="utf-8")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description="Captura cinco conversas reais com o Ollama local.")
    parser.add_argument("--model", default=os.environ.get("OLLAMA_MODEL", "qwen3:4b-instruct"))
    parser.add_argument("--url", default=os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434"))
    parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "examples")
    parser.add_argument("--only", choices=[scenario.slug for scenario in SCENARIOS])
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    scenarios = [scenario for scenario in SCENARIOS if args.only in {None, scenario.slug}]
    if not args.overwrite and any((args.output_dir / f"{scenario.slug}.md").exists() for scenario in scenarios):
        parser.error("Já existem capturas. Use --overwrite para substituí-las explicitamente.")
    try:
        load_dataset()
        load_policies()
        args.output_dir.mkdir(parents=True, exist_ok=True)
        errors = sum(record(scenario, args.output_dir, args.model, args.url) for scenario in scenarios)
    except (OSError, ValueError) as error:
        parser.exit(1, f"Falha na captura: {error}\n")
    print(f"Capturas concluídas em {args.output_dir}; erros de execução: {errors}.")
    if errors:
        parser.exit(1)


if __name__ == "__main__":
    main()
