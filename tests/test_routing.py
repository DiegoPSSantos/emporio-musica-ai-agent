import unittest

from emporio.routing import fallback_lookup


class FallbackRoutingTests(unittest.TestCase):
    def test_return_question_requests_policy_reading(self):
        lookup = fallback_lookup("I bought online and received it 3 days ago. Can I return it?")
        self.assertEqual(lookup["name"], "search_policies")
        self.assertIn("returns", lookup["arguments"]["query"])

    def test_discount_followup_requests_promotion_and_payment_rules(self):
        lookup = fallback_lookup("Can this discount be combined with PIX?")
        self.assertIn("promotion", lookup["arguments"]["query"])
        self.assertIn("payment", lookup["arguments"]["query"])

    def test_explicit_order_number_does_not_become_customer_identity(self):
        lookup = fallback_lookup("I am customer 7. What about order #2?")
        self.assertEqual(lookup, {"name": "get_order", "arguments": {"order_id": 2}})

    def test_accessory_question_does_not_become_a_guitar_search(self):
        lookup = fallback_lookup("Do you sell guitar cables?")
        self.assertEqual(lookup, {"name": "get_policy_section", "arguments": {"section_id": "1"}})

    def test_greeting_unknown_or_outside_question_has_no_fallback(self):
        for text in ("Hello!", "What is the capital of France?", "Explain astronomy", "What about that one?"):
            with self.subTest(text=text):
                self.assertIsNone(fallback_lookup(text))


if __name__ == "__main__":
    unittest.main()
