import unittest

from auto_post import markdown_tables_to_html, markdown_tables_to_text


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

    def test_markdown_table_becomes_mobile_safe_text_cards(self):
        source = """| 구분 | 정상적인 상태 | 당뇨초기증상 의심 신호 |
|---|---|---|
| 소변 횟수 | 하루 4~8회 | 밤중 2회 이상 |
| 갈증 | 수분 섭취 후 해소 | 지속적으로 마심 |"""
        result = markdown_tables_to_text(source)
        self.assertIn("📌 소변 횟수", result)
        self.assertIn("- 정상적인 상태: 하루 4~8회", result)
        self.assertIn("- 당뇨초기증상 의심 신호: 밤중 2회 이상", result)
        self.assertNotIn("|---|---|", result)
        self.assertNotIn("| 소변 횟수 |", result)


if __name__ == "__main__":
    unittest.main()
