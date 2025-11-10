# ui/import_students.py 
import re
import sys
import os
import pandas as pd
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QMessageBox, QComboBox, QLineEdit, QFrame,
    QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog
)
from PySide6.QtGui import QFont, QColor
from PySide6.QtCore import Qt
from PySide6.QtCore import Signal


try:
    from core.db import get_conn, q
    from core import session as core_session
except ImportError:
    print("HATA: import_students.py, core modüllerini yükleyemedi.")
    pass

NAVY = "#0f2535"
CARD = "#112b3d"

def _ensure_schema():
    """Create junction tables if they don't exist. Non-destructive."""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS ogrenciler(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          bolum_id INTEGER NOT NULL,
          kod TEXT NOT NULL,         -- Tkinter kodunda ogr_no -> kod yapılmıştı, geri alıyorum
          ad TEXT NOT NULL,          -- Tkinter kodunda ad_soyad -> ad yapılmıştı, geri alıyorum
          sinif_yili INTEGER NOT NULL -- Tkinter kodunda sinif -> sinif_yili yapılmıştı, geri alıyorum
        );
        """)
        
        try: cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_ogrenciler_bolum_kod ON ogrenciler(bolum_id, kod);")
        except: pass
        
        
        cur.execute("""
        CREATE TABLE IF NOT EXISTS kayitlar(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          ogrenci_id INTEGER NOT NULL REFERENCES ogrenciler(id),
          ders_id    INTEGER NOT NULL REFERENCES dersler(id),
          UNIQUE(ogrenci_id, ders_id)
        );
        """)
        conn.commit()

  #

def _fetch_bolumler_map():
    """Bölümleri {id: ad} ve {ad: id} olarak iki map şeklinde çeker."""
    
    bolumler_by_id = {}
    bolumler_by_name = {}
    try:
        with get_conn() as conn:
            cur = conn.cursor()
            cur.execute("SELECT id, ad FROM bolumler ORDER BY ad;")
            rows = cur.fetchall()
            for bolum_id, bolum_ad in rows:
                bolumler_by_id[bolum_id] = bolum_ad
                bolumler_by_name[bolum_ad] = bolum_id
        return bolumler_by_id, bolumler_by_name
    except Exception as e:
        print(f"HATA (import_students.py): Bölümler çekilemedi: {e}")
        return {}, {}

      

def _map_ogrenciler_schema():
    """ Map the real columns in 'ogrenciler'. """
    with get_conn() as conn: cur = conn.cursor(); cur.execute("PRAGMA table_info(ogrenciler);"); rows = cur.fetchall()
    if not rows: raise RuntimeError("ogrenciler tablosu bulunamadı.")
    cols = {r[1].lower(): r[1] for r in rows}
    def pick(*cands):
        for c in cands:
            if c in cols: return cols[c]
        return None
    bolum_id = pick("bolum_id","bolum")
    no_col   = pick("kod","ogr_no","ogrenci_no","numara")
    name_col = pick("ad","ad_soyad","isim")
    year_col = pick("sinif_yili","sinif") 
    missing = []
    if not bolum_id: missing.append("bolum_id")
    if not no_col:   missing.append("kod (öğrenci no)")
    if not name_col: missing.append("ad (ad soyad)")
    if not year_col: missing.append("sinif_yili")
    if missing: raise RuntimeError("ogrenciler tablosu eksik sütunlar: " + ", ".join(missing))
    return {"bolum_id": bolum_id, "no": no_col, "name": name_col, "year": year_col}

def _map_link_table():
    """ Use the teammate's M:N link table ('kayitlar'). """
    
    return {"table": "kayitlar", "ogrenci_id": "ogrenci_id", "ders_id": "ders_id"}

