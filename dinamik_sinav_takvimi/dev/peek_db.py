#peek_db.py
import sqlite3
con = sqlite3.connect(r"data/dst.sqlite3")
cur = con.cursor()
print("Tables:", cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall())



