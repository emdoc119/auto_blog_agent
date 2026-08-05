import unittest
from unittest.mock import patch
from agents import stats_scraper

class StatsScraperTests(unittest.TestCase):
    def test_scrape_naver_visitors_parses_mobile_page(self):
        html_text = "응급의학과 의사와 함께 건강 100세\n오늘 128  전체 12,345"
        class FakeLoc:
            def inner_text(self, *a, **kw):
                return html_text
        class FakePage:
            def goto(self, *a, **kw):
                pass
            def locator(self, *a, **kw):
                return FakeLoc()
        class FakeBrowser:
            def new_page(self):
                return FakePage()
            def close(self):
                pass
        class FakeChromium:
            def launch(self, **kw):
                return FakeBrowser()
        class FakePlaywright:
            chromium = FakeChromium()

        with patch("playwright.sync_api.sync_playwright") as mock_pw:
            mock_pw.return_value.__enter__.return_value = FakePlaywright()
            visitors = stats_scraper.scrape_naver_visitors("https://blog.naver.com/emdoc119")
            self.assertEqual(visitors, 128)

if __name__ == "__main__":
    unittest.main()
