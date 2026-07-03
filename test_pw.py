import os, time
from playwright.sync_api import sync_playwright
def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(storage_state="naver_state.json")
        page = context.new_page()
        page.goto("https://section.blog.naver.com/BlogHome.naver")
        time.sleep(2)
        for link in page.locator("a:has-text('글쓰기')").all():
            print("Link:", link.get_attribute("href"))
        
        # also print user id from nid_inf if possible or just print all urls containing blog.naver.com
        browser.close()
if __name__ == "__main__":
    main()
