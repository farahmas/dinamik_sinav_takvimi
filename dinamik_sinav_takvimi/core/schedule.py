from datetime import datetime, timedelta
from itertools import product
from random import shuffle
from core.db import get_conn, q
from core.errors import ErrorCodes, format_error, success_message
from core.export_excel import export_exam_excel_each_class


def build_exam_schedule(
    exam_type="vize",
    default_duration=75,
    break_time=15,
    avoid_overlap=True,
    start_date=None,
    end_date=None,
    holidays=None,
    selected_courses=None,
    exception_durations=None,
):
    """
    🔹 Dinamik sınav planlayıcı (rastgele derslik dağılımı + öğretim üyesi bilgisi ile)
    """
    try:
        with get_conn() as cn:
            cur = cn.cursor()
            try:
                dersler = cur.execute(
                    "SELECT id, kod, ad, sinif_yili, bolum_id, ogretim_uyesi FROM dersler"
                ).fetchall()
            except Exception:
                dersler = [
                    (*row, "—")
                    for row in cur.execute(
                        "SELECT id, kod, ad, sinif_yili, bolum_id FROM dersler"
                    ).fetchall()
                ]

            kayitlar = cur.execute("SELECT ogrenci_id, ders_id FROM kayitlar").fetchall()
            derslikler = cur.execute("SELECT id, ad, kapasite FROM derslikler").fetchall()

        if not dersler:
            return format_error(ErrorCodes.DERS_YOK, "Veritabanında hiç ders bulunamadı.")
        if not kayitlar:
            return format_error(ErrorCodes.OGRENCI_YOK, "Kayıtlı öğrenci bulunamadı.")
        if not derslikler:
            return format_error(ErrorCodes.DERSLIK_YOK, "Veritabanında derslik tanımlı değil.")

        if selected_courses:
            dersler = [d for d in dersler if d[0] in selected_courses]

        start_date = start_date or datetime.now().date()
        end_date = end_date or (start_date + timedelta(days=4))
        holidays = holidays or []

        days = [
            d for d in (start_date + timedelta(i)
                        for i in range((end_date - start_date).days + 1))
            if str(d) not in holidays and d.weekday() not in (5, 6)  # 5=Cumartesi, 6=Pazar
        ]

        if not days:
            return format_error(ErrorCodes.TARIH_ARALIGI, "Tüm günler tatil veya geçersiz.")

        times = [f"{h:02d}:00" for h in range(9, 18)]
        slots = [(d, t) for d, t in product(days, times)]

        dersler_by_sinif = {}
        for d_id, kod, ad, sinif_yili, bolum_id, ogretim_uyesi in dersler:
            dersler_by_sinif.setdefault(sinif_yili or 0, []).append(
                (d_id, kod, ad, sinif_yili, bolum_id, ogretim_uyesi)
            )

        ordered_dersler = []
        for i in range(max(len(v) for v in dersler_by_sinif.values())):
            for group in dersler_by_sinif.values():
                if i < len(group):
                    ordered_dersler.append(group[i])

        ders_to_ogr = {}
        for o, d in kayitlar:
            ders_to_ogr.setdefault(d, set()).add(o)

        student_busy = {}
        room_busy = {}
        plan = {}
        failed_courses = []

        for d_id, kod, ad, sinif_yili, bolum_id, ogretim_uyesi in ordered_dersler:
            ogrs = ders_to_ogr.get(d_id, set())
            if not ogrs:
                continue

            duration = (
                exception_durations.get(kod, default_duration)
                if exception_durations
                else default_duration
            )

            assigned = False
            for day, time in slots:
                conflict = False

                for sid in ogrs:
                    if sid in student_busy:
                        for (d2, t2) in student_busy[sid]:
                            if d2 == day and t2 == time:
                                conflict = True
                                break
                            if d2 == day:
                                h1, m1 = map(int, t2.split(":"))
                                h2, m2 = map(int, time.split(":"))
                                if abs((h2 * 60 + m2) - (h1 * 60 + m1)) < break_time:
                                    conflict = True
                                    break
                    if conflict:
                        break

                if conflict and avoid_overlap:
                    continue

                for dr_id, dr_ad, dr_kap in derslikler:
                    if (day, time, dr_id) in room_busy:
                        conflict = True
                        break
                if conflict:
                    continue

                rotated_rooms = derslikler[:]
                shuffle(rotated_rooms)

                total = len(ogrs)
                remaining = total
                derslik_kayit = []

                for dr_id, dr_ad, dr_kap in rotated_rooms:
                    if remaining <= 0:
                        break
                    take = min(dr_kap, remaining)
                    derslik_kayit.append((dr_id, dr_ad, take))
                    remaining -= take

                if remaining > 0:
                    failed_courses.append(
                        format_error(ErrorCodes.KAPASITE, f"{ad} ({total} öğrenci)")
                    )
                    assigned = True
                    break

                plan[d_id] = {
                    "kod": kod,
                    "ad": ad,
                    "ogretim_uyesi": ogretim_uyesi,
                    "day": day,
                    "time": time,
                    "duration": duration,
                    "derslikler": derslik_kayit,
                }

                for dr_id, _, _ in derslik_kayit:
                    h, m = map(int, time.split(":"))
                    occupied_end = h * 60 + m + duration + break_time
                    for h2 in range(9, 19):
                        t2 = f"{h2:02d}:00"
                        h2_m = h2 * 60
                        if h2_m < occupied_end:
                            room_busy[(day, t2, dr_id)] = True

                for sid in ogrs:
                    student_busy.setdefault(sid, []).append((day, time))

                assigned = True
                break

            if not assigned:
                failed_courses.append(
                    format_error(ErrorCodes.CAKISMA, f"{ad} için uygun zaman bulunamadı.")
                )

        with get_conn() as cn:
            cur = cn.cursor()
            cur.execute("DELETE FROM sinavlar")
            cur.execute("DELETE FROM sinav_zamanlari")
            cur.execute("DELETE FROM sinav_derslikleri")

            exam_type_map = {"vize": "vize", "final": "final", "bütünleme": "but", "butunleme": "but"}
            exam_type_db = exam_type_map.get(exam_type.lower(), "vize")

            for d_id, info in plan.items():
                cur.execute(
                    q("INSERT INTO sinav_zamanlari (sinav_turu, gun, baslama_saat, sure_dk) VALUES (?, ?, ?, ?)"),
                    (exam_type_db, str(info["day"]), info["time"], info["duration"]),
                )
                zaman_id = cur.lastrowid

                cur.execute(q("INSERT INTO sinavlar (ders_id, zaman_id) VALUES (?, ?)"), (d_id, zaman_id))
                sinav_id = cur.lastrowid

                for dr_id, _, kota in info["derslikler"]:
                    cur.execute(
                        q("INSERT INTO sinav_derslikleri (sinav_id, derslik_id, kota) VALUES (?, ?, ?)"),
                        (sinav_id, dr_id, kota),
                    )
            cn.commit()

        plans_by_dept = {}
        for d_id, v in plan.items():
            ders_row = next((d for d in dersler if d[0] == d_id), None)
            if not ders_row:
                continue
            _, kod, ad, sinif_yili, bolum_id, ogretim_uyesi = ders_row
            sinif_yili = sinif_yili if sinif_yili in (1, 2, 3, 4) else 1

            with get_conn() as cn:
                cur = cn.cursor()
                cur.execute("SELECT ad FROM bolumler WHERE id = ?", (bolum_id,))
                row = cur.fetchone()
                bolum_ad = row[0] if row else "Bilinmeyen Bölüm"

            plans_by_dept.setdefault(bolum_ad, {}).setdefault(sinif_yili, []).append({
                "Tarih": v["day"],
                "Saat": v["time"],
                "Ders Adı": v["ad"],
                "Öğretim Elemanı": v["ogretim_uyesi"] or "—",
                "Derslik": ", ".join(f"{x[1]} ({x[2]})" for x in v["derslikler"]),
            })

        created_files = export_exam_excel_each_class(plans_by_dept, exam_type=exam_type)

        if failed_courses:
            msg = "⚠️ Bazı dersler planlanamadı:\n" + "\n".join(failed_courses)
        else:
            msg = success_message(f"{len(plan)} sınav başarıyla planlandı.")

        msg += f"\n\n📁 {len(created_files)} Excel dosyası oluşturuldu:"
        for f in created_files:
            msg += f"\n - {f}"

        return msg

    except Exception as e:
        return format_error(ErrorCodes.GENEL, f"Beklenmeyen hata: {e}")
