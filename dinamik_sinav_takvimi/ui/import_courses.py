# ui/import_courses.py 
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
    print("HATA: import_courses.py, core modüllerini yükleyemedi.")
    pass


NAVY = "#0f2535"
CARD = "#112b3d"


def _table_info():
    """Return list of PRAGMA table_info(dersler) rows."""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(dersler);")
      
        return cur.fetchall()

def _neutral_default(sql_type: str):
    """Return a safe default for NOT NULL cols with no explicit default."""
    t = (sql_type or "").upper()
    if any(x in t for x in ("INT", "REAL", "NUM", "DEC")):
        return 0
    return ""  

def _map_dersler_schema():
    """
    Map real columns in dersler to logical names we use from Excel.
    Required: bolum_id, kod, ad, sinif_yili
    Optional: ogretim_uyesi (hoca), secmeli (0/1 or boolean)
    """
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(dersler);")
        cols = {row[1].lower(): row[1] for row in cur.fetchall()}

    if not cols:
        
        return {
            "bolum_id": "bolum_id",
            "kod": "kod",
            "ad": "ad",
            "sinif_yili": "sinif_yili",
            "hoca": "ogretim_uyesi",
            "secmeli": "secmeli",
        }

    def pick(*names):
        for n in names:
            if n in cols: return cols[n]
        return None

    mapping = {
        "bolum_id":   pick("bolum_id","bolum"),
        "kod":        pick("kod","ders_kodu","code"),
        "ad":         pick("ad","ders_adi","dersin_adi","isim","name","title"),
        "sinif_yili": pick("sinif_yili","sinif","yil","yili"),
        # optional
        "hoca":       pick("ogretim_uyesi","ogretim_elemani","ogretim_gorevlisi","hoca"),
        "secmeli":    pick("secmeli","secimli","bool_secmeli","is_secmeli","sec"),
    }

    missing = [k for k in ("bolum_id","kod","ad","sinif_yili") if mapping[k] is None]
    if missing:
        raise RuntimeError("dersler tablosunda zorunlu sütunlar bulunamadı: " + ", ".join(missing))
    return mapping

