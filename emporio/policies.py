"""Retrieve manual sections locally with source references, without generating answers."""

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


DEFAULT_POLICY_INDEX = DEFAULT_DATA_DIR / "policies.en.json"
STOP_WORDS = set(
    "a as o os um uma uns umas de da das do dos em na nas no nos para por com "
    "e ou que qual quais como quanto quantos quando eu meu minha meus minhas "
    "voce voces sua suas seu seus me se ao aos pela pelo quero gostaria saber "
    "posso pode podem preciso tem ter eh e esta estao loja favor "
    "the a an and or of to for in on at by with from is are am be been "
    "i my me we our you your can could may would please what which how when "
    "do does did this that it its store shop have has want need tell about".split()
)
SYNONYM_GROUPS = (
    ("horario", "horarios", "horas", "abre", "abrem", "abrir", "fecha", "fecham", "hours", "opening", "open", "schedule"),
    ("sabado", "sabados", "saturday", "saturdays"),
    ("domingo", "domingos", "sunday", "sundays"),
    ("pagamento", "pagamentos", "pagar", "aceitam", "payment", "payments", "pay", "accept"),
    ("parcelamento", "parcelar", "parcelas", "parcela", "vezes", "installment", "installments"),
    ("devolucao", "devolucoes", "devolver", "devolvido", "devolvida", "return", "returns", "withdrawal", "arrependimento", "arrependi"),
    ("troca", "trocas", "trocar", "exchange", "exchanges"),
    ("entrega", "entregas", "entregar", "envio", "envios", "delivery", "deliveries", "shipping", "frete"),
    ("garantia", "garantias", "warranty", "warranties"),
    ("desconto", "descontos", "discount", "discounts"),
    ("promocao", "promocoes", "promocional", "promocionais", "promotion", "promotions", "promotional"),
    ("endereco", "localizacao", "address", "location"),
    ("defeito", "defeitos", "defect", "defects"),
    ("privacidade", "privacy"),
    ("dados", "data"),
)
SYNONYMS = {word: group[0] for group in SYNONYM_GROUPS for word in group}


def _tokens(text: str) -> list[str]:
    return [
        SYNONYMS.get(word, word) for word in normalize_text(text).split()
        if word not in STOP_WORDS and not word.isdigit()
    ]


class PolicyIndexError(ValueError):
    """The index cannot be used or must be regenerated."""


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
            raise PolicyIndexError("The index contains no sections.")
        self.sections = sections
        self._counts = [Counter(_tokens(section.text)) for section in sections]
        self._average_length = sum(sum(count.values()) for count in self._counts) / len(sections)
        self._document_frequency = Counter(word for count in self._counts for word in count)
        self._anchor_terms = [set(_tokens(" ".join(section.anchors))) for section in sections]

    def get_section(self, section_id: str) -> Optional[PolicySection]:
        return next((section for section in self.sections if section.section_id == section_id), None)

    def search(self, query: str, limit: int = 3) -> list[PolicyMatch]:
        """Rank terms with BM25; the score is not a confidence measure."""
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 10:
            raise ValueError("Limit must be an integer between 1 and 10.")
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
    """Validate the index and PDF signature before allowing queries."""
    index_path = Path(index_path)
    try:
        index = json.loads(index_path.read_text(encoding="utf-8"))
        if not isinstance(index, dict) or index.get("schema_version") != 1:
            raise PolicyIndexError("Invalid index format or version.")
        source = index.get("source")
        if not isinstance(source, str) or not source or Path(source).name != source:
            raise PolicyIndexError("Invalid source filename.")
        digest = hashlib.sha256((index_path.parent / source).read_bytes()).hexdigest()
        if digest != index.get("source_sha256"):
            raise PolicyIndexError("The PDF changed; rebuild the policy index before querying it.")
        if index.get("language") == "en":
            original_name = index.get("translation_of", "")
            if not original_name or Path(original_name).name != original_name:
                raise PolicyIndexError("Invalid translation source filename.")
            original_bytes = (index_path.parent / original_name).read_bytes()
            if hashlib.sha256(original_bytes).hexdigest() != index.get("translation_source_sha256"):
                raise PolicyIndexError("The source index changed; review and update the English reference translation.")
            original = json.loads(original_bytes)
            if not isinstance(original, dict) or not isinstance(original.get("sections"), list):
                raise PolicyIndexError("Invalid translation source index.")
            translated = index.get("sections")
            if not isinstance(translated, list) or len(translated) != len(original["sections"]):
                raise PolicyIndexError("The translation must cover every source section.")
            for source_section, translation in zip(original["sections"], translated):
                if not isinstance(source_section, dict) or not isinstance(translation, dict) or any(
                    translation.get(key) != source_section.get(key) for key in ("section_id", "pages")
                ):
                    raise PolicyIndexError("Translation section or page references do not match the source.")
        raw_sections = index.get("sections")
        if not isinstance(raw_sections, list) or not raw_sections:
            raise PolicyIndexError("The index contains no sections.")
        sections = []
        for position, item in enumerate(raw_sections, start=1):
            if not isinstance(item, dict) or item.get("section_id") != str(position):
                raise PolicyIndexError("Invalid section identifiers or ordering.")
            if not all(isinstance(item.get(key), str) and item[key].strip() for key in ("title", "text")):
                raise PolicyIndexError("Invalid section title or text.")
            anchors = item.get("anchors")
            if not isinstance(anchors, list) or not all(
                isinstance(anchor, str) and anchor.strip() for anchor in anchors
            ):
                raise PolicyIndexError("Invalid search headings or labels.")
            pages = item.get("pages")
            if not isinstance(pages, list) or not pages or any(
                type(page) is not int or page < 1 for page in pages
            ) or pages != sorted(set(pages)):
                raise PolicyIndexError("Invalid page references.")
            sections.append(PolicySection(
                item["section_id"], item["title"], tuple(pages), item["text"], source, tuple(anchors)
            ))
        return PolicyStore(tuple(sections))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise PolicyIndexError(f"Could not read the index or PDF ({type(error).__name__}).") from None


def main() -> None:
    parser = argparse.ArgumentParser(description="Retrieve passages from the store manual.")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--index", type=Path, default=DEFAULT_POLICY_INDEX)
    commands = parser.add_subparsers(dest="command", required=True)
    search = commands.add_parser("search", parents=[common], help="Search sections by terms and synonyms.")
    search.add_argument("query")
    search.add_argument("--limit", type=int, default=3)
    show = commands.add_parser("show", parents=[common], help="Show a complete section by number.")
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
        parser.exit(1, f"Policy query error: {error}\n")
    if not sections:
        print("No section found. Rephrase the query or contact the store team.")
    for section in sections:
        pages = ", ".join(map(str, section.pages))
        print(f"Source: {section.source} | section {section.section_id} | pages {pages}")
        print(section.text)
        print()


if __name__ == "__main__":
    main()
