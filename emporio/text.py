"""Text normalization shared by catalog and policy search."""

import unicodedata


def normalize_text(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return " ".join(
        "".join(
            character if character.isalnum() else " "
            for character in decomposed
            if not unicodedata.combining(character)
        ).split()
    )
