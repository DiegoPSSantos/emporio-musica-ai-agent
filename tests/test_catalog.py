import subprocess
import sys
import unittest
from dataclasses import replace
from datetime import date
from decimal import Decimal

from emporio.catalog import Catalog
from emporio.data import (
    DEFAULT_DATA_DIR, Category, Dataset, Product, Promotion, load_dataset,
)


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.product = Product(
            product_id=1,
            price_brl=Decimal("100"),
            name="Violão Yamaha Nylon",
            category_id=5,
            description="Instrumento para estudo",
            stock_quantity=2,
            status="active",
            specs={"strings": "nylon"},
            created_at=date(2025, 1, 1),
        )
        self.data = Dataset(
            categories={5: Category(5, "Violões", "Violões clássicos e acústicos")},
            customers={},
            products={1: self.product},
            orders={},
            order_items=(),
            promotions={},
        )
        self.catalog = Catalog(self.data)

    def add_promotion(self, promotion_id=1, percent="20", active=True, description="Oferta"):
        self.data.promotions[promotion_id] = Promotion(
            promotion_id, 1, Decimal(percent), description, active
        )

    def test_search_ignores_accents_case_and_term_order(self):
        results = self.catalog.search_products(query="NYLON violao")
        self.assertEqual([offer.product.product_id for offer in results], [1])

    def test_category_uses_full_normalized_name(self):
        self.assertEqual(len(self.catalog.search_products(category="VIOLOES")), 1)
        self.assertEqual(self.catalog.search_products(category="Guitarras"), [])
        self.assertEqual(self.catalog.search_products(category="viol"), [])

    def test_only_active_products_with_stock_are_available(self):
        for status, stock in (("active", 0), ("discontinued", 13),
                              ("coming_soon", 2), ("unknown", 4)):
            with self.subTest(status=status, stock=stock):
                self.data.products[1] = replace(self.product, status=status, stock_quantity=stock)
                self.assertEqual(self.catalog.search_products(), [])
                self.assertFalse(self.catalog.get_product(1).available)
                self.assertEqual(len(self.catalog.search_products(available_only=False)), 1)

    def test_missing_product_is_not_replaced_with_another(self):
        self.assertIsNone(self.catalog.get_product(999))
        self.assertEqual(self.catalog.search_products(query="Produto inexistente"), [])

    def test_no_discount_by_default(self):
        offer = self.catalog.get_product(1)
        self.assertEqual(offer.price_brl, Decimal("100.00"))
        self.assertEqual(offer.discount_percent, Decimal("0"))
        self.assertIsNone(offer.discount_source)

    def test_pix_discount_without_promotion(self):
        offer = self.catalog.get_product(1, payment_method="pix")
        self.assertEqual(offer.price_brl, Decimal("95.00"))
        self.assertEqual(offer.discount_percent, Decimal("5"))
        self.assertEqual(offer.discount_source, "pix")

    def test_inactive_promotion_is_ignored(self):
        self.add_promotion(percent="80", active=False)
        self.assertEqual(self.catalog.get_product(1).price_brl, Decimal("100.00"))
        self.assertEqual(self.catalog.get_product(1, "pix").price_brl, Decimal("95.00"))

    def test_promotion_does_not_accumulate_with_pix(self):
        self.add_promotion()
        offer = self.catalog.get_product(1, "pix")
        self.assertEqual(offer.price_brl, Decimal("80.00"))
        self.assertEqual(offer.product.price_brl, Decimal("100"))
        self.assertEqual(offer.discount_percent, Decimal("20"))
        self.assertEqual(offer.discount_source, "promotion")
        self.assertEqual(offer.promotion_description, "Oferta")

    def test_pix_does_not_replace_an_active_promotion(self):
        self.add_promotion(percent="2")
        self.assertEqual(self.catalog.get_product(1, "pix").price_brl, Decimal("98.00"))

    def test_multiple_promotions_use_largest_discount_without_accumulating(self):
        self.add_promotion(1, "10")
        self.add_promotion(2, "20")
        self.assertEqual(self.catalog.get_product(1).price_brl, Decimal("80.00"))

    def test_equal_discounts_use_lowest_promotion_id(self):
        self.add_promotion(9, description="Segunda")
        self.add_promotion(1, description="Primeira")
        self.assertEqual(self.catalog.get_product(1).promotion_description, "Primeira")

    def test_unavailable_product_does_not_offer_discount(self):
        self.add_promotion()
        self.data.products[1] = replace(self.product, stock_quantity=0)
        offer = self.catalog.get_product(1, "pix")
        self.assertFalse(offer.available)
        self.assertEqual(offer.price_brl, Decimal("100.00"))
        self.assertIsNone(offer.discount_source)

    def test_price_limit_is_inclusive_and_uses_final_price(self):
        self.add_promotion()
        self.assertEqual(len(self.catalog.search_products(max_price=Decimal("80"))), 1)
        self.assertEqual(self.catalog.search_products(max_price=Decimal("79.99")), [])
        self.data.promotions.clear()
        self.assertEqual(len(self.catalog.search_products(
            max_price=Decimal("95"), payment_method="pix"
        )), 1)

    def test_rounding_half_cent_and_filter_use_same_price(self):
        self.data.products[1] = replace(self.product, price_brl=Decimal("1.50"))
        self.assertEqual(self.catalog.get_product(1, "pix").price_brl, Decimal("1.43"))
        self.assertEqual(self.catalog.search_products(
            max_price=Decimal("1.42"), payment_method="pix"
        ), [])
        self.assertEqual(len(self.catalog.search_products(
            max_price=Decimal("1.43"), payment_method="pix"
        )), 1)

    def test_results_are_sorted_by_final_price_name_and_id(self):
        self.data.products[2] = replace(self.product, product_id=2, name="Aço", price_brl=Decimal("80"))
        self.data.products[3] = replace(self.product, product_id=3, name="Aço", price_brl=Decimal("80"))
        self.assertEqual(
            [offer.product.product_id for offer in self.catalog.search_products()], [2, 3, 1]
        )
        self.add_promotion(percent="30")
        self.assertEqual(
            [offer.product.product_id for offer in self.catalog.search_products()], [1, 2, 3]
        )

    def test_invalid_payment_method_is_rejected_even_if_no_product_matches(self):
        with self.assertRaises(ValueError):
            self.catalog.get_product(999, "credit")
        with self.assertRaises(ValueError):
            self.catalog.search_products(query="não existe", payment_method="credit")

    def test_invalid_price_limits_are_rejected(self):
        for value in (Decimal("-1"), Decimal("NaN"), Decimal("Infinity")):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.catalog.search_products(max_price=value)
        with self.assertRaises(TypeError):
            self.catalog.search_products(max_price=1.1)

    def test_quoting_does_not_modify_original_data(self):
        self.add_promotion()
        before_products = self.data.products.copy()
        before_promotions = self.data.promotions.copy()
        self.catalog.search_products(payment_method="pix")
        self.assertEqual(self.data.products, before_products)
        self.assertEqual(self.data.promotions, before_promotions)

    def test_supplied_data_handles_discount_and_discontinued_stock(self):
        catalog = Catalog(load_dataset())
        self.assertEqual(catalog.get_product(121, "pix").price_brl, Decimal("439.20"))
        self.assertFalse(catalog.get_product(136).available)
        self.assertEqual(catalog.get_product(95).price_brl, Decimal("2199.00"))


