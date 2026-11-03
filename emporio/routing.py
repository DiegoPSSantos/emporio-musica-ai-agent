"""Recover a source lookup when the model omits a required tool."""

import re
from typing import Optional

from emporio.text import normalize_text


POLICY_TOPICS = (
    ({"hours", "opening", "saturday", "open", "horario", "horas", "sabado", "abre"}, "opening hours"),
    ({"return", "returns", "withdrawal", "exchange", "refund", "devolver", "devolucao", "arrependi", "troca", "reembolso"}, "returns exchanges withdrawal"),
    ({"discount", "discounts", "promotion", "promotions", "combine", "combined", "stack", "stacked", "desconto", "promocao", "acumulado", "acumula"}, "promotion discount stacking"),
    ({"pix", "payment", "payments", "pay", "installments", "credit", "debit", "pagamento", "pagar", "parcelar", "boleto"}, "payment pix installments"),
    ({"shipping", "delivery", "deliveries", "frete", "entrega", "envio"}, "shipping delivery"),
    ({"warranty", "warranties", "defect", "defects", "garantia", "defeito"}, "warranty defects"),
    ({"address", "location", "contact", "phone", "whatsapp", "endereco", "telefone"}, "address phone whatsapp"),
    ({"privacy", "deletion", "consent", "lgpd", "privacidade", "exclusao"}, "privacy data"),
)
ACCESSORIES = {"cable", "cables", "pick", "picks", "pedal", "pedals", "case", "cases", "amplifier", "amplifiers", "accessories",
               "cabo", "cabos", "palheta", "palhetas", "pedais", "amplificador", "amplificadores"}


def fallback_lookup(text: str) -> Optional[dict]:
    """Select only reads; do not answer the question or grant access.

    This small bilingual vocabulary covers explicit store topics. It is not a
    general semantic classifier and is used only if the model requests no lookup.
    """
    normalized = normalize_text(text)
    words = set(normalized.split())
    order = re.search(r"\b(?:order|pedido)\s+(?:(?:number|numero|no|n|id)\s+)?(\d+)\b", normalized)
    if order:
        return {"name": "get_order", "arguments": {"order_id": int(order.group(1))}}
    if words & ACCESSORIES:
        return {"name": "get_policy_section", "arguments": {"section_id": "1"}}
    topics = [query for triggers, query in POLICY_TOPICS if words & triggers]
    if topics:
        return {"name": "search_policies", "arguments": {"query": " ".join(topics)}}
    return None
