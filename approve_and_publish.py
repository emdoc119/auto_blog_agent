import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sqlite3
from config import DB_PATH
from agents import publisher

# 1. 상태를 approved로 변경
conn = sqlite3.connect(DB_PATH)
conn.execute("UPDATE posts SET status = 'approved' WHERE id = 1")
conn.commit()
conn.close()

# 2. 발행
print("Publishing post 1...")
publisher.publish(1)
print("Done.")
