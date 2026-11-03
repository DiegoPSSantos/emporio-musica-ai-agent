"""Consultas de recuperação quando o modelo omite uma ferramenta necessária."""

import re
from typing import Optional

from emporio.text import normalize_text


POLICY_TOPICS = (
    ({"horario", "horarios", "horas", "funcionamento", "sabado", "abre", "abrem"}, "horario funcionamento"),
    ({"devolver", "devolucao", "devolucoes", "arrependi", "arrependimento", "troca", "trocas", "trocar", "reembolso"}, "troca devolucao arrependimento"),
    ({"desconto", "descontos", "promocao", "promocoes", "acumular", "acumulado", "acumulados"}, "promocao desconto cumulatividade"),
    ({"pix", "pagamento", "pagamentos", "pagar", "parcelar", "parcelas", "boleto", "credito", "debito"}, "pagamento pix parcelamento"),
    ({"frete", "entrega", "entregas", "envio", "envios"}, "frete entrega"),
    ({"garantia", "garantias", "defeito", "defeitos"}, "garantia defeito"),
    ({"endereco", "localizacao", "contato", "telefone", "whatsapp"}, "endereco telefone whatsapp"),
    ({"privacidade", "lgpd", "exclusao", "consentimento"}, "privacidade dados"),
)
ACCESSORIES = {"cabo", "cabos", "palheta", "palhetas", "pedal", "pedais", "case", "cases", "amplificador", "amplificadores"}


def fallback_lookup(text: str) -> Optional[dict]:
    """Seleciona apenas leituras; não responde a pergunta nem concede acesso.

    Este vocabulário pequeno cobre tópicos explícitos da loja. Não é uma
    classificação semântica geral e só é usado se o modelo não pedir consulta.
    """
    normalized = normalize_text(text)
    words = set(normalized.split())
    order = re.search(r"\bpedido\s+(?:(?:numero|no|n|id)\s+)?(\d+)\b", normalized)
    if order:
        return {"name": "get_order", "arguments": {"order_id": int(order.group(1))}}
    if words & ACCESSORIES:
        return {"name": "get_policy_section", "arguments": {"section_id": "1"}}
    topics = [query for triggers, query in POLICY_TOPICS if words & triggers]
    if topics:
        return {"name": "search_policies", "arguments": {"query": " ".join(topics)}}
    return None
