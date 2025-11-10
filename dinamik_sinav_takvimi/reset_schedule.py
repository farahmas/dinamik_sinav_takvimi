# reset_schedule.py
from core.db import get_conn, q

with get_conn() as cn:
    cur = cn.cursor()
    cur.execute(q("DELETE FROM sinavlar"))
    cur.execute(q("DELETE FROM sinav_zamanlari"))
    cur.execute(q("DELETE FROM sinav_derslikleri"))
    cn.commit()

print("✅ Old exam schedule cleared.")