class CatalogCliTests(unittest.TestCase):
    def run_cli(self, *arguments):
        return subprocess.run(
            [sys.executable, "-m", "emporio.catalog", *arguments],
            cwd=DEFAULT_DATA_DIR.parent, capture_output=True, text=True,
        )

    def test_search_accepts_decimal_comma_and_displays_promotion(self):
        result = self.run_cli("search", "--query", "Ohana CK-20", "--max-price", "439,20")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("R$ 439,20", result.stdout)
        excluded = self.run_cli("search", "--query", "Ohana CK-20", "--max-price", "439,19")
        self.assertEqual(excluded.returncode, 0, excluded.stderr)
        self.assertIn("Nenhum produto encontrado", excluded.stdout)

    def test_show_displays_original_discount_and_final_price(self):
        result = self.run_cli("show", "121", "--payment-method", "pix")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("R$ 549,00", result.stdout)
        self.assertIn("20%", result.stdout)
        self.assertIn("R$ 439,20", result.stdout)

    def test_unavailable_product_is_explained_without_final_price(self):
        result = self.run_cli("show", "136")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("descontinuado", result.stdout)
        self.assertNotIn("Preço final:", result.stdout)

    def test_missing_product_is_reported(self):
        result = self.run_cli("show", "999999")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Nenhum produto encontrado", result.stdout)

    def test_invalid_price_is_a_cli_error(self):
        result = self.run_cli("search", "--max-price", "NaN")
        self.assertEqual(result.returncode, 2)
        self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