def _map_dersler_schema_for_lookup():
    """ We only need id / bolum_id / kod to match course codes. """
    with get_conn() as conn: cur = conn.cursor(); cur.execute("PRAGMA table_info(dersler);"); rows = cur.fetchall()
    if not rows: raise RuntimeError("dersler tablosu bulunamadı (önce dersleri içe aktarın).")
    cols = {r[1].lower(): r[1] for r in rows}
    def pick(*cands):
        for c in cands:
            if c in cols: return cols[c]
        return None
    id_col = pick("id"); bolum_id = pick("bolum_id","bolum"); kod_col = pick("kod","ders_kodu")
    miss = []
    if not id_col: miss.append("id");
    if not bolum_id: miss.append("bolum_id");
    if not kod_col: miss.append("kod");
    if miss: raise RuntimeError("dersler şeması eksik: " + ", ".join(miss))
    return {"id": id_col, "bolum_id": bolum_id, "kod": kod_col}

_sinif_re = re.compile(r"(\d+)")

def _parse_students_excel(filepath):
    """ Parses the student+course Excel format. """
    xl = pd.ExcelFile(filepath); students = {}; errors = []; flat = []
    for sheet in xl.sheet_names:
        try: df = xl.parse(sheet, header=None, dtype=str)
        except Exception as e: errors.append(f"[{sheet}] sayfası açılamadı: {e}"); continue
        for i in range(len(df)):
            vals = [v if isinstance(v, str) else ("" if pd.isna(v) else str(v)) for v in df.iloc[i].tolist()]
            while len(vals) < 4: vals.append("")
            ogr_no = vals[0].strip(); adsoy = vals[1].strip(); sinif_txt = vals[2].strip(); ders_kodu = vals[3].strip()
            if not ogr_no and not adsoy and not ders_kodu: continue
            m = _sinif_re.search(sinif_txt); sinif = int(m.group(1)) if m else 1
            if not ogr_no: errors.append(f"[{sheet}] satır {i+1}: Öğrenci No boş."); continue
            if not adsoy: errors.append(f"[{sheet}] satır {i+1}: Ad-Soyad boş."); continue
            if not ders_kodu: errors.append(f"[{sheet}] satır {i+1}: Ders kodu boş."); continue
            flat.append({"sheet":sheet,"row":i+1,"ogr_no":ogr_no,"ad_soyad":adsoy,"sinif":sinif,"ders":ders_kodu})
            st = students.setdefault(ogr_no, {"ogr_no":ogr_no,"ad_soyad":adsoy,"sinif":sinif,"dersler":[],"rows":[]})
            if st["ad_soyad"] != adsoy: st.setdefault("name_conflict", set()).add(adsoy)
            st["sinif"] = max(st["sinif"], sinif)
            st["dersler"].append(ders_kodu)
            st["rows"].append((sheet, i+1))
    return students, errors, flat

def _upsert_students_and_links(bolum_id, students, col_ogr, link_map, col_ders):
    """ Upserts students and links them to courses. """
    ok_links, errs = 0, []
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(f"SELECT {col_ders['id']}, {col_ders['kod']} FROM dersler WHERE {col_ders['bolum_id']}=?", (bolum_id,))
        code2id = {kod: did for (did, kod) in cur.fetchall()}
        sql_upsert_student_part1 = f"INSERT INTO ogrenciler({col_ogr['bolum_id']},{col_ogr['no']},{col_ogr['name']},{col_ogr['year']}) VALUES (?,?,?,?)"
        sql_upsert_student_part2 = f"ON CONFLICT({col_ogr['bolum_id']}, {col_ogr['no']}) DO UPDATE SET {col_ogr['name']}=excluded.{col_ogr['name']}, {col_ogr['year']}=excluded.{col_ogr['year']}"
        sql_upsert_student = q(f"{sql_upsert_student_part1} {sql_upsert_student_part2}") 
        sql_select_student_id = q(f"SELECT id FROM ogrenciler WHERE {col_ogr['bolum_id']}=? AND {col_ogr['no']}=?")
        sql_insert_link = q(f"INSERT OR IGNORE INTO {link_map['table']}({link_map['ogrenci_id']},{link_map['ders_id']}) VALUES (?,?)")

        for ogr_no, st in students.items():
            ogr_id = None
            try:
               
                cur.execute(sql_upsert_student, (bolum_id, ogr_no, st["ad_soyad"], st["sinif"]))
                
                cur.execute(sql_select_student_id, (bolum_id, ogr_no))
                row = cur.fetchone()
                if not row: raise Exception("Öğrenci ID alınamadı.")
                ogr_id = row[0]
            except Exception as e:
                
                if "syntax error" in str(e).lower() and "on conflict" in str(e).lower():
                     errs.append(f"{ogr_no}: UPSERT desteklenmiyor olabilir. Eski SQLite sürümü mü? Hata: {e}")
                else:
                     errs.append(f"{ogr_no}: Öğrenci kaydı hatası: {e}")
                continue 

            
            for kod in st["dersler"]:
                ders_id = code2id.get(kod)
                if not ders_id: errs.append(f"{ogr_no}: Ders kodu bulunamadı: {kod}"); continue
                try:
                    cur.execute(sql_insert_link, (ogr_id, ders_id))
                    ok_links += cur.rowcount 
                except Exception as e: errs.append(f"{ogr_no}: {link_map['table']} hatası ({kod}): {e}")
        conn.commit()
    return ok_links, errs

