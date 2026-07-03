import json
import time
from playwright.sync_api import sync_playwright

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(storage_state="/Users/choo/.gemini/antigravity/scratch/naver_state.json")
        page = context.new_page()
        
        print("Navigating to Naver Blog...")
        page.goto("https://blog.naver.com/emdoc119?Redirect=Write")
        time.sleep(5)
        
        # Check if iframe exists
        main_frame = None
        for frame in page.frames:
            if frame.name == "mainFrame" or "PostWrite" in frame.url:
                main_frame = frame
                break
                
        if not main_frame:
            main_frame = page.main_frame
            
        print("Clicking first publish button...")
        pub_btn = main_frame.locator("button[class*='publish_btn__']").first
        if pub_btn.count() > 0:
            pub_btn.evaluate("b => b.click()")
            time.sleep(3)
            
            # Get the HTML of the publish panel
            # The panel usually appears in the main_frame or page.
            html = main_frame.content()
            with open("publish_panel_dom.html", "w", encoding="utf-8") as f:
                f.write(html)
            print("DOM saved to publish_panel_dom.html")
        else:
            print("Publish button not found.")
            
        browser.close()

if __name__ == "__main__":
    main()
