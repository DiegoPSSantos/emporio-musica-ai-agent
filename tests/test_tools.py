import json
import unittest

from emporio.tools import TOOL_SCHEMAS, Toolbox


class ToolboxTests(unittest.TestCase):
    def test_all_declared_tools_are_read_only_and_have_closed_schemas(self):
        for tool in TOOL_SCHEMAS:
            self.assertFalse(tool["function"]["parameters"]["additionalProperties"])
        self.assertNotIn("customer_id", next(
            tool for tool in TOOL_SCHEMAS if tool["function"]["name"] == "get_order"
        )["function"]["parameters"]["properties"])

    def test_product_results_are_json_serializable_and_preserve_money(self):
        result = Toolbox().execute("get_product", {"product_id": 121, "payment_method": "pix"})
        self.assertEqual(json.loads(json.dumps(result))["product"]["price_brl"], "439.20")
        self.assertEqual(result["product"]["list_price_brl"], "549")

    def test_search_limits_results_and_reports_truncation(self):
        result = Toolbox().execute("search_products", {"category": "Violões", "max_price": "1000", "limit": 2})
        self.assertEqual(len(result["products"]), 2)
        self.assertGreater(result["total_matches"], 2)
        self.assertTrue(result["truncated"])

    def test_redundant_generic_name_does_not_exclude_category_products(self):
        result = Toolbox().execute("search_products", {
            "query": "violão", "category": "Violões", "max_price": "1000",
        })
        self.assertEqual(result["total_matches"], 12)

    def test_specific_name_is_not_removed_when_category_is_present(self):
        result = Toolbox().execute("search_products", {"query": "Fender", "category": "Violões"})
        self.assertEqual(result["total_matches"], 0)

    def test_english_categories_keep_original_catalog_results(self):
        toolbox = Toolbox()
        english = toolbox.execute("search_products", {"query": "guitars", "category": "Acoustic guitars", "max_price": "1000"})
        original = toolbox.execute("search_products", {"category": "Violões", "max_price": "1000"})
        self.assertEqual(english, original)
        self.assertEqual(english["total_matches"], 12)
        self.assertEqual(english["products"][0]["category"], "Acoustic guitars")

    def test_category_list_and_promotional_labels_are_in_english(self):
        toolbox = Toolbox()
        names = {category["name"] for category in toolbox.execute("list_categories", {})["categories"]}
        self.assertIn("Acoustic guitars", names)
        self.assertIn("Woodwind instruments", names)
        self.assertEqual(toolbox.execute("get_product", {"product_id": 121})["product"]["promotion_description"], "Exclusive discount")

    def test_invalid_arguments_and_unlisted_functions_cannot_be_executed(self):
        cases = [("get_product", {"product_id": True}),
                 ("get_product", {}), ("list_categories", {"path": "/etc/passwd"}),
                 ("search_products", {"limit": 999}),
                 ("search_products", {"max_price": "NaN"}),
                 ("search_products", {"payment_method": "credit"}),
                 ("search_policies", {"query": "x" * 501}),
                 ("get_product", "not an object")]
        for name, arguments in cases:
            with self.subTest(name=name, arguments=arguments):
                self.assertEqual(Toolbox().execute(name, arguments)["error"]["code"], "invalid_arguments")
        self.assertEqual(Toolbox().execute("__import__", {})["error"]["code"], "unknown_tool")

    def test_unavailable_product_has_no_sale_price(self):
        product = Toolbox().execute("get_product", {"product_id": 136})["product"]
        self.assertFalse(product["available"])
        self.assertIsNone(product["price_brl"])

    def test_unknown_product_id_is_not_reported_as_out_of_stock(self):
        result = Toolbox().execute("get_product", {"product_id": 1})
        self.assertEqual(result["error"]["code"], "product_not_found")
        self.assertNotIn("product", result)
        self.assertIn("search_products", result["error"]["message"])

    def test_policy_results_include_text_section_and_page(self):
        result = Toolbox().execute("search_policies", {"query": "return", "limit": 1})
        section = result["sections"][0]
        self.assertEqual(section["section_id"], "4")
        self.assertEqual(section["pages"], [4])
        self.assertIn("4.4 Items Not Eligible", section["text"])

    def test_order_requires_session(self):
        self.assertEqual(Toolbox().execute("get_order", {"order_id": 1})["error"]["code"], "session_required")

    def test_owned_order_excludes_customer_contact_and_internal_notes(self):
        order = Toolbox(customer_id=3).execute("get_order", {"order_id": 1})["order"]
        self.assertEqual(order["order_id"], 1)
        for key in ("customer_id", "email", "phone", "notes"):
            self.assertNotIn(key, order)
        self.assertTrue(order["items"])

    def test_other_customers_order_and_missing_order_have_same_response(self):
        toolbox = Toolbox(customer_id=3)
        self.assertEqual(toolbox.execute("get_order", {"order_id": 2}),
                         toolbox.execute("get_order", {"order_id": 999999}))

    def test_model_cannot_override_session_identity(self):
        result = Toolbox(customer_id=3).execute("get_order", {"order_id": 2, "customer_id": 7})
        self.assertEqual(result["error"]["code"], "invalid_arguments")

    def test_source_failures_do_not_return_partial_data(self):
        result = Toolbox(data_dir="/nonexistent-emporio-data").execute("get_product", {"product_id": 121})
        self.assertEqual(result["error"]["code"], "data_unavailable")
        self.assertNotIn("product", result)


if __name__ == "__main__":
    unittest.main()
