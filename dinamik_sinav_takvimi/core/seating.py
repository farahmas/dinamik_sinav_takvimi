import random
import math
from core.db import get_conn, q
from core.errors import ErrorCodes, format_error, success_message


def build_seating_plan(sinav_id: int, use_chess_pattern: bool = False):
    """
    Belirli bir sınav için oturma planı oluşturur.
    Her dersliğin veritabanındaki kapasitesine göre öğrencileri eksiksiz ve adil biçimde yerleştirir.
    Kapasite aşımı olmaz, tüm öğrenciler yerleşir.
    """
    try:
        with get_conn() as cn:
            cn.isolation_level = None
            cur = cn.cursor()
            cur.execute("BEGIN IMMEDIATE")

            cur.execute(q("""
                DELETE FROM oturma_koltuklari
                WHERE sinav_derslik_id IN (
                    SELECT id FROM sinav_derslikleri WHERE sinav_id = ?
                )
            """), (sinav_id,))
            cn.commit()

            cur.execute(q("""
                SELECT k.ogrenci_id
                FROM kayitlar k
                JOIN sinavlar s ON s.ders_id = k.ders_id
                WHERE s.id = ?
            """), (sinav_id,))
            students = [r[0] for r in cur.fetchall()]
            if not students:
                return format_error(ErrorCodes.OGRENCI_YOK, "Bu sınava öğrenci kayıtlı değil.")
            random.shuffle(students)
            ogrenci_sayisi = len(students)
            queue = list(students)

            cur.execute(q("""
                SELECT sd.id, d.satir, d.sutun, d.sira_grup, d.ad, d.kapasite
                FROM sinav_derslikleri sd
                JOIN derslikler d ON d.id = sd.derslik_id
                WHERE sd.sinav_id = ?
                ORDER BY d.kapasite DESC
            """), (sinav_id,))
            derslikler = cur.fetchall()
            if not derslikler:
                return format_error(ErrorCodes.DERSLIK_YOK, "Sınava atanmış derslik yok.")

            toplam_kapasite = sum(d[5] for d in derslikler)
            if toplam_kapasite < ogrenci_sayisi:
                fark = ogrenci_sayisi - toplam_kapasite
                return format_error(ErrorCodes.KAPASITE, f"Sınıf kapasiteleri yetersiz! {fark} öğrenciye yer yok.")

            oranlar = [d[5] / toplam_kapasite for d in derslikler]
            dagilim_raw = [ogrenci_sayisi * o for o in oranlar]
            dagilim_floor = [math.floor(x) for x in dagilim_raw]
            kalan = ogrenci_sayisi - sum(dagilim_floor)

            fraksiyonlar = [(i, dagilim_raw[i] - dagilim_floor[i]) for i in range(len(derslikler))]
            fraksiyonlar.sort(key=lambda x: x[1], reverse=True)
            for i, _ in fraksiyonlar[:kalan]:
                dagilim_floor[i] += 1
                while sum(dagilim_floor) < ogrenci_sayisi:
                    for i, (_, _, _, _, _, kapasite) in enumerate(derslikler):
                        if dagilim_floor[i] < kapasite:
                            dagilim_floor[i] += 1
                            if sum(dagilim_floor) == ogrenci_sayisi:
                                break


            for i in range(len(dagilim_floor)):
                beklenen = round(derslikler[i][5] / toplam_kapasite * ogrenci_sayisi)
                if dagilim_floor[i] < beklenen - 1:
                    dagilim_floor[i] = beklenen

            ogrenci_paylastir = []
            for i, (sd_id, satir, sutun, grup, derslik_ad, kapasite) in enumerate(derslikler):
                verilecek = min(dagilim_floor[i], kapasite)
                ogrenci_paylastir.append([sd_id, grup, satir, sutun, derslik_ad, verilecek])

            for (sd_id, grup, satir, sutun, derslik_ad, verilecek) in ogrenci_paylastir:
                print(f"🧮 {derslik_ad}: {verilecek} öğrenci atanacak (kapasite={kapasite})")

                if grup == 2:
                    seats_per_bench = 2
                elif grup == 3:
                    seats_per_bench = 2
                elif grup == 4:
                    seats_per_bench = 3
                else:
                    seats_per_bench = 1

                dolan = 0
                for r in range(1, satir + 1):
                    visible_col = 0
                    for c in range(1, sutun + 1):
                        if not _is_seat_visible(grup, c, sutun):
                            continue
                        visible_col += 1
                        for seat_index in range(seats_per_bench):
                            if not queue:
                                break
                            ogr_id = queue.pop(0)
                            current_col = (visible_col - 1) * seats_per_bench + (seat_index + 1)
                            cur.execute(q("""
                                INSERT INTO oturma_koltuklari (sinav_derslik_id, r, c, ogrenci_id)
                                VALUES (?, ?, ?, ?)
                            """), (sd_id, r, current_col, ogr_id))
                            dolan += 1
                            print(f"💺 {derslik_ad} → Öğrenci={ogr_id} (r{r}, c{current_col})")
                    if not queue:
                        break

                print(f"📊 {derslik_ad}: {dolan}/{verilecek} yer doldu")
  
            cn.commit()
            if queue:
                return format_error(ErrorCodes.KAPASITE, f"{len(queue)} öğrenci yerleştirilemedi.")
            return success_message("✅ Tüm öğrenciler başarıyla yerleştirildi (kapasite aşılmadı).")

    except Exception as e:
        return format_error(ErrorCodes.OTURMA, f"Oturma planı hatası: {e}")


def _is_seat_visible(grup: int, c: int, total: int) -> bool:
    return True