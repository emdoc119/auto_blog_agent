import sqlite3
import os
from config import DB_PATH

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def migrate_schema(conn):
    """기존 테이블에 신규 컬럼/테이블을 추가 (멱등, 재실행 안전)."""
    cur = conn.cursor()
    existing = {r[1] for r in cur.execute("PRAGMA table_info(posts)").fetchall()}
    additions = [
        ("quality_score", "REAL"),
        ("quality_detail", "TEXT"),
        ("views", "INTEGER DEFAULT 0"),
        ("seo_tags", "TEXT"),
        ("title_candidates", "TEXT"),
    ]
    for col, typ in additions:
        if col not in existing:
            cur.execute(f"ALTER TABLE posts ADD COLUMN {col} {typ}")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS quality_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER,
            score REAL,
            detail TEXT,
            attempt INTEGER DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)


def init_db():
    conn = get_conn()
    cur = conn.cursor()
    
    # 플랫폼 계정 연동 테이블
    cur.execute("""
        CREATE TABLE IF NOT EXISTS accounts (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            platform    TEXT NOT NULL,       -- naver | tistory | wordpress
            blog_url    TEXT,
            credentials TEXT,                -- JSON (e.g. state file path, API tokens)
            status      TEXT DEFAULT 'active',
            created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # 프로젝트 테이블
    cur.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id        INTEGER REFERENCES accounts(id),
            title             TEXT NOT NULL,
            description       TEXT,
            keywords          TEXT,
            category_name     TEXT,          -- 타겟 게시판/카테고리 이름
            posts_per_day     INTEGER DEFAULT 3,
            status            TEXT DEFAULT 'active',
            strategy_feedback TEXT,
            created_at        DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # 블로그 포스트 테이블
    cur.execute("""
        CREATE TABLE IF NOT EXISTS posts (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id    INTEGER REFERENCES projects(id),
            title         TEXT,
            content       TEXT,
            research_data TEXT,        -- 수집한 원본 자료 (JSON)
            status        TEXT DEFAULT 'researching',
                          -- researching | writing | pending_approval | approved | scheduled | published | rejected
            ceo_feedback  TEXT,
            scheduled_at  DATETIME,
            published_at  DATETIME,
            created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # 로그 테이블
    cur.execute("""
        CREATE TABLE IF NOT EXISTS logs (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id    INTEGER,
            agent      TEXT,
            message    TEXT,
            level      TEXT DEFAULT 'info',   -- info | warning | error
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # 통계 테이블 (일별 방문자 수 등 저장)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS daily_stats (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id  INTEGER REFERENCES accounts(id),
            stat_date   DATE NOT NULL,
            visitors    INTEGER DEFAULT 0,
            views       INTEGER DEFAULT 0,
            comments    INTEGER DEFAULT 0,
            created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(account_id, stat_date)
        )
    """)
    
    # 블로그 디자인/카테고리 기획안 테이블
    cur.execute("""
        CREATE TABLE IF NOT EXISTS blog_proposals (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id      INTEGER REFERENCES accounts(id),
            categories_json TEXT,           -- 제안된 카테고리 트리
            profile_bio     TEXT,           -- 제안된 프로필 소개말
            profile_img_url TEXT,           -- 제안된 프로필 사진 URL/경로
            status          TEXT DEFAULT 'pending_approval',  -- pending_approval | approved | applied | rejected
            created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    migrate_schema(conn)
    conn.commit()
    conn.close()
    print("✅ DB initialized.")

if __name__ == "__main__":
    init_db()
