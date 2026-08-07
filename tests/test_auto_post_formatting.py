import unittest

from auto_post import markdown_tables_to_html


class AutoPostFormattingTests(unittest.TestCase):
    def test_markdown_table_becomes_explicit_html_table(self):
        source = """앞 문단

| 구분 | 정상 | 주의 |
|---|---|---|
| 갈증 | 해소 | 지속 |
| 피로 | 회복 | 극심 |

뒤 문단"""
        result = markdown_tables_to_html(source)
        self.assertIn("<table", result)
        self.assertIn("<thead><tr>", result)
        self.assertIn("<th", result)
        self.assertIn("<td", result)
        self.assertIn("갈증", result)
        self.assertNotIn("| 구분 |", result)

    def test_malformed_table_is_left_as_text_for_fallback_handling(self):
        source = "| 구분 | 정상 |\n|---|\n| 갈증 | 해소 |"
        self.assertEqual(markdown_tables_to_html(source), source)


if __name__ == "__main__":
    unittest.main()
