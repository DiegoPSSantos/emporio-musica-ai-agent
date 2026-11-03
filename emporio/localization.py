"""English display labels and lookup aliases for the original Portuguese catalog."""

from emporio.text import normalize_text


CATEGORY_LABELS = {
    "guitarras": "Electric guitars", "baixos": "Bass guitars",
    "baterias e percussao": "Drums and percussion", "teclados e pianos": "Keyboards and pianos",
    "violoes": "Acoustic guitars", "instrumentos de sopro madeiras": "Woodwind instruments",
    "instrumentos de sopro metais": "Brass instruments", "cordas orquestrais": "Orchestral strings",
    "ukuleles": "Ukuleles",
}
CATEGORY_ALIASES = {
    "electric guitar": "Electric guitars", "guitarra": "Electric guitars",
    "bass": "Bass guitars", "bass guitar": "Bass guitars", "baixo": "Bass guitars",
    "acoustic guitar": "Acoustic guitars", "classical guitar": "Acoustic guitars",
    "classical guitars": "Acoustic guitars", "violao": "Acoustic guitars",
    "drums": "Drums and percussion", "drum": "Drums and percussion", "bateria": "Drums and percussion",
    "keyboard": "Keyboards and pianos", "keyboards": "Keyboards and pianos",
    "piano": "Keyboards and pianos", "pianos": "Keyboards and pianos", "teclado": "Keyboards and pianos",
    "woodwinds": "Woodwind instruments", "brass": "Brass instruments", "ukulele": "Ukuleles",
}
PROMOTION_LABELS = {
    "black friday": "Black Friday", "liquidacao de inverno": "Winter sale",
    "queima de estoque": "Stock clearance", "oferta especial": "Special offer",
    "aniversario da loja": "Store anniversary", "promocao de pascoa": "Easter promotion",
    "semana do musico": "Musician's Week", "desconto exclusivo": "Exclusive discount",
}


def category_label(name: str) -> str:
    key = normalize_text(name)
    return CATEGORY_LABELS.get(key, CATEGORY_ALIASES.get(key, name))


def category_key(name: str) -> str:
    return normalize_text(category_label(name))


def promotion_label(name: str) -> str:
    return PROMOTION_LABELS.get(normalize_text(name), name)
