"""
Publisher Agent
승인된 블로그 초안을 auto_post.py를 이용해 네이버 블로그에 자동 발행합니다.
"""
import subprocess
import sys
import os
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db import get_conn
from config import PUBLISHER_SCRIPT, PUBLISHER_VENV

def add_log(post_id, message, level="info"):
    conn = get_conn()
    conn.execute("INSERT INTO logs (post_id, agent, message, level) VALUES (?, 'Publisher', ?, ?)",
                 (post_id, message, level))
    conn.commit()
    conn.close()

def publish(post_id: int) -> bool:
    """
    post_id에 해당하는 승인된 글을 네이버 블로그에 발행합니다.
    """
    conn = get_conn()
    post = conn.execute("""
        SELECT p.*, pr.account_id, pr.category_name 
        FROM posts p
        JOIN projects pr ON p.project_id = pr.id
        WHERE p.id = ?
    """, (post_id,)).fetchone()
    
    if not post:
        conn.close()
        return False
        
    account = conn.execute("SELECT * FROM accounts WHERE id = ?", (post["account_id"],)).fetchone()
    conn.close()
    
    if post["status"] not in ["approved", "publishing"]:
        add_log(post_id, f"발행 불가: 현재 상태 = {post['status']}", "warning")
        return False
    
    platform = account["platform"]
    add_log(post_id, f"발행 시작: '{post['title']}' (플랫폼: {platform}, 카테고리: {post['category_name']})")
    
    if platform == "naver":
        return publish_naver(post_id, post)
    elif platform == "tistory":
        add_log(post_id, "티스토리 발행 (API 연동 대기 중 - Mock 처리 완료)")
        _mark_published(post_id)
        return True
    elif platform == "wordpress":
        add_log(post_id, "워드프레스 발행 (REST API 연동 대기 중 - Mock 처리 완료)")
        _mark_published(post_id)
        return True
    else:
        add_log(post_id, f"알 수 없는 플랫폼: {platform}", "error")
        return False

def _mark_published(post_id):
    conn = get_conn()
    conn.execute(
        "UPDATE posts SET status = 'published', published_at = ? WHERE id = ?",
        (datetime.now().isoformat(), post_id)
    )
    conn.commit()
    conn.close()

def publish_naver(post_id: int, post: dict) -> bool:
    """네이버 블로그 발행 (Playwright 스크립트 실행)"""
    
    try:
        cmd = [
            PUBLISHER_VENV,
            PUBLISHER_SCRIPT,
            "--title", post["title"],
            "--content", post["content"]
        ]
        if post.get("category_name"):
            cmd.extend(["--category", post["category_name"]])
            
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300   # 5분 타임아웃
        )
        
        if result.returncode == 0:
            _mark_published(post_id)
            add_log(post_id, "발행 성공!")
            return True
        else:
            add_log(post_id, f"발행 실패: {result.stderr[:300]}", "error")
            return False
            
    except subprocess.TimeoutExpired:
        add_log(post_id, "발행 타임아웃 (5분 초과)", "error")
        _mark_error(post_id)
        return False
    except Exception as e:
        add_log(post_id, f"발행 예외 발생: {e}", "error")
        _mark_error(post_id)
        return False

def _mark_error(post_id):
    conn = get_conn()
    conn.execute("UPDATE posts SET status = 'error' WHERE id = ?", (post_id,))
    conn.commit()
    conn.close()
