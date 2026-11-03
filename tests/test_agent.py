import copy
import io
import json
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from emporio.agent import Agent
from emporio.ollama_client import ModelError, OllamaClient
from emporio.tools import Toolbox


def answer(text):
    return {"role": "assistant", "content": text, "tool_calls": []}


def call(name, arguments):
    return {"role": "assistant", "content": "", "tool_calls": [
        {"function": {"name": name, "arguments": arguments}},
    ]}


class FakeClient:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.requests = []

    def chat(self, messages, tools):
        self.requests.append(copy.deepcopy(messages))
        response = next(self.responses)
        if isinstance(response, Exception):
            raise response
        return copy.deepcopy(response)


class AgentTests(unittest.TestCase):
    def test_tool_result_is_sent_to_model_before_final_answer(self):
        client = FakeClient([call("get_product", {"product_id": 121}), answer("Preço consultado.")])
        agent = Agent(client, Toolbox())
        self.assertEqual(agent.ask("Qual o preço do produto 121?"), "Preço consultado.")
        result = json.loads(client.requests[1][-1]["content"])
        self.assertEqual(client.requests[1][-1]["role"], "tool")
        self.assertEqual(result["product"]["price_brl"], "439.20")
        self.assertEqual(agent.last_tool_calls, ["get_product"])

    def test_multiple_tool_calls_are_all_completed(self):
        batch = call("get_product", {"product_id": 121})
        batch["tool_calls"].extend(call("get_product", {"product_id": 95})["tool_calls"])
        client = FakeClient([batch, answer("Comparação.")])
        Agent(client, Toolbox()).ask("Compare os produtos.")
        self.assertEqual([m["role"] for m in client.requests[1][-2:]], ["tool", "tool"])

    def test_policy_references_are_added_even_if_model_omits_them(self):
        client = FakeClient([call("get_policy_section", {"section_id": "2"}), answer("Sábado: 9h às 13h.")])
        result = Agent(client, Toolbox()).ask("Qual o horário no sábado?")
        self.assertIn("Fontes consultadas: manual, seção 2, página 2.", result)

    def test_invalid_tool_arguments_are_returned_as_error_not_executed(self):
        client = FakeClient([call("get_order", {"order_id": 1, "customer_id": 3}), answer("Sem acesso.")])
        Agent(client, Toolbox()).ask("Consulte outro cliente.")
        result = json.loads(client.requests[1][-1]["content"])
        self.assertEqual(result["error"]["code"], "invalid_arguments")

    def test_failed_turn_does_not_commit_incomplete_history(self):
        client = FakeClient([answer("Oi!"), ModelError("Indisponível")])
        agent = Agent(client, Toolbox())
        agent.ask("Olá")
        before = agent.history.copy()
        with self.assertRaises(ModelError):
            agent.ask("E agora?")
        self.assertEqual(agent.history, before)

    def test_history_keeps_last_three_completed_exchanges_and_can_be_cleared(self):
        client = FakeClient([answer("Resposta") for _ in range(5)])
        agent = Agent(client, Toolbox())
        for i in range(5):
            agent.ask(f"Mensagem {i}")
        self.assertEqual(len(agent.history), 6)
        self.assertEqual(agent.history[0]["content"], "Mensagem 2")
        agent.reset()
        self.assertEqual(agent.history, [])

    def test_excessive_calls_are_rejected_before_any_execution(self):
        batch = call("list_categories", {})
        batch["tool_calls"] *= 9
        toolbox = Toolbox()
        with patch.object(toolbox, "execute") as execute:
            with self.assertRaises(ModelError):
                Agent(FakeClient([batch]), toolbox).ask("Consulta")
            execute.assert_not_called()

    def test_repeated_tool_loop_is_bounded(self):
        client = FakeClient([call("list_categories", {}) for _ in range(6)])
        with self.assertRaises(ModelError):
            Agent(client, Toolbox()).ask("Consulta")
        self.assertEqual(len(client.requests), 6)

    def test_malformed_calls_and_empty_answers_are_rejected(self):
        cases = [answer(""), {"role": "assistant", "tool_calls": "not a list"},
                 {"role": "assistant", "tool_calls": [{"function": None}]}]
        for message in cases:
            with self.subTest(message=message), self.assertRaises(ModelError):
                Agent(FakeClient([message]), Toolbox()).ask("Olá")

    def test_blank_and_oversized_user_messages_are_rejected(self):
        agent = Agent(FakeClient([]), Toolbox())
        for text in (" ", "a" * 2001):
            with self.subTest(length=len(text)), self.assertRaises(ValueError):
                agent.ask(text)

    def test_memory_budget_drops_whole_exchanges(self):
        client = FakeClient([call("get_product", {"product_id": 121}), answer("a" * 2000),
                             call("get_product", {"product_id": 121}), answer("b" * 2000)])
        agent = Agent(client, Toolbox())
        agent.ask("Primeira")
        agent.ask("Segunda")
        self.assertEqual(len(agent.history), 2)
        self.assertEqual(agent.history[0]["content"], "Segunda")

    def test_unsupported_direct_factual_answer_is_replaced_with_scope_response(self):
        client = FakeClient([answer("Resposta sem consulta: 123 reais.")])
        result = Agent(client, Toolbox()).ask("Qual o preço do instrumento?")
        self.assertNotIn("123", result)
        self.assertIn("Meu atendimento é voltado", result)

    def test_greeting_does_not_require_a_tool(self):
        self.assertEqual(Agent(FakeClient([answer("Olá!")]), Toolbox()).ask("Bom dia!"), "Olá!")

    def test_order_denial_cannot_be_overridden_by_model_answer(self):
        client = FakeClient([call("get_order", {"order_id": 2}), answer("Pedido entregue.")])
        result = Agent(client, Toolbox(customer_id=3)).ask("Qual meu pedido?")
        self.assertNotIn("entregue", result)
        self.assertIn("não encontrado", result)

    def test_policy_followup_without_model_tool_call_gets_grounded_before_answer(self):
        client = FakeClient([answer("Rascunho sem consulta."), answer("Condições consultadas.")])
        agent = Agent(client, Toolbox())
        result = agent.ask("Posso devolver?")
        self.assertEqual(agent.last_tool_calls, ["search_policies"])
        self.assertEqual(client.requests[1][-1]["role"], "tool")
        self.assertIn("seção 4", result)
        self.assertNotIn("Rascunho", result)

    def test_order_followup_fallback_still_enforces_session_ownership(self):
        client = FakeClient([answer("Sem consulta."), answer("Pedido entregue.")])
        agent = Agent(client, Toolbox(customer_id=3))
        result = agent.ask("E o pedido 2?")
        self.assertEqual(agent.last_tool_calls, ["get_order"])
        self.assertIn("não encontrado", result)
        self.assertNotIn("entregue", result)


