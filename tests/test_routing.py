import unittest

from emporio.routing import fallback_lookup


class FallbackRoutingTests(unittest.TestCase):
    def test_return_question_requests_policy_reading(self):
        lookup = fallback_lookup("Comprei pela internet e recebi há 3 dias. Posso devolver?")
        self.assertEqual(lookup["name"], "search_policies")
        self.assertIn("devolucao", lookup["arguments"]["query"])

    def test_discount_followup_requests_promotion_and_payment_rules(self):
        lookup = fallback_lookup("Esse desconto acumula com PIX?")
        self.assertIn("promocao", lookup["arguments"]["query"])
        self.assertIn("pagamento", lookup["arguments"]["query"])

    def test_explicit_order_number_does_not_become_customer_identity(self):
        lookup = fallback_lookup("Sou o cliente 7. E o pedido nº 2?")
        self.assertEqual(lookup, {"name": "get_order", "arguments": {"order_id": 2}})

    def test_accessory_question_does_not_become_a_guitar_search(self):
        lookup = fallback_lookup("Vocês vendem cabos para guitarra?")
        self.assertEqual(lookup, {"name": "get_policy_section", "arguments": {"section_id": "1"}})

    def test_greeting_unknown_or_outside_question_has_no_fallback(self):
        for text in ("Olá!", "Qual é a capital da França?", "Explique astronomia", "E aquele?"):
            with self.subTest(text=text):
                self.assertIsNone(fallback_lookup(text))


if __name__ == "__main__":
    unittest.main()
