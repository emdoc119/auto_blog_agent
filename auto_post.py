import os
import sys
import time
import argparse
import tempfile
import re
import markdown
from html import escape
from playwright.sync_api import sync_playwright

# 로그인 세션 파일: 스크립트와 같은 폴더의 naver_state.json 사용
# (config.NAVER_STATE_FILE 과 동일 경로)
STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "naver_state.json")

TITLE_X = 300
TITLE_Y = 280
BODY_X  = 300
BODY_Y  = 480


def _rss_contains_title(title: str) -> bool:
    """Verify that Naver actually exposed the just-published title in RSS."""
    import requests
    import xml.etree.ElementTree as ET

    expected = " ".join(title.split())
    try:
        response = requests.get(
            "https://rss.blog.naver.com/emdoc119.xml",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=15,
        )
        response.raise_for_status()
        root = ET.fromstring(response.content)
        return any(
            " ".join((item.findtext("title") or "").split()) == expected
            for item in root.findall(".//item")[:20]
        )
    except Exception as exc:
        print(f"  RSS verification pending: {exc}")
        return False


def markdown_tables_to_html(text: str) -> str:
    """Convert well-formed Markdown tables to explicit, styled HTML tables.

    SmartEditor may paste a Markdown table as literal text even when the
    clipboard contains rich HTML. Explicit table markup is more consistently
    preserved by the editor and also gives mobile readers readable cell
    padding/borders. Malformed table-like text is left untouched.
    """
    lines = text.splitlines()
    output = []
    index = 0
    while index < len(lines):
        if index + 1 >= len(lines):
            output.append(lines[index])
            break
        header = lines[index].strip()
        separator_index = index + 1
        while separator_index < len(lines) and not lines[separator_index].strip():
            separator_index += 1
        if separator_index >= len(lines):
            output.append(lines[index])
            index += 1
            continue
        separator = lines[separator_index].strip()
        if not (header.startswith("|") and header.endswith("|")
                and separator.startswith("|") and separator.endswith("|")):
            output.append(lines[index])
            index += 1
            continue

        header_cells = [cell.strip() for cell in header.strip("|").split("|")]
        separator_cells = [cell.strip() for cell in separator.strip("|").split("|")]
        if (len(header_cells) < 2 or len(header_cells) != len(separator_cells)
                or not all(cell and set(cell) <= set("-:") and "-" in cell
                           for cell in separator_cells)):
            output.append(lines[index])
            index += 1
            continue

        rows = []
        row_index = separator_index + 1
        while row_index < len(lines):
            while row_index < len(lines) and not lines[row_index].strip():
                row_index += 1
            if row_index >= len(lines):
                break
            row = lines[row_index].strip()
            if not (row.startswith("|") and row.endswith("|")):
                break
            cells = [cell.strip() for cell in row.strip("|").split("|")]
            if len(cells) != len(header_cells):
                break
            rows.append(cells)
            row_index += 1

        def cell_markup(tag, value):
            return (
                f'<{tag} style="border:1px solid #d9dee8;padding:8px;'
                f'text-align:left;vertical-align:top;">{escape(value)}</{tag}>'
            )

        table = [
            '<table style="border-collapse:collapse;width:100%;margin:12px 0;table-layout:fixed;">',
            "<thead><tr>",
            "".join(cell_markup("th", value) for value in header_cells),
            "</tr></thead>",
            "<tbody>",
        ]
        for cells in rows:
            table.extend(["<tr>", "".join(cell_markup("td", value) for value in cells), "</tr>"])
        table.extend(["</tbody>", "</table>"])
        output.append("\n".join(table))
        index = row_index
    return "\n".join(output)


def markdown_tables_to_text(text: str) -> str:
    """Convert Markdown tables to plain-text cards safe for SmartEditor.

    SmartEditor can downgrade clipboard HTML to plain text. In that path a
    Markdown table becomes unreadable pipes and separator dashes, so the
    default publishing representation is deliberately plain text and mobile
    friendly. Malformed table-like text is preserved for diagnosis.
    """
    lines = text.splitlines()
    output = []
    index = 0
    while index < len(lines):
        if index + 1 >= len(lines):
            output.append(lines[index])
            break
        header = lines[index].strip()
        separator_index = index + 1
        while separator_index < len(lines) and not lines[separator_index].strip():
            separator_index += 1
        if separator_index >= len(lines):
            output.append(lines[index])
            index += 1
            continue
        separator = lines[separator_index].strip()
        if not (header.startswith("|") and header.endswith("|")
                and separator.startswith("|") and separator.endswith("|")):
            output.append(lines[index])
            index += 1
            continue

        headers = [cell.strip() for cell in header.strip("|").split("|")]
        separators = [cell.strip() for cell in separator.strip("|").split("|")]
        if (len(headers) < 2 or len(headers) != len(separators)
                or not all(cell and set(cell) <= set("-:") and "-" in cell
                           for cell in separators)):
            output.append(lines[index])
            index += 1
            continue

        rows = []
        row_index = separator_index + 1
        while row_index < len(lines):
            while row_index < len(lines) and not lines[row_index].strip():
                row_index += 1
            if row_index >= len(lines):
                break
            row = lines[row_index].strip()
            if not (row.startswith("|") and row.endswith("|")):
                break
            cells = [cell.strip() for cell in row.strip("|").split("|")]
            if len(cells) != len(headers):
                break
            rows.append(cells)
            row_index += 1

        output.append("")
        for cells in rows:
            label = cells[0]
            output.append(f"📌 {label}")
            for header_name, value in zip(headers[1:], cells[1:]):
                clean_header = re.sub(r"[*_`]+", "", header_name).strip()
                clean_value = re.sub(r"[*_`]+", "", value).strip()
                output.append(f"- {clean_header}: {clean_value}")
            output.append("")
        index = row_index
    return "\n".join(output)


