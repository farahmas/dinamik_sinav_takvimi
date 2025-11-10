# core/db.py
import os
from pathlib import Path


USE_SQLITE = os.getenv("USE_SQLITE", "1") == "1"


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_SQLITE_PATH = ROOT_DIR / "data" / "dst.sqlite3"


def _ensure_parent(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)


if USE_SQLITE:
    import sqlite3

    def get_conn():
        """
        SQLite bağlantısı döndürür.
        - Yol: ENV['SQLITE_PATH'] varsa onu, yoksa data/dst.sqlite3
        - Foreign key kısıtları: AÇIK
        """
        db_path = Path(os.getenv("SQLITE_PATH", str(DEFAULT_SQLITE_PATH)))
        _ensure_parent(db_path)
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

else:
    import psycopg2

    def get_conn():
        """
        PostgreSQL bağlantısı döndürür. ENV değişkenleri:
        DB_NAME, DB_USER, DB_PASS, DB_HOST, DB_PORT
        """
        return psycopg2.connect(
            dbname=os.getenv("DB_NAME", "dst"),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASS", "1234"),
            host=os.getenv("DB_HOST", "localhost"),
            port=os.getenv("DB_PORT", "5432"),
        )


def q(sql: str) -> str:
    """
    Yer tutucu çevirici:
    - SQLite: '?' kullan
    - PostgreSQL: '%s' kullan
    """
    return sql if USE_SQLITE else sql.replace("?", "%s")



def sqlite_path() -> Path:
    return Path(os.getenv("SQLITE_PATH", str(DEFAULT_SQLITE_PATH)))



def executescript(conn, schema_sql: str):
    """
    sqlite3.Connection.executescript benzeri; PG için cümle cümle çalıştırır.
    """
    if USE_SQLITE:
        conn.executescript(schema_sql)
    else:
        with conn:
            cur = conn.cursor()
            
            for stmt in [s.strip() for s in schema_sql.split(";")]:
                if stmt:
                    cur.execute(stmt)

                    
