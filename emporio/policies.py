"""Busca local de seções do manual com referências à fonte, sem gerar respostas."""

import argparse
import hashlib
import json
import math
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from emporio.data import DEFAULT_DATA_DIR
from emporio.text import normalize_text


DEFAULT_POLICY_INDEX = DEFAULT_DATA_DIR / "politicas_da_loja.json"
STOP_WORDS = set(
    "a as o os um uma uns umas de da das do dos em na nas no nos para por com "
    "e ou que qual quais como quanto quantos quando eu meu minha meus minhas "
    "voce voces sua suas seu seus me se ao aos pela pelo quero gostaria saber "
    "posso pode podem preciso tem ter eh e esta estao loja favor".split()
)
SYNONYM_GROUPS = (
    ("horario", "horarios", "horas", "abre", "abrem", "abrir", "fecha", "fecham"),
    ("sabado", "sabados"),
    ("domingo", "domingos"),
    ("pagamento", "pagamentos", "pagar", "aceitam"),
    ("parcelamento", "parcelar", "parcelas", "parcela", "vezes"),
    ("devolucao", "devolucoes", "devolver", "devolvido", "devolvida"),
    ("troca", "trocas", "trocar"),
    ("entrega", "entregas", "entregar", "envio", "envios"),
    ("garantia", "garantias"),
    ("desconto", "descontos"),
    ("promocao", "promocoes", "promocional", "promocionais"),
    ("endereco", "localizacao"),
)
SYNONYMS = {word: group[0] for group in SYNONYM_GROUPS for word in group}


def _tokens(text: str) -> list[str]:
    return [
        SYNONYMS.get(word, word) for word in normalize_text(text).split()
        if word not in STOP_WORDS and not word.isdigit()
    ]


class PolicyIndexError(ValueError):
    """O índice não pode ser usado ou precisa ser regenerado."""


@dataclass(frozen=True)
class PolicySection:
    section_id: str
    title: str
    pages: tuple[int, ...]
    text: str
    source: str
    anchors: tuple[str, ...]


@dataclass(frozen=True)
class PolicyMatch:
    section: PolicySection
    score: float


class PolicyStore:
    def __init__(self, sections: tuple[PolicySection, ...]):
        if not sections:
            raise PolicyIndexError("O índice não contém seções.")
        self.sections = sections
        self._counts = [Counter(_tokens(section.text)) for section in sections]
        self._average_length = sum(sum(count.values()) for count in self._counts) / len(sections)
        self._document_frequency = Counter(word for count in self._counts for word in count)
        self._anchor_terms = [set(_tokens(" ".join(section.anchors))) for section in sections]

    def get_section(self, section_id: str) -> Optional[PolicySection]:
        return next((section for section in self.sections if section.section_id == section_id), None)

    def search(self, query: str, limit: int = 3) -> list[PolicyMatch]:
        """Ranking BM25 por termos; a pontuação não é uma medida de confiança."""
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 10:
            raise ValueError("O limite deve ser um inteiro entre 1 e 10.")
        terms = sorted(set(_tokens(query)))
        if not terms or not self._average_length:
            return []
        matches = []
        total = len(self.sections)
        for section, counts, anchors in zip(self.sections, self._counts, self._anchor_terms):
            length = sum(counts.values())
            score = 0.0
            for term in terms:
                frequency = counts[term]
                if not frequency:
                    continue
                documents = self._document_frequency[term]
                inverse_frequency = math.log(1 + (total - documents + 0.5) / (documents + 0.5))
                score += inverse_frequency * frequency * 2.5 / (
                    frequency + 1.5 * (0.25 + 0.75 * length / self._average_length)
                )
                if term in anchors:
                    score += 2 * inverse_frequency
            if score > 0:
                matches.append(PolicyMatch(section, score))
        return sorted(matches, key=lambda match: (-match.score, int(match.section.section_id)))[:limit]


def load_policies(index_path: Path = DEFAULT_POLICY_INDEX) -> PolicyStore:
    """Valida o índice e a assinatura do PDF antes de permitir consultas."""
    index_path = Path(index_path)
    try:
        index = json.loads(index_path.read_text(encoding="utf-8"))
        if not isinstance(index, dict) or index.get("schema_version") != 1:
            raise PolicyIndexError("Formato ou versão de índice inválido.")
        source = index.get("source")
        if not isinstance(source, str) or not source or Path(source).name != source:
            raise PolicyIndexError("Nome de arquivo fonte inválido.")
        digest = hashlib.sha256((index_path.parent / source).read_bytes()).hexdigest()
        if digest != index.get("source_sha256"):
            raise PolicyIndexError("O PDF mudou; regenere o índice de políticas antes de consultar.")
        raw_sections = index.get("sections")
        if not isinstance(raw_sections, list) or not raw_sections:
            raise PolicyIndexError("O índice não contém seções.")
        sections = []
        for position, item in enumerate(raw_sections, start=1):
            if not isinstance(item, dict) or item.get("section_id") != str(position):
                raise PolicyIndexError("Identificação ou ordem de seções inválida.")
            if not all(isinstance(item.get(key), str) and item[key].strip() for key in ("title", "text")):
                raise PolicyIndexError("Título ou texto de seção inválido.")
            anchors = item.get("anchors")
            if not isinstance(anchors, list) or not all(
                isinstance(anchor, str) and anchor.strip() for anchor in anchors
            ):
                raise PolicyIndexError("Títulos ou rótulos de busca inválidos.")
            pages = item.get("pages")
            if not isinstance(pages, list) or not pages or any(
                type(page) is not int or page < 1 for page in pages
            ) or pages != sorted(set(pages)):
                raise PolicyIndexError("Referências de páginas inválidas.")
            sections.append(PolicySection(
                item["section_id"], item["title"], tuple(pages), item["text"], source, tuple(anchors)
            ))
        return PolicyStore(tuple(sections))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise PolicyIndexError(f"Não foi possível ler o índice ou o PDF ({type(error).__name__}).") from None


def main() -> None:
    parser = argparse.ArgumentParser(description="Recupera trechos do manual da loja.")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--index", type=Path, default=DEFAULT_POLICY_INDEX)
    commands = parser.add_subparsers(dest="command", required=True)
    search = commands.add_parser("search", parents=[common], help="Busca seções por palavras e sinônimos.")
    search.add_argument("query")
    search.add_argument("--limit", type=int, default=3)
    show = commands.add_parser("show", parents=[common], help="Mostra uma seção completa pelo número.")
    show.add_argument("section_id")
    args = parser.parse_args()
    try:
        store = load_policies(args.index)
        if args.command == "show":
            section = store.get_section(args.section_id)
            sections = [section] if section is not None else []
        else:
            sections = [match.section for match in store.search(args.query, args.limit)]
    except (PolicyIndexError, ValueError) as error:
        parser.exit(1, f"Erro na consulta de políticas: {error}\n")
    if not sections:
        print("Nenhuma seção encontrada. Reformule a busca ou consulte a equipe da loja.")
    for section in sections:
        pages = ", ".join(map(str, section.pages))
        print(f"Fonte: {section.source} | seção {section.section_id} | páginas {pages}")
        print(section.text)
        print()


if __name__ == "__main__":
    main()