def main():
    parser = argparse.ArgumentParser(description="Naver Blog Auto Poster")
    parser.add_argument("--title",   type=str, default="테스트 제목")
    parser.add_argument("--content", type=str, default="테스트 본문입니다.")
    parser.add_argument("--category", type=str, help="네이버 블로그 카테고리 이름")
    parser.add_argument("--tags", type=str, default="", help="쉼표 구분 SEO 태그")
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
            write_link = page.locator("a:has-text('글쓰기')").first
            if write_link.count() == 0:
                raise RuntimeError("글쓰기 링크를 찾지 못했습니다. 로그인 세션을 갱신하세요.")
            with context.expect_page(timeout=15000) as new_tab:
                # 네이버 홈의 링크가 화면 밖/투명 상태여도 DOM 클릭은 정상 동작합니다.
                write_link.evaluate("el => el.click()")
            editor = new_tab.value
        except Exception as e:
            print(f"ERROR: Cannot open editor: {e}", file=sys.stderr)
            browser.close()
            sys.exit(1)

        editor.wait_for_load_state("domcontentloaded")
        if "nidlogin" in editor.url:
            print("ERROR: Session expired while opening editor.", file=sys.stderr)
            browser.close()
            sys.exit(1)
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
        # SmartEditor가 클립보드 HTML을 평문으로 다운그레이드할 수 있으므로
        # 표는 HTML이 아니라 모바일에서도 읽히는 텍스트 카드로 발행합니다.
        fixed_content = markdown_tables_to_text(fixed_content)
        html_content = markdown.markdown(fixed_content, extensions=['fenced_code', 'nl2br'])
        
        # 임시 HTML 파일 생성 후 브라우저에서 열어서 전체 복사 (OS 클립보드 완벽 연동)
        tmp_file = tempfile.NamedTemporaryFile(
            mode="w", suffix=".html", prefix="blog_post_", encoding="utf-8", delete=False
        )
        tmp_html_path = tmp_file.name
        with tmp_file as f:
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
                category_dropdown = main_frame.locator("button[aria-label='카테고리 목록 버튼']").first
                if category_dropdown.count() > 0:
                    # 일반 클릭으로 드롭다운 열기 (JS 클릭은 React selectbox 를 열지 못함)
                    category_dropdown.click(timeout=5000)
                    time.sleep(1.5)
                    # 드롭다운 항목(LI item__)에서 카테고리 선택
                    cat_item = main_frame.locator(f"li[class*='item__']:has-text('{args.category}')").first
                    if cat_item.count() > 0:
                        cat_item.click(timeout=5000)
                        print(f"  Category '{args.category}' selected successfully.")
                        time.sleep(1)
                    else:
                        raise RuntimeError(f"카테고리 '{args.category}' 항목을 찾지 못했습니다.")
                else:
                    raise RuntimeError("카테고리 목록 버튼을 찾지 못했습니다.")
            except Exception as e:
                print(f"ERROR: Category selection failed: {e}", file=sys.stderr)
                browser.close()
                sys.exit(1)

        # 태그 입력 로직 (best-effort)
        if args.tags:
            print(f"Attempting to add tags: {args.tags}")
            try:
                tag_input = main_frame.locator(
                    "input[placeholder*='태그'], input[class*='tag'], .se_publish_tag input"
                ).first
                if tag_input.count() > 0:
                    tag_input.click()
                    for tag in [t.strip() for t in args.tags.split(",") if t.strip()]:
                        tag_input.type(tag, delay=0)
                        tag_input.press("Enter")
                        time.sleep(0.3)
                    print("  Tags added.")
                else:
                    print("  Warning: Tag input not found.")
            except Exception as e:
                print(f"  Error adding tags: {e}")

        print("Clicking 2nd final confirm button via JS...")
        confirm_clicked = False
        confirm_btn = main_frame.locator("button[class*='confirm_btn__']").first
        if confirm_btn.count() > 0:
            confirm_btn.evaluate("b => b.click()")
            confirm_clicked = True
            print("  Final confirm button clicked! 🎉")
        else:
            print("  Warning: confirm_btn__ not found, trying fallback...")
            for btn in main_frame.locator("button:has-text('발행')").all():
                try:
                    if "confirm_btn" in (btn.get_attribute("class") or ""):
                        btn.evaluate("b => b.click()")
                        confirm_clicked = True
                        print("  Final confirm button clicked (fallback)!")
                        break
                except: pass

        if not confirm_clicked:
            print("ERROR: Final publish confirmation button was not clicked.", file=sys.stderr)
            browser.close()
            sys.exit(1)

        verified = False
        # SmartEditor가 URL을 유지하는 경우가 있어 URL 전환과 RSS를 함께 확인합니다.
        for _ in range(10):
            time.sleep(5)
            current_url = editor.url
            if "PostWriteForm" not in current_url and "Write" not in current_url:
                verified = True
                break
            if _rss_contains_title(args.title):
                verified = True
                break

        print(f"Final URL: {editor.url}")
        if not verified:
            print("ERROR: Publish could not be verified by URL or RSS.", file=sys.stderr)
            browser.close()
            sys.exit(1)

        print("SUCCESS: Published and verified successfully!")

        browser.close()
        sys.exit(0)


if __name__ == "__main__":
    main()
