"""Extract manual sections while preserving their provenance and rule text."""

import argparse
import hashlib
import json
import re
from pathlib import Path

from emporio.data import DEFAULT_DATA_DIR


def extract_sections(pages: list[str]) -> list[dict]:
    """Recognize left-aligned headings in this specific manual layout.

    Keep indented numbered lists inside their section. Remove repeated headers
    and footers, keeping one text line per extracted table row.
    """
    sections = []
    current = None
    for page_number, page in enumerate(pages, start=1):
        for line in page.splitlines():
            stripped = line.strip()
            if not stripped or stripped == "Empório da Música Manual de Políticas e Procedimentos":
                continue
            if re.fullmatch(r"Página\s+\d+", stripped):
                continue
            heading = re.fullmatch(r"(\d+)\.\s+(.+)", line)
            if heading:
                section_id, title = heading.groups()
                if section_id != str(len(sections) + 1):
                    raise ValueError("Unexpected section sequence; review the PDF layout.")
                current = {
                    "section_id": section_id,
                    "title": title.strip(),
                    "pages": [],
                    "text": "",
                    "anchors": [title.strip()],
                }
                sections.append(current)
            if current is not None:
                if page_number not in current["pages"]:
                    current["pages"].append(page_number)
                current["text"] += re.sub(r"[ \t]+", " ", stripped) + "\n"
                columns = re.split(r"\s{2,}", stripped)
                anchor = None
                if re.match(r"\d+\.\d+\s", stripped):
                    anchor = stripped
                elif len(columns) > 1:
                    anchor = columns[0]
                if anchor and anchor not in current["anchors"]:
                    current["anchors"].append(anchor)
    if not sections or any(len(section["text"].splitlines()) < 2 for section in sections):
        raise ValueError("Could not extract complete PDF sections.")
    for section in sections:
        section["text"] = section["text"].rstrip()
    return sections


def build_index(source: Path) -> dict:
    # This dependency is optional for queries and tests.
    import pypdf

    try:
        reader = pypdf.PdfReader(source)
        pages = [page.extract_text(extraction_mode="layout") for page in reader.pages]
    except pypdf.errors.PyPdfError:
        raise ValueError("Could not extract PDF text.") from None
    return {
        "schema_version": 1,
        "source": source.name,
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "extractor": f"pypdf {pypdf.__version__} (layout)",
        "sections": extract_sections(pages),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the original-language policy index from the PDF.")
    parser.add_argument("--source", type=Path, default=DEFAULT_DATA_DIR / "politicas_da_loja.pdf")
    parser.add_argument("--output", type=Path, default=DEFAULT_DATA_DIR / "politicas_da_loja.json")
    parser.add_argument("--check", action="store_true", help="Check the index without writing files.")
    args = parser.parse_args()
    try:
        index = build_index(args.source)
        if args.check:
            saved = json.loads(args.output.read_text(encoding="utf-8"))
            if saved != index:
                raise ValueError("The index differs from the current extraction; rebuild and review the changes.")
            print("The index matches the PDF extraction.")
        else:
            args.output.write_text(
                json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            print(f"Index generated: {len(index['sections'])} sections in {args.output}")
    except ModuleNotFoundError:
        parser.exit(1, "Install the extraction dependency: python3 -m pip install -r requirements-ingest.txt\n")
    except (OSError, ValueError) as error:
        parser.exit(1, f"Policy preparation error: {error}\n")


if __name__ == "__main__":
    main()
