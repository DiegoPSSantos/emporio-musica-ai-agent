import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from emporio.policies import DEFAULT_POLICY_INDEX, PolicyIndexError, load_policies
from scripts.build_policy_index import extract_sections


class PolicySearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store = load_policies()

    def test_common_questions_retrieve_expected_section_first(self):
        cases = {
            "Que horas vocês abrem aos sábados?": "2",
            "Me arrependi da compra, posso devolver?": "4",
            "Vocês aceitam PIX?": "3",
            "Como parcelar em 12 vezes?": "3",
            "Qual o endereço da loja?": "1",
            "Como são as entregas?": "5",
            "Quais promoções e descontos existem?": "6",
            "Como funciona a privacidade e proteção de dados?": "9",
        }
        for query, expected in cases.items():
            with self.subTest(query=query):
                self.assertEqual(self.store.search(query)[0].section.section_id, expected)

    def test_returns_whole_return_policy_including_exclusions(self):
        section = self.store.search("devolver")[0].section
        self.assertEqual(section.pages, (4,))
        self.assertEqual(section.source, "politicas_da_loja.pdf")
        self.assertIn("4.1 Direito de Arrependimento", section.text)
        self.assertIn("4.4 Itens Não Elegíveis", section.text)
        self.assertIn('"venda final"', section.text)

    def test_sections_spanning_pages_keep_all_references_and_text(self):
        shipping = self.store.get_section("5")
        self.assertEqual(shipping.pages, (4, 5))
        self.assertIn("5.1 Entregas", shipping.text)
        self.assertIn("5.3 Código de Rastreamento", shipping.text)
        privacy = self.store.get_section("9")
        self.assertEqual(privacy.pages, (7, 8))
        self.assertIn("exclusivamente para:", privacy.text)
        self.assertIn("consentimento explícito", privacy.text)

    def test_warranty_question_keeps_both_relevant_sections(self):
        matches = self.store.search("defeito garantia")
        self.assertTrue({"4", "8"}.issubset({match.section.section_id for match in matches}))

    def test_empty_generic_and_unrelated_queries_have_no_fallback(self):
        for query in ("", "!!!", "por favor", "Qual é a capital da França?"):
            with self.subTest(query=query):
                self.assertEqual(self.store.search(query), [])

    def test_unknown_section_returns_none(self):
        self.assertIsNone(self.store.get_section("999"))

    def test_limit_is_enforced_and_invalid_limits_are_rejected(self):
        self.assertEqual(len(self.store.search("PIX", limit=1)), 1)
        for limit in (0, -1, 11, 1.5, True):
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                self.store.search("PIX", limit=limit)

    def test_accents_and_case_do_not_change_ranking(self):
        normal = self.store.search("horário sábado")
        plain = self.store.search("HORARIO SABADO")
        self.assertEqual(normal, plain)


class PolicyIndexTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.index_path = self.directory / DEFAULT_POLICY_INDEX.name
        shutil.copyfile(DEFAULT_POLICY_INDEX, self.index_path)
        self.source = self.directory / "politicas_da_loja.pdf"
        shutil.copyfile(DEFAULT_POLICY_INDEX.parent / self.source.name, self.source)

    def rewrite_index(self, change):
        index = json.loads(self.index_path.read_text(encoding="utf-8"))
        change(index)
        self.index_path.write_text(json.dumps(index), encoding="utf-8")

    def test_supplied_index_has_ten_sequential_sections(self):
        store = load_policies(self.index_path)
        self.assertEqual([section.section_id for section in store.sections], [str(i) for i in range(1, 11)])

    def test_changed_pdf_blocks_use_of_old_index(self):
        self.source.write_bytes(self.source.read_bytes() + b"\n")
        with self.assertRaisesRegex(PolicyIndexError, "PDF mudou"):
            load_policies(self.index_path)

    def test_missing_pdf_is_reported(self):
        self.source.unlink()
        with self.assertRaises(PolicyIndexError):
            load_policies(self.index_path)

    def test_invalid_json_and_root_are_reported(self):
        for contents in ("{invalid", "[]", '{"schema_version": 99}'):
            with self.subTest(contents=contents):
                self.index_path.write_text(contents, encoding="utf-8")
                with self.assertRaises(PolicyIndexError):
                    load_policies(self.index_path)

    def test_invalid_metadata_and_sections_are_rejected(self):
        original = self.index_path.read_bytes()
        changes = [
            lambda index: index.update(source="../politicas_da_loja.pdf"),
            lambda index: index.update(sections=[]),
            lambda index: index["sections"][0].update(section_id="2"),
            lambda index: index["sections"][0].update(text=""),
            lambda index: index["sections"][0].update(pages=[True]),
            lambda index: index["sections"][0].update(pages=[3, 2]),
            lambda index: index["sections"][0].update(anchors=[None]),
        ]
        for change in changes:
            with self.subTest(change=change):
                self.index_path.write_bytes(original)
                self.rewrite_index(change)
                with self.assertRaises(PolicyIndexError):
                    load_policies(self.index_path)


class ExtractionTests(unittest.TestCase):
    def test_indented_numbered_lists_do_not_create_sections(self):
        pages = ["Capa", "1. Atendimento\nRegras:\n    1. Saudação\n    2. Consulta\nPágina 2"]
        sections = extract_sections(pages)
        self.assertEqual(len(sections), 1)
        self.assertIn("2. Consulta", sections[0]["text"])
        self.assertNotIn("Página 2", sections[0]["text"])
        self.assertEqual(sections[0]["pages"], [2])

    def test_page_continuations_and_table_labels_are_preserved(self):
        pages = [
            "1. Dados\nEndereço     Rua de Exemplo\n",
            "Empório da Música Manual de Políticas e Procedimentos\nContinuação.\n2. Frete\nEntrega local.\n",
        ]
        sections = extract_sections(pages)
        self.assertEqual(sections[0]["pages"], [1, 2])
        self.assertIn("Continuação.", sections[0]["text"])
        self.assertIn("Endereço", sections[0]["anchors"])
        self.assertNotIn("Manual de Políticas", sections[0]["text"])

    def test_empty_incomplete_or_out_of_order_extraction_is_rejected(self):
        for pages in (["PDF sem texto de seções"], ["1. Somente título"], ["2. Frete\nTexto."]):
            with self.subTest(pages=pages), self.assertRaises(ValueError):
                extract_sections(pages)


class PolicyCliTests(unittest.TestCase):
    def run_cli(self, *arguments):
        return subprocess.run(
            [sys.executable, "-m", "emporio.policies", *arguments],
            cwd=DEFAULT_POLICY_INDEX.parent.parent,
            capture_output=True, text=True,
        )

    def test_search_prints_source_and_page_without_generating_an_answer(self):
        result = self.run_cli("search", "posso devolver?", "--limit", "1")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("seção 4 | páginas 4", result.stdout)
        self.assertIn("4.4 Itens Não Elegíveis", result.stdout)

    def test_missing_section_and_unrelated_question_have_no_result(self):
        for arguments in (("show", "999"), ("search", "capital da França")):
            with self.subTest(arguments=arguments):
                result = self.run_cli(*arguments)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("Nenhuma seção encontrada", result.stdout)

    def test_invalid_limit_returns_an_error_without_traceback(self):
        result = self.run_cli("search", "PIX", "--limit", "0")
        self.assertEqual(result.returncode, 1)
        self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
