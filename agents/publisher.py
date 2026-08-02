"""
Publisher Agent
승인된 블로그 초안을 auto_post.py를 이용해 네이버 블로그에 자동 발행합니다.
"""
import subprocess
import sys
import os
from datetime import datetime, timedelta
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

    if not account:
        add_log(post_id, "발행 계정이 없어 재시도할 수 없습니다.", "error")
        _defer_publish(post_id, "발행 계정 없음")
        return False
    
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
        _defer_publish(post_id, f"알 수 없는 플랫폼: {platform}")
        return False

def _mark_published(post_id):
    conn = get_conn()
    conn.execute(
        """UPDATE posts
           SET status = 'published', published_at = ?, retry_count = 0,
               retry_after = NULL, last_error = NULL
           WHERE id = ?""",
        (datetime.now().isoformat(), post_id)
    )
    conn.commit()
    conn.close()

def publish_naver(post_id: int, post: dict) -> bool:
    """네이버 블로그 발행 (Playwright 스크립트 실행)"""

    try:
        # 직전 시도에서 실제 발행은 됐지만 확인만 실패한 경우 중복 게시를 막습니다.
        if (post["retry_count"] or 0) > 0 and _rss_has_title(post["title"]):
            _mark_published(post_id)
            add_log(post_id, "RSS에서 동일 제목을 확인해 이전 발행 성공으로 복구했습니다.")
            return True

        cmd = [
            PUBLISHER_VENV,
            PUBLISHER_SCRIPT,
            "--title", post["title"],
            "--content", post["content"]
        ]
        if post["category_name"]:
            cmd.extend(["--category", post["category_name"]])
        if post["seo_tags"]:
            cmd.extend(["--tags", post["seo_tags"]])

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
            detail = (result.stderr or result.stdout or "알 수 없는 발행 오류")[-1000:]
            add_log(post_id, f"발행 실패(자동 재시도 예정): {detail}", "warning")
            _defer_publish(post_id, detail)
            return False
            
    except subprocess.TimeoutExpired:
        add_log(post_id, "발행 타임아웃 (5분 초과, 자동 재시도 예정)", "warning")
        _defer_publish(post_id, "발행 타임아웃")
        return False
    except Exception as e:
        add_log(post_id, f"발행 예외 발생(자동 재시도 예정): {e}", "warning")
        _defer_publish(post_id, e)
        return False


def _rss_has_title(title: str) -> bool:
    import requests
    import xml.etree.ElementTree as ET

    expected = " ".join((title or "").split())
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
    except Exception:
        return False


def _defer_publish(post_id, error):
    conn = get_conn()
    account_paused = False
    row = conn.execute(
        "SELECT COALESCE(retry_count, 0) AS retry_count FROM posts WHERE id = ?",
        (post_id,),
    ).fetchone()
    attempt = (row["retry_count"] if row else 0) + 1
    delay = min(360, 30 * (2 ** min(attempt - 1, 4)))
    retry_at = (datetime.now() + timedelta(minutes=delay)).strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        """UPDATE posts
           SET status = 'scheduled', retry_count = ?, retry_after = ?, last_error = ?
           WHERE id = ?""",
        (attempt, retry_at, str(error)[:1000], post_id),
    )
    error_text = str(error).lower()
    if "session expired" in error_text or "로그인 세션" in error_text or "nidlogin" in error_text:
        account_row = conn.execute("""
            SELECT pr.account_id
            FROM posts p JOIN projects pr ON p.project_id = pr.id
            WHERE p.id = ?
        """, (post_id,)).fetchone()
        if account_row:
            conn.execute(
                "UPDATE accounts SET status = 'reauth_required' WHERE id = ?",
                (account_row["account_id"],),
            )
            account_paused = True
    conn.commit()
    conn.close()
    if account_paused:
        add_log(post_id, "네이버 세션 만료로 계정 발행을 일시 정지했습니다.", "warning")
