# ui/students.py 
import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QMessageBox, QComboBox, QLineEdit, QFrame,
    QTableWidget, QTableWidgetItem, QHeaderView
)
from PySide6.QtGui import QColor
from PySide6.QtCore import Qt


try:
    from core.db import get_conn, q
    from core import session as core_session
except ImportError:
    print("HATA: students.py, core modüllerini yükleyemedi.")
    pass

NAVY = "#0f2535"
CARD = "#112b3d"
TEXT = "#e8f5e9"
SUBTEXT = "#bcd0d6"
ALT_BG_1 = QColor("#163754")
ALT_BG_2 = QColor("#193e5f")

def _fetch_bolumler_map():
    """Bölümleri {id: ad} ve {ad: id} olarak döndürür."""
    bolumler_by_id = {}
    bolumler_by_name = {}
    try:
        with get_conn() as conn:
            cur = conn.cursor()
            cur.execute("SELECT id, ad FROM bolumler ORDER BY ad;")
            for bolum_id, bolum_ad in cur.fetchall():
                bolumler_by_id[bolum_id] = bolum_ad
                bolumler_by_name[bolum_ad] = bolum_id
        return bolumler_by_id, bolumler_by_name
    except Exception as e:
        print(f"HATA (students.py): Bölümler çekilemedi: {e}")
        return {}, {}

