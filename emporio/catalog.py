"""Catalog queries and pricing independent of the language model."""

import argparse
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Optional

from emporio.data import DEFAULT_DATA_DIR, DataValidationError, Dataset, Product, load_dataset
from emporio.text import normalize_text as _normalize
from emporio.localization import category_key, category_label, promotion_label


def _validate_payment_method(payment_method: str) -> None:
    if payment_method not in {"standard", "pix"}:
        raise ValueError("Payment method must be standard or pix.")


@dataclass(frozen=True)
class ProductOffer:
    product: Product
    category: str
    available: bool
    price_brl: Decimal
    discount_percent: Decimal
    discount_source: Optional[str]
    promotion_description: Optional[str]


class Catalog:
    """Query a validated dataset snapshot without modifying source data."""

    def __init__(self, dataset: Dataset):
        self.dataset = dataset

    def _offer(self, product: Product, payment_method: str) -> ProductOffer:
        available = product.status == "active" and product.stock_quantity > 0
        discount = Decimal("0")
        source = None
        description = None
        if available:
            active_promotions = [
                promotion for promotion in self.dataset.promotions.values()
                if promotion.product_id == product.product_id and promotion.is_active
            ]
            # Never stack campaigns. Break ties by lowest ID for stable results.
            promotion = max(
                active_promotions,
                key=lambda item: (item.discount_percent, -item.promotion_id),
                default=None,
            )
            if promotion is not None:
                discount = promotion.discount_percent
                source = "promotion"
                description = promotion_label(promotion.description)
            elif payment_method == "pix":
                discount = Decimal("5")
                source = "pix"

        price = (product.price_brl * (1 - discount / 100)).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        return ProductOffer(
            product=product,
            category=category_label(self.dataset.categories[product.category_id].name),
            available=available,
            price_brl=price,
            discount_percent=discount,
            discount_source=source,
            promotion_description=description,
        )

    def get_product(
        self, product_id: int, payment_method: str = "standard"
    ) -> Optional[ProductOffer]:
        """Include unavailable products so their status can be explained."""
        _validate_payment_method(payment_method)
        product = self.dataset.products.get(product_id)
        return self._offer(product, payment_method) if product is not None else None

    def search_products(
        self,
        query: str = "",
        category: Optional[str] = None,
        max_price: Optional[Decimal] = None,
        available_only: bool = True,
        payment_method: str = "standard",
    ) -> list[ProductOffer]:
        """Search name terms and filter by category and inclusive final price."""
        _validate_payment_method(payment_method)
        if max_price is not None:
            if not isinstance(max_price, Decimal):
                raise TypeError("Maximum price must be provided as Decimal.")
            if not max_price.is_finite() or max_price < 0:
                raise ValueError("Maximum price must be finite and non-negative.")
        terms = _normalize(query).split()
        normalized_category = category_key(category) if category is not None else None
        results = []
        for product in self.dataset.products.values():
            normalized_name = _normalize(product.name)
            if not all(term in normalized_name for term in terms):
                continue
            offer = self._offer(product, payment_method)
            if available_only and not offer.available:
                continue
            if normalized_category is not None and category_key(offer.category) != normalized_category:
                continue
            if max_price is not None and offer.price_brl > max_price:
                continue
            results.append(offer)
        return sorted(
            results,
            key=lambda offer: (offer.price_brl, _normalize(offer.product.name), offer.product.product_id),
        )


def _money_argument(value: str) -> Decimal:
    try:
        number = Decimal(value.replace(",", "."))
        if not number.is_finite() or number < 0:
            raise ValueError
        return number
    except (InvalidOperation, ValueError):
        raise argparse.ArgumentTypeError(
            "Enter a non-negative price such as 1000 or 999.90, without thousands separators."
        ) from None


def _brl(value: Decimal) -> str:
    return f"BRL {value:,.2f}"


def _print_offer(offer: ProductOffer) -> None:
    product = offer.product
    print(f"[{product.product_id}] {product.name}")
    print(f"  Category: {offer.category}")
    if offer.available:
        print(f"  Status: available ({product.stock_quantity} units)")
    else:
        status = {
            "active": "out of stock",
            "discontinued": "discontinued",
            "coming_soon": "upcoming release, not available yet",
        }.get(product.status, "unknown status; availability is not confirmed")
        print(f"  Status: {status}")
    print(f"  List price: {_brl(product.price_brl)}")
    if offer.discount_source is not None:
        reason = offer.promotion_description if offer.discount_source == "promotion" else "PIX"
        print(f"  Discount: {offer.discount_percent}% ({reason})")
    if offer.available:
        print(f"  Final price: {_brl(offer.price_brl)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Query the Empório da Música catalog.")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    common.add_argument("--payment-method", choices=["standard", "pix"], default="standard")
    commands = parser.add_subparsers(dest="command", required=True)
    search = commands.add_parser("search", parents=[common], help="Search products.")
    search.add_argument("--query", default="", help="Terms to match in the product name.")
    search.add_argument("--category", help="Full English category name; original Portuguese names are also accepted.")
    search.add_argument("--max-price", type=_money_argument)
    search.add_argument("--include-unavailable", action="store_true")
    show = commands.add_parser("show", parents=[common], help="Look up a product by ID.")
    show.add_argument("product_id", type=int)
    args = parser.parse_args()
    try:
        catalog = Catalog(load_dataset(args.data_dir))
        if args.command == "show":
            offer = catalog.get_product(args.product_id, args.payment_method)
            results = [offer] if offer is not None else []
        else:
            results = catalog.search_products(
                query=args.query,
                category=args.category,
                max_price=args.max_price,
                available_only=not args.include_unavailable,
                payment_method=args.payment_method,
            )
    except (DataValidationError, ValueError) as error:
        parser.exit(1, f"Query error: {error}\n")
    if not results:
        print("No products match the supplied criteria.")
    for offer in results:
        _print_offer(offer)


if __name__ == "__main__":
    main()
