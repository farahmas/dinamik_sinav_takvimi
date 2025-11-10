# ui/courses.py 
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
    print("⚠️ core modülleri yüklenemedi.")
    pass


NAVY = "#0f2535"
CARD = "#112b3d"
TEXT = "#e8f5e9"
SUBTEXT = "#bcd0d6"
ALT_BG_1 = QColor("#163754")
ALT_BG_2 = QColor("#193e5f")


def _fetch_bolumler_map():
    """Bölümleri {id: ad} ve {ad: id} olarak döner."""
    bolumler_by_id, bolumler_by_name = {}, {}
    try:
        with get_conn() as conn:
            cur = conn.cursor()
            cur.execute("SELECT id, ad FROM bolumler ORDER BY ad;")
            for bid, bad in cur.fetchall():
                bolumler_by_id[bid] = bad
                bolumler_by_name[bad] = bid
    except Exception as e:
        print(f"HATA (courses.py): Bölümler alınamadı -> {e}")
    return bolumler_by_id, bolumler_by_name


class CoursesTab(QWidget):
    """📘 Ders Listesi sekmesi (admin + koordinatör uyumlu, güvenlikli)"""
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app

        if not core_session.current_user:
            self.setLayout(QVBoxLayout())
            self.layout().addWidget(QLabel("⚠️ Oturum bulunamadı. Lütfen yeniden giriş yapın."))
            return

        self.user = core_session.current_user
        self.is_admin = (self.user.rol == "admin")
        self.fixed_bolum_id = None if self.is_admin else self.user.bolum_id

        self.bolumler_by_id, self.bolumler_by_name = _fetch_bolumler_map()

        self._init_ui()
        self._connect_signals()
        self._search()  

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        
        top_bar = QFrame()
        top_bar.setStyleSheet(f"background-color:{CARD}; border-radius:8px;")
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(10, 10, 10, 10)

        lbl_bolum = QLabel("Bölüm:")
        top_layout.addWidget(lbl_bolum)

        self.cmb_bolum = QComboBox()
        if self.is_admin:
            for bid, bad in self.bolumler_by_id.items():
                self.cmb_bolum.addItem(f"{bid} - {bad}", userData=bid)
        else:
            bolum_ad = self.bolumler_by_id.get(self.fixed_bolum_id, "Bilinmeyen Bölüm")
            self.cmb_bolum.addItem(f"{self.fixed_bolum_id} - {bolum_ad}", userData=self.fixed_bolum_id)
            self.cmb_bolum.setEnabled(False)
        top_layout.addWidget(self.cmb_bolum)

        lbl_search = QLabel("Ara (Kod/Ad):")
        top_layout.addWidget(lbl_search, alignment=Qt.AlignRight)
        self.ent_q = QLineEdit()
        self.ent_q.setPlaceholderText("Ders kodu veya adı...")
        top_layout.addWidget(self.ent_q)

        self.btn_search = QPushButton("Ara")
        self.btn_search.setStyleSheet(f"background-color:{NAVY}; color:white; font-weight:bold; padding:5px;")
        top_layout.addWidget(self.btn_search)
        main_layout.addWidget(top_bar)

       
        body_layout = QHBoxLayout()
        body_layout.setSpacing(20)

        
        left_panel = QFrame()
        left_panel.setStyleSheet(f"background-color:{CARD}; border-radius:8px; padding:10px;")
        left_layout = QVBoxLayout(left_panel)
        left_layout.addWidget(QLabel("📚 Ders Listesi"))

        self.table_dersler = QTableWidget()
        self.table_dersler.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table_dersler.setSelectionBehavior(QTableWidget.SelectRows)
        self.table_dersler.setSelectionMode(QTableWidget.SingleSelection)
        self.table_dersler.setColumnCount(4)
        self.table_dersler.setHorizontalHeaderLabels(["Kod", "Ad", "Tür", "Öğretim Üyesi"])
        self.table_dersler.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        left_layout.addWidget(self.table_dersler)

      
        right_panel = QFrame()
        right_panel.setStyleSheet(f"background-color:{CARD}; border-radius:8px; padding:10px;")
        right_layout = QVBoxLayout(right_panel)
        right_layout.addWidget(QLabel("👩‍🎓 Dersi Alan Öğrenciler"))

        self.table_ogrenciler = QTableWidget()
        self.table_ogrenciler.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table_ogrenciler.setColumnCount(3)
        self.table_ogrenciler.setHorizontalHeaderLabels(["Öğr.No", "Ad Soyad", "Sınıf"])
        self.table_ogrenciler.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        right_layout.addWidget(self.table_ogrenciler)

        body_layout.addWidget(left_panel, stretch=2)
        body_layout.addWidget(right_panel, stretch=1)
        main_layout.addLayout(body_layout)

   
    def _connect_signals(self):
        self.btn_search.clicked.connect(self._search)
        self.ent_q.returnPressed.connect(self._search)
        self.table_dersler.itemSelectionChanged.connect(self._on_select_ders)

    def _current_bolum_id(self):
        if not self.is_admin:
            return self.fixed_bolum_id
        return self.cmb_bolum.currentData()

   
    def _search(self):
        """Ders tablosunu günceller (rol bazlı filtreleme ile)."""
        if self.is_admin:
            bid = self.cmb_bolum.currentData()
            if not bid:
                QMessageBox.warning(self, "Uyarı", "Lütfen bir bölüm seçiniz.")
                return
        else:
            bid = self.fixed_bolum_id

        q_text = self.ent_q.text().strip()
        like = f"%{q_text}%"

        try:
            with get_conn() as conn:
                cur = conn.cursor()
                sql = """
                    SELECT id, kod, ad,
                           CASE WHEN secmeli=1 THEN 'Seçmeli' ELSE 'Zorunlu' END AS tur,
                           ogretim_uyesi
                    FROM dersler
                    WHERE bolum_id=? {cond}
                    ORDER BY kod
                """.format(cond="AND (kod LIKE ? OR ad LIKE ?)" if q_text else "")
                params = (bid, like, like) if q_text else (bid,)
                cur.execute(q(sql), params)
                rows = cur.fetchall()

            self.table_dersler.setRowCount(0)
            self.table_ogrenciler.setRowCount(0)
            self.table_dersler.setRowCount(len(rows))

            for i, (rid, kod, ad, tur, hoca) in enumerate(rows):
                item = QTableWidgetItem(kod)
                item.setData(Qt.UserRole, rid)
                self.table_dersler.setItem(i, 0, item)
                self.table_dersler.setItem(i, 1, QTableWidgetItem(ad))
                self.table_dersler.setItem(i, 2, QTableWidgetItem(tur))
                self.table_dersler.setItem(i, 3, QTableWidgetItem(hoca))
                bg = ALT_BG_1 if i % 2 == 0 else ALT_BG_2
                for j in range(4):
                    self.table_dersler.item(i, j).setBackground(bg)

        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Dersler yüklenirken hata oluştu:\n{e}")

    
    def _on_select_ders(self):
        selected = self.table_dersler.selectedItems()
        if not selected:
            return

        ders_id_item = self.table_dersler.item(selected[0].row(), 0)
        if not ders_id_item:
            return

        ders_id = ders_id_item.data(Qt.UserRole)
        if not ders_id:
            return

        try:
            with get_conn() as conn:
                cur = conn.cursor()

                
                if not self.is_admin:
                    cur.execute("SELECT bolum_id FROM dersler WHERE id=?", (ders_id,))
                    row = cur.fetchone()
                    if not row or row[0] != self.fixed_bolum_id:
                        QMessageBox.warning(self, "Yetki", "Bu derse erişim izniniz yok.")
                        return

                cur.execute(q("""
                    SELECT o.kod, o.ad, o.sinif_yili
                    FROM kayitlar k
                    JOIN ogrenciler o ON o.id = k.ogrenci_id
                    WHERE k.ders_id = ?
                    ORDER BY o.ad
                """), (ders_id,))
                rows = cur.fetchall()

            self.table_ogrenciler.setRowCount(0)
            self.table_ogrenciler.setRowCount(len(rows))

            for i, (no, ad, sy) in enumerate(rows):
                self.table_ogrenciler.setItem(i, 0, QTableWidgetItem(no))
                self.table_ogrenciler.setItem(i, 1, QTableWidgetItem(ad))
                self.table_ogrenciler.setItem(i, 2, QTableWidgetItem(str(sy)))
                bg = ALT_BG_1 if i % 2 == 0 else ALT_BG_2
                for j in range(3):
                    self.table_ogrenciler.item(i, j).setBackground(bg)

        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Öğrenciler yüklenirken hata oluştu:\n{e}")
