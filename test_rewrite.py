import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sqlite3
from config import DB_PATH
from agents.orchestrator import run_pipeline

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
post = conn.execute("SELECT * FROM posts WHERE id = 1").fetchone()
conn.close()

if post:
    print(f"Rewriting Post 1: {post['title']}")
    # 1. 상태 초기화
    conn = sqlite3.connect(DB_PATH)
    conn.execute("UPDATE posts SET status = 'researching' WHERE id = 1")
    conn.commit()
    conn.close()
    
    # 2. 파이프라인 수동 실행
    keywords = ["갱년기증상", "관절건강", "건강식품섭취"]
    run_pipeline(1, keywords)
    
    # 3. 작성된 내용 확인 및 승인 대기 상태로 변경 (자동 발행 방지용)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("UPDATE posts SET status = 'pending_approval' WHERE id = 1")
    conn.commit()
    new_post = conn.execute("SELECT title, content FROM posts WHERE id = 1").fetchone()
    conn.close()
    
    print("\n[새로운 제목]")
    print(new_post["title"])
    print("\n[새로운 본문 일부]")
    print(new_post["content"])
