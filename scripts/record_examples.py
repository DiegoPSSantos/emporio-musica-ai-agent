"""Record real local-agent conversations without rewriting responses."""

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
    Scenario("01_catalog", "Catalog search and follow-up",
             "Search acoustic guitars within a budget and look up a payment option in a follow-up.",
             ("Which acoustic guitars are available for up to BRL 1,000?",
              "How much is the Yamaha C40 if I pay with PIX?")),
    Scenario("02_promotions_pix", "Promotions and PIX payment",
             "Demonstrate a price lookup and the rule against combining discounts.",
             ("How much is product 121 if I pay with PIX?",
              "Can that discount be combined with the 5% PIX discount?")),
    Scenario("03_policies", "Opening hours and return conditions",
             "Retrieve policy references and preserve the conditions for a return.",
             ("What are your Saturday opening hours?",
              "I bought online and received the product 3 days ago. Can I return it?")),
    Scenario("04_orders", "Orders and session isolation",
             "Look up an authorized order and attempt to access another customer without revealing their data.",
             ("What is the status of order 1?", "What about order 2?"), customer_id=3),
    Scenario("05_scope", "Out-of-scope questions and accessories",
             "Observe scope handling and a request for accessories.",
             ("What is the capital of France?", "Do you sell guitar cables?")),
)


def revision() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], cwd=PROJECT_ROOT,
            check=True, capture_output=True, text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unavailable"


def record(scenario: Scenario, directory: Path, model: str, url: str) -> int:
    started = datetime.now(ZoneInfo("America/Sao_Paulo")).isoformat(timespec="seconds")
    parts = [
        f"# {scenario.title}",
        "Automatically recorded real application conversation. The responses below have not been edited.",
        f"Scenario objective: {scenario.purpose}",
        f"- Started: {started}\n- Requested model: `{model}`\n"
        f"- Python: {platform.python_version()}\n- Application commit: `{revision()}`\n"
        f"- Simulated session customer: {scenario.customer_id if scenario.customer_id is not None else 'none'}",
        "The scenario objective is not a claim that the result passed review. "
        "Responses include application safeguards and source references. "
        "Tools may be invoked by the model or the application fallback. "
        "Timings are observations from this run, not a benchmark.",
    ]
    agent = Agent(OllamaClient(model, url), Toolbox(customer_id=scenario.customer_id))
    errors = 0
    for number, message in enumerate(scenario.messages, start=1):
        print(f"{scenario.slug}: message {number}/{len(scenario.messages)}", flush=True)
        started_turn = perf_counter()
        try:
            response = agent.ask(message)
            label = "Assistant"
        except (ModelError, ValueError) as error:
            response = str(error)
            label = "Application error"
            errors += 1
        elapsed = perf_counter() - started_turn
        tools = ", ".join(f"`{name}`" for name in agent.last_tool_calls) or "none"
        parts.extend([
            f"## Message {number}",
            f"**Customer:** {message}",
            f"Tools invoked: {tools}. Observed time: {elapsed:.2f} s.",
            f"**{label}:**\n\n{response}",
        ])
    (directory / f"{scenario.slug}.md").write_text("\n\n".join(parts) + "\n", encoding="utf-8")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description="Capture five real conversations with local Ollama.")
    parser.add_argument("--model", default=os.environ.get("OLLAMA_MODEL", "qwen3:4b-instruct"))
    parser.add_argument("--url", default=os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434"))
    parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "examples")
    parser.add_argument("--only", choices=[scenario.slug for scenario in SCENARIOS])
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    scenarios = [scenario for scenario in SCENARIOS if args.only in {None, scenario.slug}]
    if not args.overwrite and any((args.output_dir / f"{scenario.slug}.md").exists() for scenario in scenarios):
        parser.error("Captures already exist. Use --overwrite to replace them explicitly.")
    try:
        load_dataset()
        load_policies()
        args.output_dir.mkdir(parents=True, exist_ok=True)
        errors = sum(record(scenario, args.output_dir, args.model, args.url) for scenario in scenarios)
    except (OSError, ValueError) as error:
        parser.exit(1, f"Capture failed: {error}\n")
    print(f"Captures saved to {args.output_dir}; execution errors: {errors}.")
    if errors:
        parser.exit(1)


if __name__ == "__main__":
    main()
