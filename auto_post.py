import os
import sys
import time
import argparse
import markdown
from playwright.sync_api import sync_playwright

# 로그인 세션 파일: 스크립트와 같은 폴더의 naver_state.json 사용
# (config.NAVER_STATE_FILE 과 동일 경로)
STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "naver_state.json")

TITLE_X = 300
TITLE_Y = 280
BODY_X  = 300
BODY_Y  = 480


def main():
    parser = argparse.ArgumentParser(description="Naver Blog Auto Poster")
    parser.add_argument("--title",   type=str, default="테스트 제목")
    parser.add_argument("--content", type=str, default="테스트 본문입니다.")
    parser.add_argument("--category", type=str, help="네이버 블로그 카테고리 이름")
    args = parser.parse_args()

    if not os.path.exists(STATE_FILE):
        print("ERROR: naver_state.json not found.", file=sys.stderr)
        sys.exit(1)

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

        if "nidlogin" in page.url:
            print("ERROR: Session expired.", file=sys.stderr)
            browser.close()
            sys.exit(1)

        print("Clicking '글쓰기'...")
        try:
            with context.expect_page(timeout=15000) as new_tab:
                page.locator("a:has-text('글쓰기')").first.click()
            editor = new_tab.value
        except Exception as e:
            print(f"ERROR: Cannot open editor: {e}", file=sys.stderr)
            browser.close()
            sys.exit(1)

        editor.wait_for_load_state("domcontentloaded")
        print("Waiting for SmartEditor ONE to initialize...")
        time.sleep(12)

        editor.keyboard.press("Escape")
        time.sleep(1)

        main_frame = None
        for f in editor.frames:
            if "PostWriteForm" in f.url:
                main_frame = f
                break

        # 임시저장 복구 팝업(se-popup-alert-confirm)이 뜨면 JS로 취소 누르기
        if main_frame:
            try:
                popup_cancel = main_frame.locator(".se-popup-alert-confirm button:has-text('취소')").first
                if popup_cancel.count() > 0:
                    popup_cancel.evaluate("b => b.click()")
                    time.sleep(1)
                    print("  Auto-save popup closed via JS.")
            except:
                pass

            # 도움말 사이드바 강제 숨김 (JS)
            try:
                main_frame.evaluate("""
                    () => {
                        document.querySelectorAll('div, aside').forEach(el => {
                            if (el.innerText && el.innerText.includes('도움말') && el.innerText.includes('What\\'s New')) {
                                el.style.display = 'none';
                            }
                        });
                    }
                """)
                time.sleep(1)
            except:
                pass

        print("Entering title...")
        editor.mouse.click(TITLE_X, TITLE_Y)
        time.sleep(0.5)
        editor.keyboard.press("Meta+a")
        time.sleep(0.2)
        editor.keyboard.type(args.title, delay=0)
        time.sleep(0.5)

        print("Parsing and downloading images...")
        import re
        import requests
        import uuid
        
        image_matches = re.findall(r'!\[.*?\]\((https?://[^\)]+)\)', args.content)
        downloaded_images = []
        fixed_content = args.content
        
        # 마크다운 이미지는 유지 -> markdown 변환 시 인라인 <img> 로 본문 중간에 배치
        # (Pexels 저작권 프리 실사 사진. writer.insert_photos 가 삽입)
        
        # [AI 이미지 프롬프트: '...'] 와 같은 불필요한 텍스트 찌꺼기 제거
        fixed_content = re.sub(r'\[AI 이미지 프롬프트:.*?\]', '', fixed_content)
        
        # 표 깨짐 방지: 불필요한 '-- |' 문자열 제거 및 표 앞 빈 줄 강제 삽입
        fixed_content = re.sub(r'\n\s*--\s*\|\s*\n', '\n', fixed_content)
        fixed_content = re.sub(r'([^\n])\n(\s*\|)', r'\1\n\n\2', fixed_content)
        
        # 이미지 다운로드 비활성 (인라인 <img> 방식 사용. downloaded_images 가 비어 업로드도 자동 스킵)
        for url in []:
            try:
                print(f"Downloading: {url[:50]}...")
                resp = requests.get(url, timeout=10)
                if resp.status_code == 200:
                    ext = "jpg"
                    if "png" in url: ext = "png"
                    filename = os.path.abspath(f"temp_img_{uuid.uuid4().hex[:8]}.{ext}")
                    with open(filename, 'wb') as f:
                        f.write(resp.content)
                    downloaded_images.append(filename)
            except Exception as e:
                print(f"Failed to download image {url}: {e}")
                
        print("Entering content via Rich Text paste (Browser Copy method)...")
        # Markdown을 HTML로 변환
        html_content = markdown.markdown(fixed_content, extensions=['tables', 'fenced_code', 'nl2br'])
        
        # 임시 HTML 파일 생성 후 브라우저에서 열어서 전체 복사 (OS 클립보드 완벽 연동)
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
        
        try:
            os.remove(tmp_html_path)
        except: pass
        
        editor.mouse.click(BODY_X, BODY_Y)
        time.sleep(0.5)
        editor.keyboard.press("Meta+v")
        time.sleep(3)
        
        # 다운로드 받은 이미지를 네이티브 파일 첨부 버튼을 통해 업로드
        if downloaded_images:
            print("Uploading images natively...")
            try:
                # 사진 첨부 버튼 찾기
                photo_btn = main_frame.locator("button:has-text('사진'), button[data-name='image'], .se-image-toolbar-button").first
                if photo_btn.count() > 0:
                    with editor.expect_file_chooser(timeout=10000) as fc_info:
                        photo_btn.click()
                    file_chooser = fc_info.value
                    file_chooser.set_files(downloaded_images)
                    time.sleep(8) # 업로드 완료 대기
                    print("Images uploaded successfully.")
                else:
                    print("Warning: Photo button not found, skipping image upload.")
            except Exception as e:
                print(f"Error during image upload: {e}")
            
            # 임시 이미지 파일 삭제
            for img in downloaded_images:
                try: os.remove(img)
                except: pass

        print("Clicking 1st publish button via JS...")
        if not main_frame:
            print("ERROR: Cannot find mainFrame", file=sys.stderr)
            sys.exit(1)

        pub_btn = main_frame.locator("button[class*='publish_btn__']").first
        if pub_btn.count() > 0:
            pub_btn.evaluate("b => b.click()")
            print("  Top publish button clicked.")
        else:
            print("ERROR: Top publish button not found.", file=sys.stderr)
            browser.close()
            sys.exit(1)

        time.sleep(3)
        
        # 카테고리 선택 로직
        if args.category:
            print(f"Attempting to select category: {args.category}")
            try:
                # 콤보박스 클릭 시도 (네이버 스마트에디터 ONE의 카테고리 버튼 aria-label 사용)
                category_dropdown = main_frame.locator("button[aria-label='카테고리 목록 버튼']").first
                if category_dropdown.count() > 0:
                    category_dropdown.evaluate("b => b.click()")
                    time.sleep(1)
                    # 드롭다운에서 텍스트 일치 항목 클릭
                    cat_item = main_frame.locator(f"button:has-text('{args.category}'), span:has-text('{args.category}')").last
                    if cat_item.count() > 0:
                        cat_item.evaluate("b => b.click()")
                        print(f"  Category '{args.category}' selected successfully.")
                    else:
                        print(f"  Warning: Category '{args.category}' not found in dropdown.")
                else:
                    print("  Warning: Category dropdown button not found.")
            except Exception as e:
                print(f"  Error selecting category: {e}")

        print("Clicking 2nd final confirm button via JS...")
        confirm_btn = main_frame.locator("button[class*='confirm_btn__']").first
        if confirm_btn.count() > 0:
            confirm_btn.evaluate("b => b.click()")
            print("  Final confirm button clicked! 🎉")
        else:
            print("  Warning: confirm_btn__ not found, trying fallback...")
            for btn in main_frame.locator("button:has-text('발행')").all():
                try:
                    if "confirm_btn" in (btn.get_attribute("class") or ""):
                        btn.evaluate("b => b.click()")
                        print("  Final confirm button clicked (fallback)!")
                        break
                except: pass

        time.sleep(5)
        print(f"Final URL: {editor.url}")
        
        if "Write" not in editor.url:
            print("SUCCESS: Published successfully!")
        else:
            print("SUCCESS: Finished script (please verify manually if URL didn't change).")

        browser.close()
        sys.exit(0)


if __name__ == "__main__":
    main()
