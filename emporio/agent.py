"""Terminal conversation using a local model and controlled query tools."""

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
from emporio.routing import fallback_lookup


SYSTEM_PROMPT = (Path(__file__).parent / "prompts" / "system.txt").read_text(encoding="utf-8")
SMALL_TALK = {"oi", "ola", "bom dia", "boa tarde", "boa noite", "obrigado", "obrigada",
              "muito obrigado", "muito obrigada", "tchau", "ate logo",
              "hi", "hello", "good morning", "good afternoon", "good evening", "thanks", "thank you", "goodbye", "bye"}
SCOPE_RESPONSE = (
    "I provide customer support for Empório da Música. I can help with musical "
    "instruments, prices, stock, orders and store policies. Which of these can I help you with?"
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
            raise ValueError("Enter a message between 1 and 2000 characters.")
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
                raise ModelError("The model returned invalid tool calls.")
            if not calls and last_result is None:
                lookup = fallback_lookup(text)
                if lookup is not None:
                    # The application requests the missing lookup and discards the ungrounded draft.
                    calls = [{"function": lookup}]
                    message = {"role": "assistant", "content": "", "tool_calls": calls}
            if not calls:
                answer = message.get("content", "").strip()
                if not answer:
                    raise ModelError("The model returned no answer.")
                # Do not deliver store-related claims without a lookup in the current turn.
                if last_result is None and normalize_text(text) not in SMALL_TALK:
                    answer = SCOPE_RESPONSE
                elif last_result is not None and "error" in last_result:
                    code = last_result["error"]["code"]
                    if code in {"session_required", "order_not_found"}:
                        answer = last_result["error"]["message"]
                    else:
                        answer = "I could not complete the lookup. Could you rephrase your question or contact the store team?"
                if references:
                    labels = []
                    for section_id, pages in sorted(references, key=lambda item: int(item[0])):
                        page_label = "page" if len(pages) == 1 else "pages"
                        labels.append(f"manual, section {section_id}, {page_label} {', '.join(map(str, pages))}")
                    answer += "\n\nSources consulted: " + "; ".join(labels) + "."
                self.history = [*self.history, user_message, {"role": "assistant", "content": answer}][-6:]
                while sum(len(item["content"]) for item in self.history) > 4000:
                    del self.history[:2]
                return answer
            if used + len(calls) > 8:
                raise ModelError("The model exceeded the lookup limit. Please rephrase your question.")
            # Validate the entire batch before executing any call.
            for call in calls:
                function = call.get("function") if isinstance(call, dict) else None
                if not isinstance(function, dict) or not isinstance(function.get("name"), str):
                    raise ModelError("The model returned a malformed tool call.")
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
        raise ModelError("The model did not finish within the step limit. Please rephrase your question.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Chat with the local Empório da Música support agent.")
    parser.add_argument("--model", default=os.environ.get("OLLAMA_MODEL", "qwen3:4b-instruct"))
    parser.add_argument("--url", default=os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434"))
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--customer-id", type=int, help="Simulate an identified session. This is not production authentication.")
    parser.add_argument("--trace", action="store_true", help="Show the names of invoked tools.")
    parser.add_argument("--message", help="Run one message without interactive mode.")
    args = parser.parse_args()
    try:
        data = load_dataset(args.data_dir)
        load_policies(args.data_dir / "policies.en.json")
        if args.customer_id is not None and args.customer_id not in data.customers:
            raise ValueError("Demo customer not found in the dataset.")
        client = OllamaClient(args.model, args.url)
        trace = (lambda name: print(f"[lookup] {name}", flush=True)) if args.trace else None
        agent = Agent(client, Toolbox(args.data_dir, args.customer_id), trace)
    except (ValueError, DataValidationError, PolicyIndexError) as error:
        parser.exit(1, f"Configuration error: {error}\n")
    if args.message is not None:
        try:
            print(agent.ask(args.message))
        except (ModelError, ValueError) as error:
            parser.exit(1, f"Error: {error}\n")
        return
    print(f"Empório da Música — local model: {args.model}")
    print("Type /exit to quit or /reset to start a new conversation.")
    if args.customer_id is not None:
        print("Demo customer session; this is not production authentication.")
    while True:
        try:
            text = input("You: ").strip()
            if text == "/exit":
                break
            if text == "/reset":
                agent.reset()
                print("Conversation history cleared.")
                continue
            if not text:
                continue
            try:
                print("Assistant:", agent.ask(text))
            except (ModelError, ValueError) as error:
                print(f"Error: {error}")
        except (EOFError, KeyboardInterrupt):
            print()
            break


if __name__ == "__main__":
    main()