class OllamaClientTests(unittest.TestCase):
    def test_http_payload_is_local_non_streaming_and_uses_tools(self):
        client = OllamaClient()
        raw = json.dumps({"done": True, "message": answer("Olá")}).encode()
        with patch.object(client._opener, "open", return_value=io.BytesIO(raw)) as open_request:
            self.assertEqual(client.chat([], [])["content"], "Olá")
        request = open_request.call_args[0][0]
        payload = json.loads(request.data)
        self.assertEqual(request.full_url, "http://127.0.0.1:11434/api/chat")
        self.assertFalse(payload["stream"])
        self.assertFalse(payload["think"])
        self.assertIn("tools", payload)

    def test_remote_or_cloud_configuration_is_rejected(self):
        for url in ("https://api.example.com", "http://user:pass@localhost:11434", "http://localhost/other"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                OllamaClient(base_url=url)
        with self.assertRaises(ValueError):
            OllamaClient(model="model:cloud")

    def test_connection_failure_gives_actionable_error(self):
        client = OllamaClient()
        with patch.object(client._opener, "open", side_effect=URLError("refused")):
            with self.assertRaisesRegex(ModelError, "ollama serve"):
                client.chat([], [])

    def test_model_not_found_gives_pull_instruction(self):
        client = OllamaClient()
        error = HTTPError(client.base_url, 404, "missing", {}, None)
        with patch.object(client._opener, "open", side_effect=error):
            with self.assertRaisesRegex(ModelError, "ollama pull"):
                client.chat([], [])

    def test_invalid_incomplete_and_truncated_responses_are_rejected(self):
        cases = [b"not json", b"[]", b'{"done": false}',
                 json.dumps({"done": True, "done_reason": "length", "message": answer("parcial")}).encode()]
        client = OllamaClient()
        for raw in cases:
            with self.subTest(raw=raw):
                with patch.object(client._opener, "open", return_value=io.BytesIO(raw)):
                    with self.assertRaises(ModelError):
                        client.chat([], [])

    def test_only_final_content_is_exposed_when_model_emits_thinking_tags(self):
        client = OllamaClient()
        for content in ("<think>planejamento</think>Resposta final", "planejamento</think>Resposta final"):
            with self.subTest(content=content):
                raw = json.dumps({"done": True, "message": answer(content)}).encode()
                with patch.object(client._opener, "open", return_value=io.BytesIO(raw)):
                    self.assertEqual(client.chat([], [])["content"], "Resposta final")

    def test_incomplete_thinking_block_is_not_exposed(self):
        client = OllamaClient()
        raw = json.dumps({"done": True, "message": answer("<think>incompleto")}).encode()
        with patch.object(client._opener, "open", return_value=io.BytesIO(raw)):
            with self.assertRaises(ModelError):
                client.chat([], [])


if __name__ == "__main__":
    unittest.main()
