import os
import time
from playwright.sync_api import sync_playwright

STATE_FILE = os.path.expanduser("~/.gemini/antigravity/scratch/naver_state.json")

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            storage_state=STATE_FILE,
            viewport={"width": 1280, "height": 900},
            permissions=["clipboard-read", "clipboard-write"]
        )
        
        page_html = context.new_page()
        page_html.goto(f"file://{os.path.abspath('test_content.html')}")
        page_html.keyboard.press("Meta+A")
        time.sleep(0.5)
        page_html.keyboard.press("Meta+C")
        time.sleep(0.5)
        
        page_editor = context.new_page()
        page_editor.goto("https://section.blog.naver.com/BlogHome.naver", timeout=60000)
        time.sleep(2)
        
        with context.expect_page(timeout=15000) as new_tab:
            page_editor.locator("a:has-text('글쓰기')").first.click()
        editor = new_tab.value
        
        editor.wait_for_load_state("domcontentloaded")
        time.sleep(5)
        editor.keyboard.press("Escape")
        time.sleep(1)
        
        main_frame = None
        for f in editor.frames:
            if "PostWriteForm" in f.url:
                main_frame = f
                break
                
        if main_frame:
            try:
                main_frame.locator(".se-popup-alert-confirm button:has-text('취소')").first.click()
            except: pass
            
        editor.mouse.click(300, 480)
        time.sleep(0.5)
        editor.keyboard.press("Meta+V")
        time.sleep(3)
        
        content = main_frame.content()
        print("TABLE COUNT:", content.count("<table"))
        print("IMG COUNT:", content.count("<img"))
        
        browser.close()

if __name__ == "__main__":
    main()
