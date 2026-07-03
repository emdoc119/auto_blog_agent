import os
import time
from playwright.sync_api import sync_playwright

STATE_FILE = os.path.expanduser("~/.gemini/antigravity/scratch/naver_state.json")
BODY_X = 300
BODY_Y = 480

html_content = """
<html>
<body>
<h1>테스트 제목</h1>
<p>이것은 <b>굵은 글씨</b> 테스트입니다.</p>
<table border="1">
    <tr><th>구분</th><th>내용</th></tr>
    <tr><td>항목1</td><td>테스트1</td></tr>
    <tr><td>항목2</td><td>테스트2</td></tr>
</table>
<img src="https://image.pollinations.ai/prompt/apple" width="400" />
</body>
</html>
"""

def main():
    with open("test_content.html", "w", encoding="utf-8") as f:
        f.write(html_content)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True) # Run headlessly for testing
        context = browser.new_context(
            storage_state=STATE_FILE,
            viewport={"width": 1280, "height": 900},
            permissions=["clipboard-read", "clipboard-write"]
        )
        
        # 1. Open the local HTML file and copy its content
        page_html = context.new_page()
        page_html.goto(f"file://{os.path.abspath('test_content.html')}")
        page_html.wait_for_load_state("networkidle")
        
        # Select all and copy
        page_html.keyboard.press("Meta+A")
        time.sleep(0.5)
        page_html.keyboard.press("Meta+C")
        time.sleep(1.0)
        
        # 2. Go to Naver Blog Editor
        page_editor = context.new_page()
        page_editor.goto("https://section.blog.naver.com/BlogHome.naver", timeout=60000)
        time.sleep(2)
        
        with context.expect_page(timeout=15000) as new_tab:
            page_editor.locator("a:has-text('글쓰기')").first.click()
        editor = new_tab.value
        
        editor.wait_for_load_state("domcontentloaded")
        time.sleep(10)
        
        editor.keyboard.press("Escape")
        time.sleep(1)
        
        main_frame = None
        for f in editor.frames:
            if "PostWriteForm" in f.url:
                main_frame = f
                break
                
        if main_frame:
            try:
                popup_cancel = main_frame.locator(".se-popup-alert-confirm button:has-text('취소')").first
                if popup_cancel.count() > 0:
                    popup_cancel.evaluate("b => b.click()")
                    time.sleep(1)
            except: pass
            
        print("Clicking body and pasting...")
        editor.mouse.click(BODY_X, BODY_Y)
        time.sleep(0.5)
        editor.keyboard.press("Meta+V")
        time.sleep(5) # wait for paste and image upload processing
        
        # Take a screenshot to verify
        editor.screenshot(path="test_paste_result.png")
        print("Screenshot saved to test_paste_result.png")
        browser.close()

if __name__ == "__main__":
    main()
