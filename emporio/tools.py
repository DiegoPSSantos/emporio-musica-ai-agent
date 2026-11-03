"""Read-only model tools; arbitrary names never execute application code."""

from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Optional

from emporio.catalog import Catalog, ProductOffer
from emporio.data import DEFAULT_DATA_DIR, DataValidationError, load_dataset
from emporio.policies import PolicyIndexError, load_policies
from emporio.text import normalize_text
from emporio.localization import category_key, category_label


def _tool(name, description, properties, required=()):
    return {"type": "function", "function": {
        "name": name, "description": description,
        "parameters": {"type": "object", "properties": properties,
                       "required": list(required), "additionalProperties": False},
    }}


TEXT = {"type": "string", "maxLength": 500}
PAYMENT = {"type": "string", "enum": ["standard", "pix"]}
POSITIVE_ID = {"type": "integer", "minimum": 1}
TOOL_SCHEMAS = [
    _tool("list_categories", "List the exact English names of instrument categories.", {}),
    _tool("search_products", "Look up current product names, stock and prices. Use category for instrument types; query must contain only name terms, not the whole question.", {
        "query": TEXT,
        "category": {**TEXT, "description": "Full category name returned by list_categories."},
        "max_price": {**TEXT, "description": "Maximum price as a decimal string without thousands separators, for example 1000.00."},
        "payment_method": PAYMENT,
        "available_only": {"type": "boolean"},
        "limit": {"type": "integer", "minimum": 1, "maximum": 20},
    }),
    _tool("get_product", "Look up a product by ID, including unavailable products.", {
        "product_id": POSITIVE_ID, "payment_method": PAYMENT,
    }, ["product_id"]),
    _tool("search_policies", "Retrieve English manual sections with source pages about opening hours, address, payment, shipping, returns and other policies.", {
        "query": {**TEXT, "minLength": 1},
        "limit": {"type": "integer", "minimum": 1, "maximum": 3},
    }, ["query"]),
    _tool("get_policy_section", "Read a complete section: 1 store details; 2 opening hours; 3 payments; 4 returns; 5 shipping; 6 promotions; 7 customer support; 8 warranty; 9 privacy; 10 final provisions.", {
        "section_id": {"type": "string", "enum": [str(i) for i in range(1, 11)]},
    }, ["section_id"]),
    _tool("get_order", "Look up only an order owned by the customer bound to this session. Customer identity is not an argument.", {
        "order_id": POSITIVE_ID,
    }, ["order_id"]),
]
SCHEMAS_BY_NAME = {tool["function"]["name"]: tool["function"]["parameters"] for tool in TOOL_SCHEMAS}
CATEGORY_TERMS = {
    "acoustic guitars": {"guitar", "guitars", "acoustic guitar", "acoustic guitars", "classical guitar", "classical guitars", "violao", "violoes"},
    "electric guitars": {"guitar", "guitars", "electric guitar", "electric guitars", "guitarra", "guitarras"},
    "bass guitars": {"bass", "bass guitar", "bass guitars", "baixo", "baixos"},
    "drums and percussion": {"drum", "drums", "percussion", "bateria", "baterias"},
    "keyboards and pianos": {"keyboard", "keyboards", "piano", "pianos", "teclado", "teclados"},
    "ukuleles": {"ukulele", "ukuleles"},
}


def _validate_arguments(name: str, arguments: dict) -> None:
    schema = SCHEMAS_BY_NAME[name]
    if not isinstance(arguments, dict):
        raise ValueError("Arguments must be a JSON object.")
    if set(arguments) - set(schema["properties"]):
        raise ValueError("The tool received unsupported fields.")
    if set(schema["required"]) - set(arguments):
        raise ValueError("Required arguments are missing.")
    for key, value in arguments.items():
        field = schema["properties"][key]
        expected = {"string": str, "integer": int, "boolean": bool}[field["type"]]
        if type(value) is not expected:
            raise ValueError(f"Invalid type for argument {key}.")
        if "enum" in field and value not in field["enum"]:
            raise ValueError(f"Unsupported value for argument {key}.")
        if isinstance(value, str):
            if not field.get("minLength", 0) <= len(value) <= field.get("maxLength", 500):
                raise ValueError(f"Invalid length for argument {key}.")
        elif type(value) is int:
            if value < field.get("minimum", value) or value > field.get("maximum", value):
                raise ValueError(f"Value out of range for argument {key}.")