def _ensure_schema():
    """Create dersler if missing – in your teammate's shape."""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS dersler(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          bolum_id INTEGER NOT NULL,
          kod TEXT NOT NULL,
          ad  TEXT NOT NULL,
          sinif_yili INTEGER NOT NULL,
          secmeli INT NOT NULL,            -- 0/1  (Zorunlu=0, Seçmeli=1)
          ogretim_uyesi TEXT NOT NULL
        );
        """)
        try:
            cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_dersler_bolum_kod ON dersler(bolum_id, kod);")
        except Exception:
            pass
        conn.commit()

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
        print(f"HATA (import_courses.py): Bölümler çekilemedi: {e}")
        return {}, {}

def _insert_rows(bolum_id, rows, colmap):
    """
    Insert each parsed row into 'dersler', adapting to extra NOT NULL columns.
    Uses teammate's columns: ogretim_uyesi and secmeli (0/1).
    """
    info = _table_info()
    if not info:
        return [(r, False, "dersler tablosu bulunamadı") for r in rows]

    pk_names = {r[1] for r in info if r[5] == 1}

    cols_ordered, getters = [], []
    def add_col(colname, getter):
        if colname in pk_names:  
            return
        cols_ordered.append(colname); getters.append(getter)

   
    add_col(colmap["bolum_id"],   lambda r: bolum_id)
    add_col(colmap["kod"],        lambda r: r["kod"])
    add_col(colmap["ad"],         lambda r: r["ad"])
    add_col(colmap["sinif_yili"], lambda r: r["sinif_yili"])

    
    if colmap.get("hoca"):
        add_col(colmap["hoca"], lambda r: r.get("hoca",""))


    if colmap.get("secmeli"):
        def _to_secmeli(r):
            t = str(r.get("tip","Z")).strip().lower()
            return 1 if t.startswith("s") else 0
        add_col(colmap["secmeli"], _to_secmeli)

  
    needed = set(cols_ordered)
    for cid, name, ctype, notnull, dflt, pk in info:
        if pk == 1 or name in needed:
            continue
        if notnull == 1 and dflt is None:
            default_val = _neutral_default(ctype)
            add_col(name, (lambda v=default_val: (lambda _r: v))())

    placeholders = ",".join(["?"] * len(cols_ordered))
    col_list       = ",".join(cols_ordered)
    sql = f"INSERT OR REPLACE INTO dersler({col_list}) VALUES ({placeholders})"
    sql = q(sql) 

    out = []
    with get_conn() as conn:
        cur = conn.cursor()
        for r in rows:
            try:
                params = tuple(g(r) for g in getters)
                cur.execute(sql, params)
                out.append((r, True, ""))
            except Exception as e:
                out.append((r, False, str(e)))
        conn.commit()
    return out

def _parse_excel(filepath):
    """
    Accepts the formatted workbook shown in the screenshot.
    Returns: list[ {sheet, row, kod, ad, hoca, sinif_yili, tip} ], list[error strings]
    """
    results, errors = [], []
    xl = pd.ExcelFile(filepath)
    for sheet_name in xl.sheet_names:
        try:
            df = xl.parse(sheet_name, header=None, dtype=str)
        except Exception as e:
            errors.append(f"[{sheet_name}] sayfası açılamadı: {e}")
            continue

        current_year = None
        current_tip = 'Z'  
        
        for i in range(len(df)):
            row_vals = [str(x).strip() if pd.notna(x) else "" for x in df.iloc[i].tolist()]
            joined = " ".join(row_vals).lower()

         
            if any(s in joined for s in ["1. sınıf", "2. sınıf", "3. sınıf", "4. sınıf"]):
                
                for cand in (1,2,3,4,5,6,7,8):
                    if f"{cand}. sınıf" in joined:
                        current_year = cand
                        break
                current_tip = 'Z'
                continue

           
            if "seçmeli ders" in joined:
                current_tip = 'S'
                continue

            
            if ("ders kodu" in joined and "dersin adı" in joined) or ("ders kodu" in joined and "ders adı" in joined):
                continue

           
            cells = [c for c in row_vals if c]
            if current_year and len(cells) >= 2:
                kod = row_vals[0].strip()
                ad  = row_vals[1].strip()
                hoca = row_vals[2].strip() if len(row_vals) > 2 else ""
                
                if not kod or not ad:
                    continue
              
                if kod.lower().startswith("ders kodu") or ad.lower().startswith("ders"):
                    continue
                results.append({
                    "sheet": sheet_name,
                    "row": i+1,
                    "kod": kod,
                    "ad": ad,
                    "hoca": hoca,
                    "sinif_yili": int(current_year),
                    "tip": current_tip
                })
            else:
                pass
    return results, errors

class ImportCoursesTab(QWidget):
    data_imported = Signal()
    """
    Excel -> dersler tablosu içe aktarma arayüzü
    """
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        
        if not core_session.current_user:
            self.setLayout(QVBoxLayout())
            self.layout().addWidget(QLabel("Oturum hatası. Lütfen tekrar giriş yapın."))
            return
            
        self.user = core_session.current_user
        self.is_admin = (self.user.rol == "admin")
        self.fixed_bolum_id = None if self.is_admin else self.user.bolum_id
        
        
        try:
            self.colmap = _map_dersler_schema()
            _ensure_schema()
        except Exception as e:
            QMessageBox.critical(self, "Veritabanı Şema Hatası", f"Dersler tablosu şeması okunamadı/oluşturulamadı:\n{e}")
            return

        self.bolumler_by_id, _ = _fetch_bolumler_map()
        self.selected_file = None

        self.init_ui()
        
    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        top_bar = QFrame()
        top_bar.setStyleSheet(f"background-color: {CARD}; border-radius: 8px; padding: 10px;")
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(0, 0, 0, 0)
        
        top_layout.addWidget(QLabel("Bölüm:"))
        self.cmb_bolum = QComboBox()
        if self.is_admin:
            for bolum_id, bolum_ad in self.bolumler_by_id.items():
                self.cmb_bolum.addItem(f"{bolum_id} - {bolum_ad}", userData=bolum_id)
        else:
            bolum_ad = self.bolumler_by_id.get(self.fixed_bolum_id, "Bilinmeyen Bölüm")
            self.cmb_bolum.addItem(f"{self.fixed_bolum_id} - {bolum_ad}", userData=self.fixed_bolum_id)
            self.cmb_bolum.setEnabled(False)
        top_layout.addWidget(self.cmb_bolum, stretch=1)
        
        self.btn_choose = QPushButton("Excel Dosyası Seç...")
        self.btn_choose.setStyleSheet(f"background-color: {NAVY}; font-weight: bold; padding: 5px;")
        top_layout.addWidget(self.btn_choose)
        
        self.btn_import = QPushButton("İçe Aktar")
        self.btn_import.setStyleSheet(f"background-color: {NAVY}; font-weight: bold; padding: 5px;")
        top_layout.addWidget(self.btn_import)
        
        main_layout.addWidget(top_bar)

        body_frame = QFrame()
        body_frame.setStyleSheet(f"background-color: {CARD}; border-radius: 8px; padding: 10px;")
        body_layout = QVBoxLayout(body_frame)
        
        self.lbl_stats = QLabel("Lütfen içe aktarmak için bir Excel dosyası seçin.")
        self.lbl_stats.setStyleSheet("font-weight: bold;")
        body_layout.addWidget(self.lbl_stats)

        body_layout.addWidget(QLabel("Sonuç / Hata Günlüğü:"))
        
        self.table_log = QTableWidget()
        self.table_log.setEditTriggers(QTableWidget.NoEditTriggers)
        cols = ("sheet","row","kod","ad","hoca","sinif","tip","durum")
        self.table_log.setColumnCount(len(cols))
        self.table_log.setHorizontalHeaderLabels(["Sayfa","Satır","Kod","Ad","Hoca","Sınıf","Tip","Durum"])
        self.table_log.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_log.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents) # Row
        self.table_log.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents) # Sınıf
        body_layout.addWidget(self.table_log)

        main_layout.addWidget(body_frame, stretch=1)

        self.btn_choose.clicked.connect(self._choose_file)
        self.btn_import.clicked.connect(self._import)

    def _choose_file(self):

        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Excel Dosyası Seç",
            "", 
            "Excel Dosyaları (*.xlsx *.xls)"
        )
        if filepath:
            self.selected_file = filepath
            filename = os.path.basename(filepath)
            self.lbl_stats.setText(f"Seçildi: {filename}")

    def _current_bolum_id(self):
        """Seçili bölüm ID'sini döndürür."""
        if not self.is_admin:
            return self.fixed_bolum_id
        return self.cmb_bolum.currentData()

    def _import(self):
        self.table_log.setRowCount(0)
        if not self.selected_file:
            QMessageBox.warning(self, "Dosya", "Önce bir Excel dosyası seçiniz.")
            return

        bolum_id = self._current_bolum_id()
        if not bolum_id:
            QMessageBox.warning(self, "Bölüm", "Bölüm seçiniz.")
            return

        try:
            parsed, parse_errors = _parse_excel(self.selected_file)
        except Exception as e:
            QMessageBox.critical(self, "Okuma Hatası", str(e))
            return

        for err in parse_errors:
            row_count = self.table_log.rowCount()
            self.table_log.insertRow(row_count)
            self.table_log.setItem(row_count, 7, QTableWidgetItem(f"HATA: {err}"))

        results = _insert_rows(bolum_id, parsed, self.colmap)

        ok_count = 0
        err_count = 0
        for r, ok, msg in results:
            status = "OK" if ok else f"DB HATA: {msg}"
            if ok: ok_count += 1
            else:  err_count += 1
            
            row_count = self.table_log.rowCount()
            self.table_log.insertRow(row_count)
            self.table_log.setItem(row_count, 0, QTableWidgetItem(r.get("sheet","")))
            self.table_log.setItem(row_count, 1, QTableWidgetItem(str(r.get("row",""))))
            self.table_log.setItem(row_count, 2, QTableWidgetItem(r.get("kod","")))
            self.table_log.setItem(row_count, 3, QTableWidgetItem(r.get("ad","")))
            self.table_log.setItem(row_count, 4, QTableWidgetItem(r.get("hoca","")))
            self.table_log.setItem(row_count, 5, QTableWidgetItem(str(r.get("sinif_yili",""))))
            self.table_log.setItem(row_count, 6, QTableWidgetItem(r.get("tip","")))
            self.table_log.setItem(row_count, 7, QTableWidgetItem(status))

        total_errors = err_count + len(parse_errors)
        stats_text = f"Toplam: {len(parsed)} | Eklendi/Güncellendi: {ok_count} | Hata: {total_errors}"
        self.lbl_stats.setText(stats_text)
        self.data_imported.emit()

        QMessageBox.information(
            self,
            "İçe Aktarım",
            f"Tamamlandı.\nEklendi/Güncellendi: {ok_count}\nHata: {total_errors}"
        )



        