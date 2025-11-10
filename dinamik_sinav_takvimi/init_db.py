import sys
import os
import sqlite3
from pathlib import Path
import bcrypt

#
def resource_path(relative_path):
    """PyInstaller exe içinde doğru dosya yolunu bulmak için"""
    if hasattr(sys, '_MEIPASS'):
        return Path(os.path.join(sys._MEIPASS, relative_path))
    return Path(os.path.abspath(relative_path))

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "dst.sqlite3"

print(f"🗂️  Veritabanı: {DB_PATH}")

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()


schema_path = resource_path("core/schema.sqlite.sql")


if not schema_path.exists():
    raise FileNotFoundError(f"Şema dosyası bulunamadı: {schema_path}")

with open(schema_path, "r", encoding="utf-8") as f:
    schema_sql = f.read()
cur.executescript(schema_sql)



bolumler = [
    "Bilgisayar Müh.",
    "Yazılım Müh.",
    "Elektrik Müh.",
    "Elektronik Müh.",
    "İnşaat Müh.",
]
for b in bolumler:
    cur.execute("INSERT OR IGNORE INTO bolumler(ad) VALUES (?)", (b,))


email = "admin@kou.edu.tr"
plain_pw = b"123456"
hashed_pw = bcrypt.hashpw(plain_pw, bcrypt.gensalt()).decode("utf-8")

cur.execute(
    "INSERT OR IGNORE INTO kullanicilar(eposta, sifre_hash, rol, bolum_id) VALUES (?, ?, ?, NULL)",
    (email, hashed_pw, "admin"),
)

conn.commit()
conn.close()

print("✅ Veritabanı başarıyla oluşturuldu!")
print("🔑 Giriş: admin@kou.edu.tr / 123456")



