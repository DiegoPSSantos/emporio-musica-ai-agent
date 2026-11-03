"""Ferramentas de leitura que o modelo pode solicitar; nenhum código é executado por nome livre."""

from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Optional

from emporio.catalog import Catalog, ProductOffer
from emporio.data import DEFAULT_DATA_DIR, DataValidationError, load_dataset
from emporio.policies import PolicyIndexError, load_policies
from emporio.text import normalize_text


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
    _tool("list_categories", "Lista os nomes exatos das categorias de instrumentos.", {}),
    _tool("search_products", "Consulta nomes, estoque e preços atuais. Use category para tipos de instrumento; query contém apenas termos do nome, não a pergunta inteira.", {
        "query": TEXT,
        "category": {**TEXT, "description": "Nome completo de uma categoria retornada por list_categories."},
        "max_price": {**TEXT, "description": "Preço máximo como texto decimal sem separador de milhar, por exemplo 1000.00."},
        "payment_method": PAYMENT,
        "available_only": {"type": "boolean"},
        "limit": {"type": "integer", "minimum": 1, "maximum": 20},
    }),
    _tool("get_product", "Consulta um produto pelo ID, incluindo sua indisponibilidade.", {
        "product_id": POSITIVE_ID, "payment_method": PAYMENT,
    }, ["product_id"]),
    _tool("search_policies", "Recupera seções do manual, com páginas de origem, sobre horários, endereço, pagamento, frete, trocas e outras políticas.", {
        "query": {**TEXT, "minLength": 1},
        "limit": {"type": "integer", "minimum": 1, "maximum": 3},
    }, ["query"]),
    _tool("get_policy_section", "Lê uma seção completa: 1 dados da loja; 2 horários; 3 pagamentos; 4 trocas; 5 entregas; 6 promoções; 7 atendimento; 8 garantia; 9 privacidade; 10 disposições finais.", {
        "section_id": {"type": "string", "enum": [str(i) for i in range(1, 11)]},
    }, ["section_id"]),
    _tool("get_order", "Consulta apenas um pedido do cliente vinculado à sessão. Não aceita identidade de cliente como argumento.", {
        "order_id": POSITIVE_ID,
    }, ["order_id"]),
]
SCHEMAS_BY_NAME = {tool["function"]["name"]: tool["function"]["parameters"] for tool in TOOL_SCHEMAS}
CATEGORY_TERMS = {
    "violoes": {"violao", "violoes"},
    "guitarras": {"guitarra", "guitarras"},
    "baixos": {"baixo", "baixos"},
    "ukuleles": {"ukulele", "ukuleles"},
    "baterias e percussao": {"bateria", "baterias", "percussao"},
    "teclados e pianos": {"teclado", "teclados", "piano", "pianos"},
}


def _validate_arguments(name: str, arguments: dict) -> None:
    schema = SCHEMAS_BY_NAME[name]
    if not isinstance(arguments, dict):
        raise ValueError("Os argumentos devem ser um objeto JSON.")
    if set(arguments) - set(schema["properties"]):
        raise ValueError("A ferramenta recebeu campos não permitidos.")
    if set(schema["required"]) - set(arguments):
        raise ValueError("Faltam argumentos obrigatórios.")
    for key, value in arguments.items():
        field = schema["properties"][key]
        expected = {"string": str, "integer": int, "boolean": bool}[field["type"]]
        if type(value) is not expected:
            raise ValueError(f"Tipo inválido no argumento {key}.")
        if "enum" in field and value not in field["enum"]:
            raise ValueError(f"Valor não permitido no argumento {key}.")
        if isinstance(value, str):
            if not field.get("minLength", 0) <= len(value) <= field.get("maxLength", 500):
                raise ValueError(f"Tamanho inválido no argumento {key}.")
        elif type(value) is int:
            if value < field.get("minimum", value) or value > field.get("maximum", value):
                raise ValueError(f"Valor fora dos limites no argumento {key}.")


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
            raise ValueError("O cliente da sessão deve ter um ID inteiro positivo.")
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
            return {"error": {"code": "unknown_tool", "message": "Ferramenta não permitida."}}
        try:
            _validate_arguments(name, arguments)
            return self._handlers[name](**arguments)
        except (DataValidationError, PolicyIndexError):
            return {"error": {"code": "data_unavailable", "message": "Não foi possível consultar a fonte. Não confirme dados sem consulta válida."}}
        except (ValueError, InvalidOperation):
            return {"error": {"code": "invalid_arguments", "message": "Argumentos inválidos. Corrija os campos conforme o esquema da ferramenta."}}

    def _list_categories(self) -> dict:
        data = load_dataset(self.data_dir)
        return {"categories": [{"category_id": c.category_id, "name": c.name}
                               for c in data.categories.values()], "source": "categories.csv"}

    def _search_products(self, query="", category=None, max_price=None,
                         payment_method="standard", available_only=True, limit=5) -> dict:
        # O modelo pode repetir o tipo genérico em query, embora ele já esteja na categoria.
        if category and normalize_text(query) in CATEGORY_TERMS.get(normalize_text(category), set()):
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
        store = load_policies(self.data_dir / "politicas_da_loja.json")
        return {"sections": [_section(match.section) for match in store.search(query, limit)]}

    def _get_policy_section(self, section_id) -> dict:
        section = load_policies(self.data_dir / "politicas_da_loja.json").get_section(section_id)
        return {"section": _section(section) if section else None}

    def _get_order(self, order_id) -> dict:
        if self.customer_id is None:
            return {"error": {"code": "session_required", "message": "A consulta exige uma sessão de cliente identificada pela aplicação. Não solicite senha ou identidade no chat."}}
        data = load_dataset(self.data_dir)
        order = data.orders.get(order_id)
        if order is None or order.customer_id != self.customer_id:
            # A mesma resposta evita confirmar a existência de pedidos de terceiros.
            return {"error": {"code": "order_not_found", "message": "Pedido não encontrado para o cliente desta sessão."}}
        return {"order": {
            "order_id": order.order_id, "order_date": order.order_date.isoformat(),
            "status": order.status, "total_brl": str(order.total_brl),
            "payment_method": order.payment_method, "tracking_code": order.tracking_code,
            "estimated_delivery": order.estimated_delivery.isoformat() if order.estimated_delivery else None,
            "items": [{"product_id": item.product_id, "name": data.products[item.product_id].name,
                       "quantity": item.quantity} for item in data.order_items if item.order_id == order_id],
        }, "sources": ["orders.csv", "order_items.csv", "products.csv"]}
