import sqlite3
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import DB_PATH

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# Create accounts table
cur.execute("""
CREATE TABLE IF NOT EXISTS accounts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    platform    TEXT NOT NULL,
    blog_url    TEXT,
    credentials TEXT,
    status      TEXT DEFAULT 'active',
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
)
""")

# Insert default naver account if empty
acc = cur.execute("SELECT id FROM accounts WHERE platform = 'naver'").fetchone()
if not acc:
    cur.execute("INSERT INTO accounts (platform, blog_url, credentials) VALUES ('naver', '기본 네이버 블로그', '{\"state_file\": \"naver_state.json\"}')")
    account_id = cur.lastrowid
else:
    account_id = acc['id']

# Alter projects table
try:
    cur.execute("ALTER TABLE projects ADD COLUMN account_id INTEGER REFERENCES accounts(id)")
    cur.execute("ALTER TABLE projects ADD COLUMN category_name TEXT")
except Exception as e:
    print(f"Alter projects error (maybe already exists): {e}")

# Update existing projects to use account 1
cur.execute("UPDATE projects SET account_id = ? WHERE account_id IS NULL", (account_id,))
conn.commit()
conn.close()
print("Phase 2 DB setup complete.")
