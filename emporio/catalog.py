"""Consultas de catálogo e cálculo de preços, independentes do modelo de linguagem."""

import argparse
import unicodedata
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Optional

from emporio.data import DEFAULT_DATA_DIR, DataValidationError, Dataset, Product, load_dataset


def _normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return " ".join(
        "".join(
            character if character.isalnum() else " "
            for character in decomposed
            if not unicodedata.combining(character)
        ).split()
    )


def _validate_payment_method(payment_method: str) -> None:
    if payment_method not in {"standard", "pix"}:
        raise ValueError("Forma de pagamento deve ser standard ou pix.")


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
    """Consulta uma fotografia validada dos dados, sem modificar os originais."""

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
            # Não acumular campanhas. Em empate, usar o menor ID para manter estabilidade.
            promotion = max(
                active_promotions,
                key=lambda item: (item.discount_percent, -item.promotion_id),
                default=None,
            )
            if promotion is not None:
                discount = promotion.discount_percent
                source = "promotion"
                description = promotion.description
            elif payment_method == "pix":
                discount = Decimal("5")
                source = "pix"

        price = (product.price_brl * (1 - discount / 100)).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        return ProductOffer(
            product=product,
            category=self.dataset.categories[product.category_id].name,
            available=available,
            price_brl=price,
            discount_percent=discount,
            discount_source=source,
            promotion_description=description,
        )

    def get_product(
        self, product_id: int, payment_method: str = "standard"
    ) -> Optional[ProductOffer]:
        """Retorna também produtos indisponíveis, para explicar sua situação."""
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
        """Busca termos no nome; filtra categoria e preço final inclusivo."""
        _validate_payment_method(payment_method)
        if max_price is not None:
            if not isinstance(max_price, Decimal):
                raise TypeError("O preço máximo deve ser informado como Decimal.")
            if not max_price.is_finite() or max_price < 0:
                raise ValueError("O preço máximo deve ser finito e não negativo.")
        terms = _normalize(query).split()
        normalized_category = _normalize(category) if category is not None else None
        results = []
        for product in self.dataset.products.values():
            normalized_name = _normalize(product.name)
            if not all(term in normalized_name for term in terms):
                continue
            offer = self._offer(product, payment_method)
            if available_only and not offer.available:
                continue
            if normalized_category is not None and _normalize(offer.category) != normalized_category:
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
            "Informe um preço não negativo, como 1000 ou 999,90, sem separador de milhar."
        ) from None


def _brl(value: Decimal) -> str:
    return "R$ " + format(value, ",.2f").translate(str.maketrans({",": ".", ".": ","}))


def _print_offer(offer: ProductOffer) -> None:
    product = offer.product
    print(f"[{product.product_id}] {product.name}")
    print(f"  Categoria: {offer.category}")
    if offer.available:
        print(f"  Situação: disponível ({product.stock_quantity} unidades)")
    else:
        status = {
            "active": "sem estoque",
            "discontinued": "descontinuado",
            "coming_soon": "lançamento futuro, ainda indisponível",
        }.get(product.status, "status não reconhecido, disponibilidade não confirmada")
        print(f"  Situação: {status}")
    print(f"  Preço de tabela: {_brl(product.price_brl)}")
    if offer.discount_source is not None:
        reason = offer.promotion_description if offer.discount_source == "promotion" else "PIX"
        print(f"  Desconto: {offer.discount_percent}% ({reason})")
    if offer.available:
        print(f"  Preço final: {_brl(offer.price_brl)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Consulta o catálogo da Empório da Música.")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    common.add_argument("--payment-method", choices=["standard", "pix"], default="standard")
    commands = parser.add_subparsers(dest="command", required=True)
    search = commands.add_parser("search", parents=[common], help="Busca produtos.")
    search.add_argument("--query", default="", help="Termos procurados no nome do produto.")
    search.add_argument("--category", help="Nome completo da categoria, com ou sem acentos.")
    search.add_argument("--max-price", type=_money_argument)
    search.add_argument("--include-unavailable", action="store_true")
    show = commands.add_parser("show", parents=[common], help="Consulta um produto pelo ID.")
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
        parser.exit(1, f"Erro na consulta: {error}\n")
    if not results:
        print("Nenhum produto encontrado para os critérios informados.")
    for offer in results:
        _print_offer(offer)


if __name__ == "__main__":
    main()