class ImportStudentsTab(QWidget):
    data_imported = Signal()
    """ Excel -> ogrenciler + kayitlar içe aktarma arayüzü """
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        
       
        if not core_session.current_user:
            self.setLayout(QVBoxLayout()); self.layout().addWidget(QLabel("Oturum hatası."))
            return
        self.user = core_session.current_user
        self.is_admin = (self.user.rol == "admin")
        self.fixed_bolum_id = None if self.is_admin else self.user.bolum_id
      

        try:
            _ensure_schema()
            self.col_ogr = _map_ogrenciler_schema()
            self.col_dx  = _map_link_table()
            self.col_ders = _map_dersler_schema_for_lookup()
        except Exception as e:
            QMessageBox.critical(self, "Veritabanı Şema Hatası", f"Öğrenci/Kayıt tabloları okunamadı/oluşturulamadı:\n{e}")
            return 

        self.bolumler_by_id, _ = _fetch_bolumler_map()
        self.selected_file = None
        self.init_ui()
        
    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        top_bar = QFrame(); top_bar.setStyleSheet(f"background-color: {CARD}; border-radius: 8px; padding: 10px;")
        top_layout = QHBoxLayout(top_bar); top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.addWidget(QLabel("Bölüm:"))
        self.cmb_bolum = QComboBox()
        if self.is_admin:
            self.cmb_bolum.addItem("— Bölüm Seçin —", userData=None)
            for bid, bad in self.bolumler_by_id.items(): self.cmb_bolum.addItem(f"{bid} - {bad}", userData=bid)
        else:
            bad = self.bolumler_by_id.get(self.fixed_bolum_id, "?"); self.cmb_bolum.addItem(f"{self.fixed_bolum_id} - {bad}", userData=self.fixed_bolum_id); self.cmb_bolum.setEnabled(False)
        top_layout.addWidget(self.cmb_bolum, stretch=1)
        self.btn_choose = QPushButton("Excel Dosyası Seç..."); self.btn_choose.setStyleSheet(f"background-color: {NAVY}; font-weight: bold; padding: 5px;")
        top_layout.addWidget(self.btn_choose)
        self.btn_import = QPushButton("İçe Aktar"); self.btn_import.setStyleSheet(f"background-color: {NAVY}; font-weight: bold; padding: 5px;")
        top_layout.addWidget(self.btn_import)
        main_layout.addWidget(top_bar)

       
        body_frame = QFrame(); body_frame.setStyleSheet(f"background-color: {CARD}; border-radius: 8px; padding: 10px;")
        body_layout = QVBoxLayout(body_frame)
        self.lbl_stats = QLabel("Lütfen içe aktarmak için bir Excel dosyası seçin."); self.lbl_stats.setStyleSheet("font-weight: bold;")
        body_layout.addWidget(self.lbl_stats)
        body_layout.addWidget(QLabel("Sonuç / Hata Günlüğü:"))
        self.table_log = QTableWidget(); self.table_log.setEditTriggers(QTableWidget.NoEditTriggers)
        cols = ("sheet","row","ogr_no","ad","sinif","ders","durum")
        self.table_log.setColumnCount(len(cols)); self.table_log.setHorizontalHeaderLabels(["Sayfa","Satır","Öğr.No","Ad Soyad","Sınıf","Ders","Durum"])
        self.table_log.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_log.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents) 
        self.table_log.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents) 
        body_layout.addWidget(self.table_log)
        main_layout.addWidget(body_frame, stretch=1)

        self.btn_choose.clicked.connect(self._choose_file)
        self.btn_import.clicked.connect(self._import)

    def _choose_file(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Excel Dosyası Seç", "", "Excel Dosyaları (*.xlsx *.xls)")
        if filepath: self.selected_file = filepath; filename = os.path.basename(filepath); self.lbl_stats.setText(f"Seçildi: {filename}")

    def _current_bolum_id(self):
        if not self.is_admin: return self.fixed_bolum_id
        return self.cmb_bolum.currentData()

    def _import(self):
        self.table_log.setRowCount(0)
        if not self.selected_file: QMessageBox.warning(self, "Dosya", "Önce bir Excel dosyası seçiniz."); return
        bolum_id = self._current_bolum_id()
        if not bolum_id: QMessageBox.warning(self, "Bölüm", "Bölüm seçiniz."); return

        try: students, parse_errs, flat = _parse_students_excel(self.selected_file)
        except Exception as e: QMessageBox.critical(self, "Okuma Hatası", str(e)); return

       
        self.table_log.setRowCount(len(flat) + len(parse_errs)) 
        log_row_idx = 0
        for r in flat:
            self.table_log.setItem(log_row_idx, 0, QTableWidgetItem(r["sheet"]))
            self.table_log.setItem(log_row_idx, 1, QTableWidgetItem(str(r["row"])))
            self.table_log.setItem(log_row_idx, 2, QTableWidgetItem(r["ogr_no"]))
            self.table_log.setItem(log_row_idx, 3, QTableWidgetItem(r["ad_soyad"]))
            self.table_log.setItem(log_row_idx, 4, QTableWidgetItem(str(r["sinif"])))
            self.table_log.setItem(log_row_idx, 5, QTableWidgetItem(r["ders"]))
            self.table_log.setItem(log_row_idx, 6, QTableWidgetItem("OK (Parsed)")) 
            log_row_idx += 1
        for err in parse_errs:
            self.table_log.setItem(log_row_idx, 6, QTableWidgetItem(f"Parse HATA: {err}"))
            log_row_idx += 1

       
        try:
             ok_links, db_errs = _upsert_students_and_links(bolum_id, students, self.col_ogr, self.col_dx, self.col_ders)
        except Exception as e:
             QMessageBox.critical(self, "Veritabanı Hatası", f"Öğrenci/kayıt eklenirken kritik hata:\n{e}")
           
             row_count = self.table_log.rowCount()
             self.table_log.insertRow(row_count)
             self.table_log.setItem(row_count, 6, QTableWidgetItem(f"KRİTİK DB HATA: {e}"))
             db_errs = [f"KRİTİK HATA: {e}"]
             ok_links = 0
        
        
        db_err_count = 0
        if db_errs:
            db_err_count = len(db_errs)
            needed_rows = log_row_idx + db_err_count - self.table_log.rowCount()
            if needed_rows > 0: self.table_log.setRowCount(self.table_log.rowCount() + needed_rows)
            for msg in db_errs:
                self.table_log.setItem(log_row_idx, 6, QTableWidgetItem(f"DB HATA: {msg}"))
                log_row_idx += 1

        total_errors = len(parse_errs) + db_err_count
        stats_text = f"Öğrenci: {len(students)} | Satır: {len(flat)} | Eşleştirme(öğrenci-ders): +{ok_links} | Hata: {total_errors}"
        self.lbl_stats.setText(stats_text)
        self.data_imported.emit()
        QMessageBox.information(self, "İçe Aktarım", f"Tamamlandı.\nÖğrenci: {len(students)}\nSatır: {len(flat)}\nEşleştirme: +{ok_links}\nHata: {total_errors}")


        