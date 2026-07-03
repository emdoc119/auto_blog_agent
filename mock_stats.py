import sqlite3
from datetime import datetime, timedelta
import random
from config import DB_PATH

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

accounts = cur.execute("SELECT id FROM accounts").fetchall()
for acc in accounts:
    acc_id = acc[0]
    for i in range(7, 0, -1):
        dt = (datetime.now() - timedelta(days=i)).date().isoformat()
        visitors = random.randint(30, 150)
        cur.execute("INSERT OR IGNORE INTO daily_stats (account_id, stat_date, visitors) VALUES (?, ?, ?)",
                    (acc_id, dt, visitors))

conn.commit()
conn.close()
print("Mock stats inserted.")
