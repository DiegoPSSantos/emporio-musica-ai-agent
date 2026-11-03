import csv
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path

from emporio.data import DEFAULT_DATA_DIR, DataValidationError, load_dataset


class DatasetTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        for source in DEFAULT_DATA_DIR.glob("*.csv"):
            shutil.copyfile(source, self.directory / source.name)

    def rewrite(self, table, change):
        path = self.directory / f"{table}.csv"
        with path.open(encoding="utf-8-sig", newline="") as file:
            reader = csv.DictReader(file)
            headers = reader.fieldnames
            rows = list(reader)
        change(rows)
        with path.open("w", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=headers)
            writer.writeheader()
            writer.writerows(rows)

    def test_supplied_data_loads_with_appropriate_types(self):
        data = load_dataset(self.directory)
        product = data.products[81]
        self.assertEqual(product.price_brl, Decimal("599.9"))
        self.assertIsInstance(product.created_at, date)
        self.assertEqual(product.specs["strings"], "nylon")
        self.assertIsInstance(next(iter(data.promotions.values())).is_active, bool)
        self.assertTrue(data.order_items)

    def test_missing_optional_order_information_is_none(self):
        self.rewrite("orders", lambda rows: rows[0].update(
            tracking_code="", estimated_delivery="", notes=""
        ))
        data = load_dataset(self.directory)
        order = data.orders[1]
        self.assertIsNone(order.tracking_code)
        self.assertIsNone(order.estimated_delivery)
        self.assertIsNone(order.notes)

    def test_zero_stock_is_valid(self):
        self.rewrite("products", lambda rows: rows[0].update(stock_quantity="0"))
        self.assertEqual(load_dataset(self.directory).products[81].stock_quantity, 0)

    def test_invalid_money_is_rejected(self):
        for value in ("-1", "NaN", "Infinity", "não é um preço", ""):
            with self.subTest(value=value):
                self.rewrite("products", lambda rows: rows[0].update(price_brl=value))
                with self.assertRaisesRegex(DataValidationError, "products.csv.*price_brl"):
                    load_dataset(self.directory)

    def test_invalid_stock_and_quantity_are_rejected(self):
        cases = [("products", "stock_quantity", "-1"),
                 ("products", "stock_quantity", "1.5"),
                 ("order_items", "quantity", "0")]
        for table, field, value in cases:
            with self.subTest(field=field, value=value):
                original = (self.directory / f"{table}.csv").read_bytes()
                self.rewrite(table, lambda rows: rows[0].update({field: value}))
                with self.assertRaisesRegex(DataValidationError, field):
                    load_dataset(self.directory)
                (self.directory / f"{table}.csv").write_bytes(original)

    def test_invalid_promotion_values_are_rejected(self):
        for field, value in (("discount_percent", "101"), ("is_active", "false")):
            with self.subTest(field=field):
                original = (self.directory / "promotions.csv").read_bytes()
                self.rewrite("promotions", lambda rows: rows[0].update({field: value}))
                with self.assertRaisesRegex(DataValidationError, field):
                    load_dataset(self.directory)
                (self.directory / "promotions.csv").write_bytes(original)

    def test_duplicate_primary_key_is_rejected(self):
        self.rewrite("products", lambda rows: rows.append(rows[0].copy()))
        with self.assertRaisesRegex(DataValidationError, "chave duplicada.*product_id"):
            load_dataset(self.directory)

    def test_broken_references_are_rejected(self):
        cases = [("products", "category_id"), ("orders", "customer_id"),
                 ("order_items", "order_id"), ("order_items", "product_id"),
                 ("promotions", "product_id")]
        for table, field in cases:
            with self.subTest(table=table, field=field):
                original = (self.directory / f"{table}.csv").read_bytes()
                self.rewrite(table, lambda rows: rows[0].update({field: "999999"}))
                with self.assertRaisesRegex(DataValidationError, f"{table}.csv.*{field}"):
                    load_dataset(self.directory)
                (self.directory / f"{table}.csv").write_bytes(original)

    def test_invalid_dates_and_specifications_are_rejected(self):
        cases = [("created_at", "2026-02-30"), ("specs", "{inválido"),
                 ("specs", "[]"), ("specs", '{"strings": 3}')]
        for field, value in cases:
            with self.subTest(field=field, value=value):
                original = (self.directory / "products.csv").read_bytes()
                self.rewrite("products", lambda rows: rows[0].update({field: value}))
                with self.assertRaisesRegex(DataValidationError, field):
                    load_dataset(self.directory)
                (self.directory / "products.csv").write_bytes(original)

    def test_invalid_headers_and_row_width_are_rejected(self):
        path = self.directory / "categories.csv"
        original = path.read_text(encoding="utf-8")
        cases = ["category_id,name,name\n1,a,b\n",
                 "category_id,name\n1,a\n",
                 "category_id,name,description\n1,a\n",
                 "category_id,name,description\n1,a,b,extra\n"]
        for contents in cases:
            with self.subTest(contents=contents):
                path.write_text(contents, encoding="utf-8")
                with self.assertRaises(DataValidationError):
                    load_dataset(self.directory)
        path.write_text(original, encoding="utf-8")

    def test_missing_and_empty_tables_are_rejected(self):
        path = self.directory / "categories.csv"
        path.unlink()
        with self.assertRaisesRegex(DataValidationError, "categories.csv"):
            load_dataset(self.directory)
        path.write_text("category_id,name,description\n", encoding="utf-8")
        with self.assertRaisesRegex(DataValidationError, "tabela vazia"):
            load_dataset(self.directory)

    def test_utf8_bom_is_supported(self):
        path = self.directory / "categories.csv"
        contents = path.read_text(encoding="utf-8")
        path.write_text(contents, encoding="utf-8-sig")
        self.assertTrue(load_dataset(self.directory).categories)

    def test_errors_do_not_include_personal_cell_contents(self):
        self.rewrite("customers", lambda rows: rows[0].update(customer_id="dado-privado"))
        with self.assertRaises(DataValidationError) as caught:
            load_dataset(self.directory)
        self.assertIn("customer_id", str(caught.exception))
        self.assertNotIn("dado-privado", str(caught.exception))

    def test_cli_returns_error_for_invalid_data_without_traceback(self):
        self.rewrite("products", lambda rows: rows[0].update(price_brl="inválido"))
        result = subprocess.run(
            [sys.executable, "-m", "emporio.data", "--data-dir", str(self.directory)],
            cwd=DEFAULT_DATA_DIR.parent,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("products.csv", result.stderr)
        self.assertIn("price_brl", result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertEqual(result.stdout, "")


if __name__ == "__main__":
    unittest.main()
