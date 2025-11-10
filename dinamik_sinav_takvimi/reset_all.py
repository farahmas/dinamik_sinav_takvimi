# reset_all.py
from core.db import get_conn, q

def reset_all():
    with get_conn() as cn:
        cur = cn.cursor()
        print("🧹 Clearing all related tables...")

        # --- Remove dependent tables first (order matters!) ---
        cur.execute(q("DELETE FROM oturma_koltuklari"))
        cur.execute(q("DELETE FROM sinav_derslikleri"))
        cur.execute(q("DELETE FROM sinavlar"))
        cur.execute(q("DELETE FROM sinav_zamanlari"))
        cur.execute(q("DELETE FROM kayitlar"))
        cur.execute(q("DELETE FROM ogrenciler"))
        cur.execute(q("DELETE FROM dersler"))
        cur.execute(q("DELETE FROM derslikler"))
        cur.execute(q("DELETE FROM bolumler"))

        # Optionally keep users (admin, coordinators), or clear them too:
        # cur.execute(q("DELETE FROM kullanicilar"))

        cn.commit()

    print("✅ Database cleared. You can now re-import Excel data.")

if __name__ == "__main__":
    reset_all()
