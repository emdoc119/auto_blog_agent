"""
CEO 대시보드 - Flask 웹 애플리케이션
목표 입력 → 진행 현황 확인 → 초안 승인/거절 → 자동 발행
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, render_template, request, redirect, url_for, jsonify
from db import get_conn, init_db
from config import FLASK_HOST, FLASK_PORT, FLASK_SECRET_KEY, AUTO_PUBLISH
from agents import orchestrator, publisher
import time
import threading

app = Flask(__name__)
app.secret_key = FLASK_SECRET_KEY

# 앱 시작 시 DB 초기화
with app.app_context():
    init_db()

# ─────────────────────────────────────────────
# 메인 대시보드
# ─────────────────────────────────────────────
@app.route("/")
def dashboard():
    conn = get_conn()
    projects = conn.execute("SELECT * FROM projects ORDER BY created_at DESC").fetchall()
    
    stats = {
        "total":     conn.execute("SELECT COUNT(*) FROM posts").fetchone()[0],
        "pending":   conn.execute("SELECT COUNT(*) FROM posts WHERE status = 'pending_approval'").fetchone()[0],
        "published": conn.execute("SELECT COUNT(*) FROM posts WHERE status = 'published'").fetchone()[0],
        "running":   conn.execute("SELECT COUNT(*) FROM posts WHERE status IN ('researching','writing')").fetchone()[0],
    }
    
    recent_posts = conn.execute("""
        SELECT p.*, pr.title as project_title
        FROM posts p LEFT JOIN projects pr ON p.project_id = pr.id
        ORDER BY p.created_at DESC LIMIT 10
    """).fetchall()
    
    conn.close()
    return render_template("dashboard.html", projects=projects, stats=stats, recent_posts=recent_posts)

# ─────────────────────────────────────────────
# 계정 관리
# ─────────────────────────────────────────────
@app.route("/accounts", methods=["GET", "POST"])
def manage_accounts():
    conn = get_conn()
    if request.method == "POST":
        platform = request.form["platform"]
        blog_url = request.form["blog_url"]
        credentials = request.form["credentials"]
        conn.execute("INSERT INTO accounts (platform, blog_url, credentials) VALUES (?, ?, ?)",
                     (platform, blog_url, credentials))
        conn.commit()
        return redirect(url_for("manage_accounts"))
        
    accounts = conn.execute("SELECT * FROM accounts ORDER BY created_at DESC").fetchall()
    conn.close()
    return render_template("accounts.html", accounts=accounts)

# ─────────────────────────────────────────────
# 프로젝트 생성
# ─────────────────────────────────────────────
@app.route("/project/new", methods=["GET", "POST"])
def new_project():
    conn = get_conn()
    if request.method == "POST":
        title      = request.form["title"]
        description= request.form.get("description", "")
        keywords   = request.form["keywords"]
        posts_per_day = int(request.form.get("posts_per_day", 3))
        account_id = int(request.form.get("account_id", 1))
        category_name = request.form.get("category_name", "").strip()
        
        if not category_name:
            from google import genai
            import os
            client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
            response = client.models.generate_content(
                model='gemini-2.5-flash-lite',
                contents=f"프로젝트 제목 '{title}' 에 적합한 블로그 카테고리(게시판) 이름을 15자 이내로 1개만 생성해줘. (예: 웰니스 및 응급실, IT 기기 리뷰 등). 부가설명 없이 이름만 답변해."
            )
            category_name = response.text.strip()
        
        cur = conn.execute(
            "INSERT INTO projects (title, description, keywords, posts_per_day, account_id, category_name) VALUES (?, ?, ?, ?, ?, ?)",
            (title, description, keywords, posts_per_day, account_id, category_name)
        )
        project_id = cur.lastrowid
        conn.commit()
        conn.close()
        
        # 첫날 포스트 파이프라인 즉시 시작
        from agents import orchestrator
        orchestrator.trigger_daily_pipeline(project_id)
        
        return redirect(url_for("dashboard"))
    
    accounts = conn.execute("SELECT * FROM accounts WHERE status = 'active'").fetchall()
    conn.close()
    return render_template("new_project.html", accounts=accounts)

# ─────────────────────────────────────────────
# 프로젝트 상세 및 상태 제어
# ─────────────────────────────────────────────
@app.route("/project/<int:project_id>")
def view_project(project_id):
    conn = get_conn()
    project = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    
    if not project:
        conn.close()
        return "Project not found", 404
        
    posts = conn.execute("""
        SELECT * FROM posts 
        WHERE project_id = ? 
        ORDER BY created_at DESC
    """, (project_id,)).fetchall()
    
    stats = {
        "total": len(posts),
        "published": sum(1 for p in posts if p["status"] == "published"),
        "scheduled": sum(1 for p in posts if p["status"] == "scheduled"),
    }
    
    conn.close()
    return render_template("project_detail.html", project=project, posts=posts, stats=stats)

@app.route("/project/<int:project_id>/toggle", methods=["POST"])
def toggle_project(project_id):
    conn = get_conn()
    project = conn.execute("SELECT status FROM projects WHERE id = ?", (project_id,)).fetchone()
    if project:
        new_status = "paused" if project["status"] == "active" else "active"
        conn.execute("UPDATE projects SET status = ? WHERE id = ?", (new_status, project_id))
        conn.commit()
    conn.close()
    return redirect(url_for("view_project", project_id=project_id))

# ─────────────────────────────────────────────
# 초안 상세 보기 & 승인/거절
# ─────────────────────────────────────────────
@app.route("/post/<int:post_id>")
def view_post(post_id):
    conn = get_conn()
    post = conn.execute("""
        SELECT p.*, pr.title as project_title, pr.keywords
        FROM posts p LEFT JOIN projects pr ON p.project_id = pr.id
        WHERE p.id = ?
    """, (post_id,)).fetchone()
    
    logs = conn.execute(
        "SELECT * FROM logs WHERE post_id = ? ORDER BY created_at ASC",
        (post_id,)
    ).fetchall()
    conn.close()
    
    if not post:
        return "Post not found", 404
    
    return render_template("post_detail.html", post=post, logs=logs)

@app.route("/post/<int:post_id>/approve", methods=["POST"])
def approve_post(post_id):
    edited_title   = request.form.get("title")
    edited_content = request.form.get("content")
    
    conn = get_conn()
    conn.execute(
        "UPDATE posts SET status = 'approved', title = ?, content = ? WHERE id = ?",
        (edited_title, edited_content, post_id)
    )
    conn.commit()
    conn.close()
    
    # 승인 즉시 발행
    publisher.publish(post_id)
    
    return redirect(url_for("dashboard"))

@app.route("/post/<int:post_id>/reject", methods=["POST"])
def reject_post(post_id):
    feedback = request.form.get("feedback", "")
    conn = get_conn()
    conn.execute(
        "UPDATE posts SET status = 'rejected', ceo_feedback = ? WHERE id = ?",
        (feedback, post_id)
    )
    conn.commit()
    conn.close()
    return redirect(url_for("dashboard"))

@app.route("/post/<int:post_id>/retry", methods=["POST"])
def retry_post(post_id):
    """거절된 글을 재작성합니다."""
    conn = get_conn()
    post = conn.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
    project = conn.execute("SELECT * FROM projects WHERE id = ?", (post["project_id"],)).fetchone()
    conn.execute("UPDATE posts SET status = 'researching', title = '[재작성 중]', content = '' WHERE id = ?", (post_id,))
    conn.commit()
    conn.close()
    
    keywords = [k.strip() for k in project["keywords"].split(",") if k.strip()]
    
    import threading
    t = threading.Thread(
        target=orchestrator.run_pipeline,
        args=(post_id, keywords[:3]),
        daemon=True
    )
    t.start()
    
    return redirect(url_for("view_post", post_id=post_id))

# ==========================================
# 블로그 관리 에이전트 (Blog Manager)
# ==========================================
@app.route("/blog_manager")
def blog_manager():
    conn = get_conn()
    # 최근 제안안 5개 가져오기
    proposals = conn.execute("SELECT * FROM blog_proposals ORDER BY id DESC LIMIT 5").fetchall()
    
    # JSON 파싱해서 템플릿으로 전달
    parsed_proposals = []
    for p in proposals:
        import json
        cats = json.loads(p["categories_json"]) if p["categories_json"] else []
        parsed_proposals.append({
            "id": p["id"],
            "categories": cats,
            "profile_bio": p["profile_bio"],
            "profile_img_url": p["profile_img_url"],
            "status": p["status"],
            "created_at": p["created_at"]
        })
    conn.close()
    return render_template("blog_manager.html", proposals=parsed_proposals)

@app.route("/blog_manager/generate", methods=["POST"])
def generate_proposal():
    from agents.blog_manager import generate_blog_proposal
    # 현재는 기본 계정 ID 1 사용
    generate_blog_proposal(1)
    return redirect(url_for("blog_manager"))

@app.route("/blog_manager/apply/<int:proposal_id>", methods=["POST"])
def apply_proposal(proposal_id):
    conn = get_conn()
    conn.execute("UPDATE blog_proposals SET status = 'applied' WHERE id = ?", (proposal_id,))
    conn.commit()
    conn.close()
    
    # 백그라운드로 Playwright 스크립트 실행하여 적용
    import subprocess
    import threading
    def run_auto_manage():
        subprocess.run(["venv/bin/python", "auto_manage.py", str(proposal_id)])
        
    t = threading.Thread(target=run_auto_manage, daemon=True)
    t.start()
    
    return redirect(url_for("blog_manager"))

@app.route("/reset_all_errors", methods=["POST"])
def reset_all_errors():
    """모든 에러 상태의 글을 대기 중(pending)으로 일괄 복구합니다."""
    conn = get_conn()
    conn.execute("UPDATE posts SET status = 'pending' WHERE status = 'error'")
    conn.commit()
    conn.close()
    return redirect(url_for("dashboard"))

@app.route("/post/<int:post_id>/force_publish", methods=["POST"])
def force_publish(post_id):
    """에러가 났거나 스케줄 대기 중인 글을 즉시 발행합니다.
    만약 예약된(scheduled) 글을 강제로 당겨서 발행할 경우, 
    원래 스케줄 빈자리를 채우기 위해 새 글 작성을 백그라운드에서 시작합니다."""
    conn = get_conn()
    post = conn.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
    
    if not post:
        conn.close()
        return "Post not found", 404
        
    old_status = post["status"]
    
    # 1. 현재 글을 즉시 발행 상태로 변경하고 퍼블리셔 실행
    conn.execute("UPDATE posts SET status = 'publishing' WHERE id = ?", (post_id,))
    conn.commit()
    
    import threading
    t = threading.Thread(target=publisher.publish, args=(post_id,), daemon=True)
    t.start()
    
    # 2. 만약 원래 스케줄 대기 중이던 글을 미리 뽑아 썼다면, 그 시간대에 빈자리가 생기지 않도록 새 글 생성
    if old_status == "scheduled":
        project = conn.execute("SELECT * FROM projects WHERE id = ?", (post["project_id"],)).fetchone()
        keywords = [k.strip() for k in project["keywords"].split(",") if k.strip()]
        
        # 원래의 예약 시간 그대로 빈 포스트 생성
        cur = conn.execute(
            "INSERT INTO posts (project_id, title, status, research_data, scheduled_at) VALUES (?, ?, 'researching', '', ?)",
            (post["project_id"], "[빈자리 보충용 새 글 작성 중]", post["scheduled_at"])
        )
        new_post_id = cur.lastrowid
        conn.commit()
        
        # 새 글 작성 파이프라인 시작
        import random
        kw_sample = random.sample(keywords, min(3, len(keywords))) if keywords else [project["title"]]
        
        t2 = threading.Thread(
            target=orchestrator.run_pipeline,
            args=(new_post_id, kw_sample),
            daemon=True
        )
        t2.start()
        
    conn.close()
    return redirect(request.referrer or url_for("dashboard"))

# ─────────────────────────────────────────────
# 통계 분석 (Analytics) 대시보드
# ─────────────────────────────────────────────
@app.route("/analytics")
def analytics():
    conn = get_conn()
    accounts = conn.execute("SELECT * FROM accounts").fetchall()
    conn.close()
    return render_template("analytics.html", accounts=accounts)

@app.route("/api/stats")
def api_stats():
    account_id = request.args.get("account_id")
    days = int(request.args.get("days", 7))
    conn = get_conn()
    
    if account_id:
        query = "SELECT stat_date, visitors FROM daily_stats WHERE account_id = ? ORDER BY stat_date DESC LIMIT ?"
        rows = conn.execute(query, (account_id, days)).fetchall()
    else:
        # 전체 통계 합산
        query = "SELECT stat_date, SUM(visitors) as visitors FROM daily_stats GROUP BY stat_date ORDER BY stat_date DESC LIMIT ?"
        rows = conn.execute(query, (days,)).fetchall()
        
    conn.close()
    
    # Chart.js를 위해 오래된 날짜부터 정렬
    rows.reverse()
    
    return jsonify({
        "labels": [r["stat_date"] for r in rows],
        "visitors": [r["visitors"] for r in rows]
    })

# ─────────────────────────────────────────────
# API: 실시간 상태 폴링 (대시보드 자동 갱신)
# ─────────────────────────────────────────────
@app.route("/api/status")
def api_status():
    conn = get_conn()
    posts = conn.execute("""
        SELECT p.id, p.title, p.status, p.created_at, pr.title as project_title
        FROM posts p LEFT JOIN projects pr ON p.project_id = pr.id
        ORDER BY p.created_at DESC LIMIT 20
    """).fetchall()
    conn.close()
    return jsonify([dict(p) for p in posts])

@app.route("/api/logs/<int:post_id>")
def api_logs(post_id):
    conn = get_conn()
    logs = conn.execute(
        "SELECT * FROM logs WHERE post_id = ? ORDER BY created_at ASC",
        (post_id,)
    ).fetchall()
    conn.close()
    return jsonify([dict(l) for l in logs])

def background_scheduler():
    """주기적으로 예약된 포스트를 확인하고 발행합니다."""
    last_daily_check = None
    while True:
        try:
            conn = get_conn()
            from datetime import datetime, date
            now = datetime.now()
            today = now.date()
            
            # 1. 일일 피드백 분석 및 통계 수집
            if last_daily_check != today:
                print(f"📅 [{today}] 일일 프로젝트 점검 및 통계 수집 시작...")
                
                # 1-0. 방문자 통계 수집 (스크래퍼 실행)
                try:
                    from agents.stats_scraper import run_stats_scraper
                    run_stats_scraper()
                except Exception as e:
                    print(f"Stats Scraper error: {e}")

                active_projects = conn.execute("SELECT id FROM projects WHERE status = 'active'").fetchall()
                for p in active_projects:
                    try:
                        # 1-1. 성과 분석
                        from agents.feedback import analyze_and_update_strategy
                        analyze_and_update_strategy(p["id"])
                    except Exception as e:
                        print(f"Feedback Agent error for project {p['id']}: {e}")
                        
                    # 1-2. 오늘, 내일(2일치) 스케줄 포스트 생성
                    from datetime import timedelta
                    for day_offset in range(2):
                        target_date = today + timedelta(days=day_offset)
                        target_str = target_date.strftime("%Y-%m-%d")
                        count = conn.execute("SELECT COUNT(*) FROM posts WHERE project_id = ? AND date(scheduled_at) = ?", (p["id"], target_str)).fetchone()[0]
                        if count == 0:
                            print(f"  -> 프로젝트 {p['id']} {target_str} 포스트 파이프라인 시작")
                            from agents.orchestrator import trigger_daily_pipeline
                            trigger_daily_pipeline(p["id"], target_date=target_date)
                            import time
                            time.sleep(2) # 짧은 딜레이 추가
                
                last_daily_check = today

            # 1.5. 'pending' 상태의 밀린 포스트 1개 처리 (API 과부하 방지를 위해 1분당 1개씩만)
            pending_post = conn.execute("SELECT id, project_id FROM posts WHERE status = 'pending' LIMIT 1").fetchone()
            if pending_post:
                pp_id = pending_post["id"]
                project = conn.execute("SELECT * FROM projects WHERE id = ?", (pending_post["project_id"],)).fetchone()
                if project and project["status"] == "active":
                    conn.execute("UPDATE posts SET status = 'researching' WHERE id = ?", (pp_id,))
                    conn.commit()
                    keywords = [k.strip() for k in project["keywords"].split(",") if k.strip()]
                    import random
                    kw_sample = random.sample(keywords, min(3, len(keywords))) if keywords else [project["title"]]
                    
                    print(f"🔄 밀린 대기 중(pending) 포스트 {pp_id} 파이프라인 재시작...")
                    from agents.orchestrator import run_pipeline
                    t = threading.Thread(target=run_pipeline, args=(pp_id, kw_sample), daemon=True)
                    t.start()

            # 2. 예약된 시간 발행 확인
            now_str = now.strftime("%Y-%m-%d %H:%M:%S")
            posts = conn.execute("""
                SELECT p.id, p.project_id
                FROM posts p
                JOIN projects pr ON p.project_id = pr.id
                WHERE p.status = 'scheduled' 
                  AND p.scheduled_at <= ? 
                  AND pr.status = 'active'
                ORDER BY p.scheduled_at ASC
            """, (now_str,)).fetchall()
            
            from collections import defaultdict
            from datetime import timedelta
            
            project_posts = defaultdict(list)
            for post in posts:
                project_posts[post["project_id"]].append(post["id"])
                
            for project_id, post_ids in project_posts.items():
                # 현재 발행 중인 글이 있는지 확인 (동시 발행 방지)
                is_publishing = conn.execute("SELECT COUNT(*) FROM posts WHERE project_id = ? AND status = 'publishing'", (project_id,)).fetchone()[0]
                if is_publishing > 0:
                    continue
                
                # 가장 오래된 하나만 발행
                target_post_id = post_ids[0]
                print(f"⏰ 스케줄러: 포스트 {target_post_id} 예약 발행을 시작합니다! (프로젝트 {project_id})")
                conn.execute("UPDATE posts SET status = 'publishing' WHERE id = ?", (target_post_id,))
                conn.commit()
                
                t = threading.Thread(target=publisher.publish, args=(target_post_id,), daemon=True)
                t.start()
                
                # 나머지 밀린 포스트들은 1시간에 3개씩(5분 간격) 스케줄 강제 연기 (어뷰징 방지)
                if len(post_ids) > 1:
                    print(f"⚠️ 프로젝트 {project_id} 연달아 발행 대기 중: {len(post_ids)-1}개의 일정을 1시간당 3개씩 분산 처리합니다.")
                    for i, delayed_post_id in enumerate(post_ids[1:]):
                        group = (i + 1) // 3
                        position_in_group = (i + 1) % 3
                        delay_minutes = group * 60 + (position_in_group * 5)
                        new_time = now + timedelta(minutes=delay_minutes)
                        new_time_str = new_time.strftime("%Y-%m-%d %H:%M:%S")
                        conn.execute("UPDATE posts SET scheduled_at = ? WHERE id = ?", (new_time_str, delayed_post_id))
                    conn.commit()
            
            conn.close()
            
        except Exception as e:
            print(f"Scheduler error: {e}")
        
        time.sleep(60)

if __name__ == "__main__":
    if AUTO_PUBLISH:
        t = threading.Thread(target=background_scheduler, daemon=True)
        t.start()
        print("\n⏰ 백그라운드 스케줄러(예약 발행)가 시작되었습니다.")
        
    print(f"\n🚀 CEO 대시보드 시작: http://{FLASK_HOST}:{FLASK_PORT}\n")
    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=False)
