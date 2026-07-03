import json
import urllib.request
import re

data = json.load(open('naver_state.json'))
cookie_header = "; ".join([f"{c['name']}={c['value']}" for c in data['cookies']])
req = urllib.request.Request("https://section.blog.naver.com/BlogHome.naver", headers={"Cookie": cookie_header, "User-Agent": "Mozilla/5.0"})
try:
    html = urllib.request.urlopen(req).read().decode('utf-8')
    matches = re.findall(r'https://blog\.naver\.com/([a-zA-Z0-9_-]+)', html)
    print("Found IDs:", list(set(matches)))
except Exception as e:
    print(e)