def _product(offer: ProductOffer) -> dict:
    product = offer.product
    return {
        "product_id": product.product_id, "name": product.name,
        "category": offer.category, "description": product.description,
        "status": product.status, "stock_quantity": product.stock_quantity,
        "available": offer.available, "specs": product.specs,
        "list_price_brl": str(product.price_brl),
        "price_brl": str(offer.price_brl) if offer.available else None,
        "discount_percent": str(offer.discount_percent),
        "discount_source": offer.discount_source,
        "promotion_description": offer.promotion_description,
    }


def _section(section) -> dict:
    return {"section_id": section.section_id, "title": section.title,
            "pages": list(section.pages), "source": section.source, "text": section.text}


class Toolbox:
    def __init__(self, data_dir: Path = DEFAULT_DATA_DIR, customer_id: Optional[int] = None):
        if customer_id is not None and (type(customer_id) is not int or customer_id < 1):
            raise ValueError("The session customer ID must be a positive integer.")
        self.data_dir = Path(data_dir)
        self.customer_id = customer_id
        self._handlers = {
            "list_categories": self._list_categories,
            "search_products": self._search_products,
            "get_product": self._get_product,
            "search_policies": self._search_policies,
            "get_policy_section": self._get_policy_section,
            "get_order": self._get_order,
        }

    def execute(self, name: str, arguments: dict) -> dict:
        if name not in self._handlers:
            return {"error": {"code": "unknown_tool", "message": "Tool not allowed."}}
        try:
            _validate_arguments(name, arguments)
            return self._handlers[name](**arguments)
        except (DataValidationError, PolicyIndexError):
            return {"error": {"code": "data_unavailable", "message": "Could not query the source. Do not confirm facts without a successful lookup."}}
        except (ValueError, InvalidOperation):
            return {"error": {"code": "invalid_arguments", "message": "Invalid arguments. Correct the fields according to the tool schema."}}

    def _list_categories(self) -> dict:
        data = load_dataset(self.data_dir)
        return {"categories": [{"category_id": c.category_id, "name": category_label(c.name)}
                               for c in data.categories.values()], "source": "categories.csv"}

    def _search_products(self, query="", category=None, max_price=None,
                         payment_method="standard", available_only=True, limit=5) -> dict:
        # The model may repeat a generic type in query even when category already specifies it.
        if category and normalize_text(query) in CATEGORY_TERMS.get(category_key(category), set()):
            query = ""
        maximum = Decimal(max_price.replace(",", ".")) if max_price is not None else None
        offers = Catalog(load_dataset(self.data_dir)).search_products(
            query, category, maximum, available_only, payment_method
        )
        return {"products": [_product(offer) for offer in offers[:limit]],
                "total_matches": len(offers), "truncated": len(offers) > limit,
                "sources": ["products.csv", "promotions.csv"]}

    def _get_product(self, product_id, payment_method="standard") -> dict:
        offer = Catalog(load_dataset(self.data_dir)).get_product(product_id, payment_method)
        return {"product": _product(offer) if offer else None,
                "sources": ["products.csv", "promotions.csv"]}

    def _search_policies(self, query, limit=3) -> dict:
        store = load_policies(self.data_dir / "policies.en.json")
        return {"sections": [_section(match.section) for match in store.search(query, limit)]}

    def _get_policy_section(self, section_id) -> dict:
        section = load_policies(self.data_dir / "policies.en.json").get_section(section_id)
        return {"section": _section(section) if section else None}

    def _get_order(self, order_id) -> dict:
        if self.customer_id is None:
            return {"error": {"code": "session_required", "message": "Order details require an identified customer session. Please contact the store team for help."}}
        data = load_dataset(self.data_dir)
        order = data.orders.get(order_id)
        if order is None or order.customer_id != self.customer_id:
            # An identical response avoids confirming the existence of other customers' orders.
            return {"error": {"code": "order_not_found", "message": "Order not found for the customer in this session."}}
        return {"order": {
            "order_id": order.order_id, "order_date": order.order_date.isoformat(),
            "status": order.status, "total_brl": str(order.total_brl),
            "payment_method": order.payment_method, "tracking_code": order.tracking_code,
            "estimated_delivery": order.estimated_delivery.isoformat() if order.estimated_delivery else None,
            "items": [{"product_id": item.product_id, "name": data.products[item.product_id].name,
                       "quantity": item.quantity} for item in data.order_items if item.order_id == order_id],
        }, "sources": ["orders.csv", "order_items.csv", "products.csv"]}
