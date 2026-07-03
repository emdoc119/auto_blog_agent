import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'blog_agent'))
from config import GEMINI_API_KEY
from google import genai

client = genai.Client(api_key=GEMINI_API_KEY)
for m in client.models.list():
    if "flash" in m.name.lower():
        print(m.name)
