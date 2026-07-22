"""
Orchestrator Agent
CEO의 목표를 받아 포스트 작업을 생성하고, Researcher → Writer → Publisher 순서로 에이전트를 지휘합니다.
"""
import threading
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db import get_conn
from agents import researcher, writer, publisher
from config import ENABLE_EDITOR, ENABLE_TREND, ENABLE_QUALITY_SCORE, QUALITY_THRESHOLD, MAX_QUALITY_ATTEMPTS, ENABLE_SEO
from datetime import datetime, timedelta

def add_log(post_id, message, level="info"):
    conn = get_conn()
    conn.execute("INSERT INTO logs (post_id, agent, message, level) VALUES (?, 'Orchestrator', ?, ?)",
                 (post_id, message, level))
    conn.commit()
    conn.close()

def create_daily_posts(project_id: int, target_date: datetime = None):
    """
    프로젝트에 해당하는 특정 날짜(기본: 오늘)의 포스트 레코드를 생성합니다.
    """
    conn = get_conn()
    project = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    conn.close()
    
    if not project:
        return []
    
    keywords = [k.strip() for k in project["keywords"].split(",") if k.strip()]
    posts_per_day = project["posts_per_day"]
    
    post_ids = []
    conn = get_conn()
    
    target_dt = target_date if target_date else datetime.now()
    target_hours = [9, 13, 18]
    now = datetime.now()
    
    for i in range(posts_per_day):
        # 무작위 키워드 할당보다는 순환 할당
        import random
        # 매일 다른 키워드 조합을 위해 셔플
        kw_sample = random.sample(keywords, min(3, len(keywords))) if keywords else []
        kw_str = ", ".join(kw_sample) if kw_sample else project["title"]
        
        # 아침, 점심, 저녁 배정
        time_idx = i % 3
        scheduled_at = target_dt.replace(hour=target_hours[time_idx], minute=0, second=0, microsecond=0)
        
        # 이미 지났다면 과거 시간이지만 스케줄러가 즉시 처리하도록 둠 (혹은 5분 뒤)
        if scheduled_at < now:
            scheduled_at = now + timedelta(minutes=5 * (i+1))
            
        sched_str = scheduled_at.strftime("%Y-%m-%d %H:%M:%S")
        
        cur = conn.execute(
            "INSERT INTO posts (project_id, title, status, research_data, scheduled_at) VALUES (?, ?, 'researching', '', ?)",
            (project_id, f"[작성 중] {kw_str}", sched_str)
        )
        post_ids.append(cur.lastrowid)
    
    conn.commit()
    conn.close()
    return post_ids

def run_pipeline(post_id: int, keywords: list[str]):
    """
    단일 포스트에 대한 전체 파이프라인을 실행합니다.
    Trend 분석 → 자료 수집 → 글쓰기
    """
    try:
        # 1. 경쟁사 트렌드 분석 (선택)
        trend_strategy = ""
        if ENABLE_TREND:
            from agents import trend_agent
            trend_strategy = trend_agent.analyze_trends(post_id, keywords)
        
        # 2. 자료 수집
        research_data = researcher.research(post_id, keywords)
        
        # 3. 글 작성
        kw_str = ", ".join(keywords)
        title, content = writer.write(post_id, kw_str, research_data, trend_strategy)

        # 4. 품질 에디팅 (선택)
        if ENABLE_EDITOR and content:
            from agents import editor
            title, content = editor.edit(post_id, title, content)

        # 5. 품질 점수화 + 기준 미만 자동 개선 (선택)
        if ENABLE_QUALITY_SCORE and content:
            from agents import editor
            for attempt in range(1, MAX_QUALITY_ATTEMPTS + 1):
                total, detail = editor.score(post_id, title, content, attempt)
                if total is None or total >= QUALITY_THRESHOLD:
                    break
                if attempt < MAX_QUALITY_ATTEMPTS:
                    title, content = editor.improve(post_id, title, content, detail)

        # 6. SEO 태그 생성 (선택)
        seo_tags = ''
        if ENABLE_SEO and content:
            try:
                import seo
                tags = seo.generate_tags(title, content, kw_str)
                seo_tags = ', '.join(tags)
                add_log(post_id, f'SEO 태그: {seo_tags}')
            except Exception as e:
                add_log(post_id, f'SEO 태그 생성 실패: {e}', 'warning')

        # 최종본 DB 저장
        if content:
            conn = get_conn()
            conn.execute("UPDATE posts SET title = ?, content = ?, seo_tags = ? WHERE id = ?",
                         (title, content, seo_tags, post_id))
            conn.commit()
            conn.close()
        
    except Exception as e:
        add_log(post_id, f"파이프라인 오류: {e}", "error")
        conn = get_conn()
        conn.execute("UPDATE posts SET status = 'error' WHERE id = ?", (post_id,))
        conn.commit()
        conn.close()

def trigger_daily_pipeline(project_id: int, target_date: datetime = None):
    """
    프로젝트의 오늘자(혹은 특정일자) 포스트를 생성하고 백그라운드에서 파이프라인을 실행합니다.
    """
    conn = get_conn()
    project = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    conn.close()
    
    if not project or project["status"] != "active":
        return
        
    keywords = [k.strip() for k in project["keywords"].split(",") if k.strip()]
    post_ids = create_daily_posts(project_id, target_date)
    
    def run_all():
        for post_id in post_ids:
            import random
            kw_sample = random.sample(keywords, min(3, len(keywords))) if keywords else [project["title"]]
            run_pipeline(post_id, kw_sample)
    
    # 백그라운드 스레드로 실행
    t = threading.Thread(target=run_all, daemon=True)
    t.start()
    return post_ids