class StudentsTab(QWidget):
    """Öğrenci Arama sekmesi (rol bazlı erişim ile)"""
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

        self.bolumler_by_id, self.bolumler_by_name = _fetch_bolumler_map()

        self.init_ui()
        self.connect_signals()
        self._search()

   
    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        top_bar = QFrame()
        top_bar.setStyleSheet(f"background-color: {CARD}; border-radius: 8px;")
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(10, 10, 10, 10)

        top_layout.addWidget(QLabel("Bölüm:"))
        self.cmb_bolum = QComboBox()
        if self.is_admin:
            for bid, ad in self.bolumler_by_id.items():
                self.cmb_bolum.addItem(f"{bid} - {ad}", userData=bid)
        else:
            bolum_ad = self.bolumler_by_id.get(self.fixed_bolum_id, "Bilinmeyen Bölüm")
            self.cmb_bolum.addItem(f"{self.fixed_bolum_id} - {bolum_ad}", userData=self.fixed_bolum_id)
            self.cmb_bolum.setEnabled(False)
        top_layout.addWidget(self.cmb_bolum)

        top_layout.addWidget(QLabel("Ara (No/Ad):"), alignment=Qt.AlignRight)
        self.ent_q = QLineEdit()
        self.ent_q.setPlaceholderText("Öğrenci no veya adı...")
        top_layout.addWidget(self.ent_q)

        self.btn_search = QPushButton("Ara")
        self.btn_search.setStyleSheet(f"background-color: {NAVY}; font-weight:bold; padding:5px;")
        top_layout.addWidget(self.btn_search)
        main_layout.addWidget(top_bar)

        body_layout = QHBoxLayout()
        body_layout.setSpacing(20)

        left_panel = QFrame()
        left_panel.setStyleSheet(f"background-color:{CARD}; border-radius:8px; padding:10px;")
        left_layout = QVBoxLayout(left_panel)
        left_layout.addWidget(QLabel("Öğrenciler"))

        self.table_ogrenciler = QTableWidget()
        self.table_ogrenciler.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table_ogrenciler.setSelectionBehavior(QTableWidget.SelectRows)
        self.table_ogrenciler.setSelectionMode(QTableWidget.SingleSelection)
        self.table_ogrenciler.setColumnCount(4)
        self.table_ogrenciler.setHorizontalHeaderLabels(["ID", "Öğr.No", "Ad Soyad", "Sınıf"])
        self.table_ogrenciler.setColumnHidden(0, True)
        self.table_ogrenciler.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        left_layout.addWidget(self.table_ogrenciler)

        right_panel = QFrame()
        right_panel.setStyleSheet(f"background-color:{CARD}; border-radius:8px; padding:10px;")
        right_layout = QVBoxLayout(right_panel)
        right_layout.addWidget(QLabel("Aldığı Dersler"))

        self.table_dersler = QTableWidget()
        self.table_dersler.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table_dersler.setColumnCount(5)
        self.table_dersler.setHorizontalHeaderLabels(["Kod", "Ad", "Sınıf", "Tip", "Öğr. Üyesi"])
        self.table_dersler.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        right_layout.addWidget(self.table_dersler)

        body_layout.addWidget(left_panel, stretch=1)
        body_layout.addWidget(right_panel, stretch=2)
        main_layout.addLayout(body_layout)

  
    def connect_signals(self):
        self.btn_search.clicked.connect(self._search)
        self.ent_q.returnPressed.connect(self._search)
        self.table_ogrenciler.itemSelectionChanged.connect(self._on_select_ogrenci)

    def _current_bolum_id(self):
        if not self.is_admin:
            return self.fixed_bolum_id
        return self.cmb_bolum.currentData()


    def _search(self):
        """Öğrenci listesini doldurur (rol bazlı)."""
        if self.is_admin:
            bid = self.cmb_bolum.currentData()
            if not bid:
                QMessageBox.warning(self, "Bölüm", "Bölüm seçiniz.")
                return
        else:
            bid = self.fixed_bolum_id

        q_text = self.ent_q.text().strip()
        like = f"%{q_text}%"

        try:
            with get_conn() as conn:
                cur = conn.cursor()
                if q_text:
                    sql = """
                        SELECT o.id, o.kod, o.ad, o.sinif_yili
                        FROM ogrenciler o
                        WHERE o.bolum_id=? AND (o.kod LIKE ? OR o.ad LIKE ?)
                        ORDER BY o.ad, o.kod
                    """
                    params = (bid, like, like)
                else:
                    sql = """
                        SELECT o.id, o.kod, o.ad, o.sinif_yili
                        FROM ogrenciler o
                        WHERE o.bolum_id=?
                        ORDER BY o.ad, o.kod
                    """
                    params = (bid,)

                cur.execute(q(sql), params)
                rows = cur.fetchall()

            self.table_ogrenciler.setRowCount(0)
            self.table_dersler.setRowCount(0)
            self.table_ogrenciler.setRowCount(len(rows))

            for row_idx, (rid, no, name, year) in enumerate(rows):
                item_id = QTableWidgetItem(str(rid))
                item_id.setData(Qt.UserRole, rid)
                self.table_ogrenciler.setItem(row_idx, 0, item_id)
                self.table_ogrenciler.setItem(row_idx, 1, QTableWidgetItem(no))
                self.table_ogrenciler.setItem(row_idx, 2, QTableWidgetItem(name))
                self.table_ogrenciler.setItem(row_idx, 3, QTableWidgetItem(str(year)))

                bg_color = ALT_BG_1 if row_idx % 2 == 0 else ALT_BG_2
                for col_idx in range(1, 4):
                    self.table_ogrenciler.item(row_idx, col_idx).setBackground(bg_color)

        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Öğrenciler aranırken hata oluştu:\n{e}")

    
    def _on_select_ogrenci(self):
        """Bir öğrenciye tıklandığında aldığı dersleri göster."""
        selected_rows = self.table_ogrenciler.selectedItems()
        if not selected_rows:
            return

        ogr_id_item = self.table_ogrenciler.item(selected_rows[0].row(), 0)
        if not ogr_id_item:
            return

        ogr_id = ogr_id_item.data(Qt.UserRole)
        if not ogr_id:
            return

        try:
            with get_conn() as conn:
                cur = conn.cursor()

               
                if not self.is_admin:
                    cur.execute("SELECT bolum_id FROM ogrenciler WHERE id=?", (ogr_id,))
                    row = cur.fetchone()
                    if not row or row[0] != self.fixed_bolum_id:
                        QMessageBox.warning(self, "Yetki", "Bu öğrenciye erişim izniniz yok.")
                        return

                cur.execute(q("""
                    SELECT d.kod, d.ad, d.sinif_yili,
                        CASE WHEN d.secmeli=1 THEN 'S' ELSE 'Z' END AS tip,
                        d.ogretim_uyesi
                    FROM kayitlar k
                    JOIN dersler d ON d.id = k.ders_id
                    WHERE k.ogrenci_id = ?
                    ORDER BY d.kod
                """), (ogr_id,))
                rows = cur.fetchall()

            self.table_dersler.setRowCount(0)
            self.table_dersler.setRowCount(len(rows))

            for row_idx, (kod, ad, sy, tip, hoca) in enumerate(rows):
                self.table_dersler.setItem(row_idx, 0, QTableWidgetItem(kod))
                self.table_dersler.setItem(row_idx, 1, QTableWidgetItem(ad))
                self.table_dersler.setItem(row_idx, 2, QTableWidgetItem(str(sy)))
                self.table_dersler.setItem(row_idx, 3, QTableWidgetItem(tip))
                self.table_dersler.setItem(row_idx, 4, QTableWidgetItem(hoca))

                bg_color = ALT_BG_1 if row_idx % 2 == 0 else ALT_BG_2
                for col_idx in range(5):
                    self.table_dersler.item(row_idx, col_idx).setBackground(bg_color)

        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Öğrencinin dersleri yüklenirken hata: {e}")
