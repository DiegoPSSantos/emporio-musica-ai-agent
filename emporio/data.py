"""Leitura dos CSVs fornecidos, sem dependências externas ou acesso ao modelo."""

import argparse
import csv
import json
from dataclasses import dataclass, fields
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Iterable, Optional, TypeVar


DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
T = TypeVar("T")


class DataValidationError(ValueError):
    """Os dados não podem ser usados com segurança pelas consultas."""


@dataclass(frozen=True)
class Category:
    category_id: int
    name: str
    description: str


@dataclass(frozen=True)
class Customer:
    customer_id: int
    name: str
    phone: str
    email: str
    city: str


@dataclass(frozen=True)
class Product:
    product_id: int
    price_brl: Decimal
    name: str
    category_id: int
    description: str
    stock_quantity: int
    status: str
    specs: dict[str, str]
    created_at: date


@dataclass(frozen=True)
class Order:
    order_id: int
    customer_id: int
    order_date: date
    status: str
    total_brl: Decimal
    payment_method: str
    tracking_code: Optional[str]
    estimated_delivery: Optional[date]
    notes: Optional[str]


@dataclass(frozen=True)
class OrderItem:
    order_id: int
    quantity: int
    product_id: int


@dataclass(frozen=True)
class Promotion:
    promotion_id: int
    product_id: int
    discount_percent: Decimal
    description: str
    is_active: bool


@dataclass(frozen=True)
class Dataset:
    categories: dict[int, Category]
    customers: dict[int, Customer]
    products: dict[int, Product]
    orders: dict[int, Order]
    order_items: tuple[OrderItem, ...]
    promotions: dict[int, Promotion]


def _convert(field: str, value: str):
    value = value.strip()
    if not value:
        if field in {"tracking_code", "estimated_delivery", "notes"}:
            return None
        raise ValueError("campo obrigatório vazio")

    if field.endswith("_id") or field in {"stock_quantity", "quantity"}:
        number = int(value)
        minimum = 0 if field == "stock_quantity" else 1
        if number < minimum:
            raise ValueError(f"inteiro deve ser maior ou igual a {minimum}")
        return number

    if field in {"price_brl", "total_brl", "discount_percent"}:
        number = Decimal(value)
        if not number.is_finite() or number < 0:
            raise ValueError("decimal deve ser finito e não negativo")
        if field == "discount_percent" and number > 100:
            raise ValueError("desconto deve estar entre 0 e 100")
        return number

    if field in {"created_at", "order_date", "estimated_delivery"}:
        return date.fromisoformat(value)

    if field == "is_active":
        if value not in {"0", "1"}:
            raise ValueError("indicador deve ser 0 ou 1")
        return value == "1"

    if field == "specs":
        specs = json.loads(value)
        if not isinstance(specs, dict) or not all(
            isinstance(key, str) and isinstance(item, str)
            for key, item in specs.items()
        ):
            raise ValueError("especificações devem ser um objeto JSON de textos")
        return specs

    return value


def _read_table(directory: Path, name: str, model: type[T]) -> list[T]:
    path = directory / f"{name}.csv"
    expected = {field.name for field in fields(model)}
    records = []
    try:
        with path.open(encoding="utf-8-sig", newline="") as file:
            reader = csv.DictReader(file, strict=True)
            headers = reader.fieldnames or []
            if set(headers) != expected or len(headers) != len(expected):
                raise DataValidationError(
                    f"{path.name}: cabeçalho inválido; campos esperados: "
                    + ", ".join(sorted(expected))
                )
            for row in reader:
                location = f"{path.name}: linha {reader.line_num}"
                if None in row or any(value is None for value in row.values()):
                    raise DataValidationError(f"{location}: quantidade inválida de colunas")
                converted = {}
                for field, value in row.items():
                    try:
                        converted[field] = _convert(field, value)
                    except (ValueError, InvalidOperation):
                        # Não incluir conteúdo das células: pode conter dados pessoais.
                        raise DataValidationError(
                            f"{location}: valor inválido no campo {field}"
                        ) from None
                records.append(model(**converted))
    except (OSError, UnicodeError, csv.Error) as error:
        raise DataValidationError(
            f"{path.name}: não foi possível ler o CSV ({type(error).__name__})"
        ) from None
    if not records:
        raise DataValidationError(f"{path.name}: tabela vazia")
    return records


def _index(records: list[T], key: str, table: str) -> dict[int, T]:
    indexed = {}
    for record in records:
        identity = getattr(record, key)
        if identity in indexed:
            raise DataValidationError(f"{table}.csv: chave duplicada no campo {key}")
        indexed[identity] = record
    return indexed


def _check_references(records: Iterable[T], field: str, target: dict, table: str) -> None:
    for record in records:
        if getattr(record, field) not in target:
            raise DataValidationError(
                f"{table}.csv: referência inexistente no campo {field}"
            )


def load_dataset(directory: Path = DEFAULT_DATA_DIR) -> Dataset:
    """Carrega e valida todas as tabelas antes de disponibilizar o conjunto."""
    directory = Path(directory)
    categories = _index(
        _read_table(directory, "categories", Category), "category_id", "categories"
    )
    customers = _index(
        _read_table(directory, "customers", Customer), "customer_id", "customers"
    )
    products = _index(
        _read_table(directory, "products", Product), "product_id", "products"
    )
    orders = _index(_read_table(directory, "orders", Order), "order_id", "orders")
    items = tuple(_read_table(directory, "order_items", OrderItem))
    promotions = _index(
        _read_table(directory, "promotions", Promotion), "promotion_id", "promotions"
    )

    _check_references(products.values(), "category_id", categories, "products")
    _check_references(orders.values(), "customer_id", customers, "orders")
    _check_references(items, "order_id", orders, "order_items")
    _check_references(items, "product_id", products, "order_items")
    _check_references(promotions.values(), "product_id", products, "promotions")
    return Dataset(categories, customers, products, orders, items, promotions)


def main() -> None:
    parser = argparse.ArgumentParser(description="Valida os dados da Empório da Música.")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    args = parser.parse_args()
    try:
        dataset = load_dataset(args.data_dir)
    except DataValidationError as error:
        parser.exit(1, f"Erro de validação: {error}\n")
    print("Dados carregados e validados:")
    for field in fields(dataset):
        print(f"  {field.name}: {len(getattr(dataset, field.name))} registros")


if __name__ == "__main__":
    main()
