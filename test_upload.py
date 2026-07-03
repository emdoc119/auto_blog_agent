import os
import sys
import time
import re
import requests
import uuid
import markdown
from playwright.sync_api import sync_playwright

STATE_FILE = os.path.expanduser("~/.gemini/antigravity/scratch/naver_state.json")
BODY_X = 300
BODY_Y = 480

broken_content = """
이것은 네이티브 업로드 테스트입니다.

| 연구 단계 | AI 활용법 | 기대 효과 |
|:----------|:----------|:----------|
-- |
| 문헌 탐색 및 정리 | 핵심 논문 요약, 키워드 추출 | 탐색 시간 획기적 단축, 최신 트렌드 파악 |

이미지 테스트:
![건강한 숲](https://image.pollinations.ai/prompt/forest)
"""

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            storage_state=STATE_FILE,
            viewport={"width": 1280, "height": 900},
            permissions=["clipboard-read", "clipboard-write"]
        )
        page = context.new_page()

        print("Navigating to Blog Home...")
        page.goto("https://section.blog.naver.com/BlogHome.naver", timeout=60000)
        time.sleep(2)

        print("Clicking '글쓰기'...")
        with context.expect_page(timeout=15000) as new_tab:
            page.locator("a:has-text('글쓰기')").first.click()
        editor = new_tab.value

        editor.wait_for_load_state("domcontentloaded")
        time.sleep(12)
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

        editor.mouse.click(TITLE_X:=300, TITLE_Y:=280)
        time.sleep(0.5)
        editor.keyboard.type("완벽 자가 진단 테스트 - 이미지/표 업로드", delay=0)
        time.sleep(0.5)

        image_matches = re.findall(r'!\[.*?\]\((https?://[^\)]+)\)', broken_content)
        downloaded_images = []
        fixed_content = broken_content
        fixed_content = re.sub(r'!\[.*?\]\((https?://[^\)]+)\)', '', fixed_content)
        fixed_content = re.sub(r'\n\s*--\s*\|\s*\n', '\n', fixed_content)
        fixed_content = re.sub(r'([^\n])\n(\s*\|)', r'\1\n\n\2', fixed_content)

        for url in image_matches:
            try:
                print(f"Downloading: {url[:50]}...")
                resp = requests.get(url, timeout=10)
                if resp.status_code == 200:
                    filename = os.path.abspath(f"temp_img_{uuid.uuid4().hex[:8]}.jpg")
                    with open(filename, 'wb') as f:
                        f.write(resp.content)
                    downloaded_images.append(filename)
            except Exception as e:
                print(f"Failed to download image {url}: {e}")

        html_content = markdown.markdown(fixed_content, extensions=['tables', 'fenced_code', 'nl2br'])
        tmp_html_path = os.path.abspath("temp_post.html")
        with open(tmp_html_path, "w", encoding="utf-8") as f:
            f.write(f"<html><body>{html_content}</body></html>")
            
        page_html = context.new_page()
        page_html.goto(f"file://{tmp_html_path}")
        time.sleep(0.5)
        page_html.keyboard.press("Meta+a")
        time.sleep(0.5)
        page_html.keyboard.press("Meta+c")
        time.sleep(1)
        page_html.close()

        editor.mouse.click(BODY_X, BODY_Y)
        time.sleep(0.5)
        editor.keyboard.press("Meta+v")
        time.sleep(3)

        if downloaded_images:
            print("Uploading images natively...")
            try:
                photo_btn = main_frame.locator("button:has-text('사진'), button[data-name='image'], .se-image-toolbar-button").first
                if photo_btn.count() > 0:
                    with editor.expect_file_chooser(timeout=10000) as fc_info:
                        photo_btn.click()
                    file_chooser = fc_info.value
                    file_chooser.set_files(downloaded_images)
                    time.sleep(8)
                    print("Images uploaded successfully.")
                else:
                    print("Warning: Photo button not found.")
            except Exception as e:
                print(f"Error during image upload: {e}")

        editor.screenshot(path="final_test_result.png")
        print("Screenshot saved to final_test_result.png")
        
        browser.close()

if __name__ == "__main__":
    main()
