# ui/rooms.py 
import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QLineEdit,
    QPushButton, QMessageBox, QComboBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QGraphicsView, QGraphicsScene, QGraphicsRectItem, QSpinBox, QFrame
)
from PySide6.QtGui import QFont, QColor, QPen
from PySide6.QtCore import Qt, Signal


try:
    from core.db import get_conn, q
    from core import session as core_session
except ImportError:
    print("⚠️ core modülleri yüklenemedi.")
    get_conn = None
    core_session = None


NAVY = "#0f2535"
CARD = "#112b3d"
TEXT = "#e6edf5"
SUBTEXT = "#bcd0d6"
GREEN = "#2e7d32"


def _map_schema():
    """Veritabanı sütun isimlerini belirler."""
    try:
        with get_conn() as conn:
            cur = conn.cursor()
            cur.execute("PRAGMA table_info(derslikler)")
            cols = {row[1] for row in cur.fetchall()}
    except Exception:
        cols = {"satir", "sutun", "sira_grup"}

    row_col = "satir" if "satir" in cols else "boyuna"
    col_col = "sutun" if "sutun" in cols else "enine"
    grp_col = "sira_grup" if "sira_grup" in cols else "sira_yapisi"
    return row_col, col_col, grp_col, [str(v) for v in (2, 3, 4)]


def _fetch_bolumler_map():
    """{id: 'Bölüm Adı'} döner"""
    try:
        with get_conn() as conn:
            cur = conn.cursor()
            cur.execute("SELECT id, ad FROM bolumler ORDER BY ad")
            return {r[0]: r[1] for r in cur.fetchall()}
    except Exception as e:
        print(f"Bölümler çekilemedi: {e}")
        return {}


class RoomsTab(QWidget):
    """Derslik Yönetimi sekmesi"""
    derslikler_kaydedildi = Signal()

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.selected_derslik_id = None

        if not core_session or not core_session.current_user:
            layout = QVBoxLayout(self)
            layout.addWidget(QLabel("❌ Oturum hatası. Lütfen tekrar giriş yapın."))
            return 

        self.is_admin = core_session.current_user.rol == "admin"
        self.fixed_bolum_id = None if self.is_admin else core_session.current_user.bolum_id

        #
        self.col_row, self.col_col, self.col_grp, self.grp_values = _map_schema()
        self.bolumler_map = _fetch_bolumler_map()

       
        self._init_ui()
        self._connect_signals()
        try:
            self._load_all()
        except Exception:
            pass


    def _init_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(20)

       
        left = QFrame()
        left.setStyleSheet(f"background-color: {CARD}; border-radius: 8px;")
        left.setFixedWidth(420)
        left_layout = QVBoxLayout(left)

        form = QFormLayout()
        form.setContentsMargins(10, 10, 10, 10)
        form.setSpacing(10)

        self.combo_bolum = QComboBox()
        for bid, bad in self.bolumler_map.items():
            self.combo_bolum.addItem(f"{bid} - {bad}", bid)

        if self.is_admin:
            form.addRow("Bölüm:", self.combo_bolum)
        else:
            idx = self.combo_bolum.findData(self.fixed_bolum_id)
            if idx != -1:
                self.combo_bolum.setCurrentIndex(idx)
            self.combo_bolum.setEnabled(False)
            form.addRow("Bölüm:", self.combo_bolum)

        self.ent_kod = QLineEdit()
        self.ent_ad = QLineEdit()
        self.spin_kapasite = QSpinBox(minimum=1, maximum=500, value=1)
        self.spin_boyuna = QSpinBox(minimum=1, maximum=30, value=1)
        self.spin_enine = QSpinBox(minimum=1, maximum=30, value=1)
        self.combo_sira_yapisi = QComboBox()
        self.combo_sira_yapisi.addItems(self.grp_values)

        form.addRow("Derslik Kodu:", self.ent_kod)
        form.addRow("Derslik Adı:", self.ent_ad)
        form.addRow("Kapasite:", self.spin_kapasite)
        form.addRow("Satır (boyuna):", self.spin_boyuna)
        form.addRow("Sütun (enine):", self.spin_enine)
        form.addRow("Sıra Yapısı:", self.combo_sira_yapisi)

        left_layout.addLayout(form)

    
        btns = QHBoxLayout()
        self.btn_yeni = QPushButton("Yeni")
        self.btn_kaydet = QPushButton("Kaydet")
        self.btn_sil = QPushButton("Sil")
        for b, c in [
            (self.btn_yeni, "#183b57"),
            (self.btn_kaydet, "#2e7d32"),
            (self.btn_sil, "#c94a4a"),
        ]:
            b.setStyleSheet(f"background-color:{c}; color:white; font-weight:bold;")
            btns.addWidget(b)
        left_layout.addLayout(btns)

        
        lbl = QLabel("Oturma Düzeni Önizleme")
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setFont(QFont("Segoe UI", 11, QFont.Bold))
        left_layout.addWidget(lbl)

        self.scene = QGraphicsScene()
        self.view = QGraphicsView(self.scene)
        self.view.setMinimumHeight(220)
        left_layout.addWidget(self.view)
        main_layout.addWidget(left)

        
        right = QFrame()
        right.setStyleSheet(f"background-color:{CARD}; border-radius:8px;")
        right_layout = QVBoxLayout(right)

        
        form_search = QFormLayout()
        self.search_id = QLineEdit()
        self.search_q = QLineEdit()
        self.btn_search = QPushButton("Ara")
        self.btn_search.setStyleSheet("background-color:#183b57; font-weight:bold; color:white;")
        form_search.addRow("ID:", self.search_id)
        form_search.addRow("Kod/Ad:", self.search_q)
        form_search.addRow("", self.btn_search)
        right_layout.addLayout(form_search)

        
        self.table = QTableWidget()
        cols = ("id", "bolum", "kod", "ad", "kapasite", self.col_row, self.col_col, self.col_grp)
        self.table.setColumnCount(len(cols))
        self.table.setHorizontalHeaderLabels([c.capitalize() for c in cols])
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        right_layout.addWidget(self.table)
        main_layout.addWidget(right, 1)

    
    def _connect_signals(self):
        self.btn_search.clicked.connect(self._search)
        self.table.itemSelectionChanged.connect(self._on_select)
        self.btn_yeni.clicked.connect(self._clear)
        self.btn_kaydet.clicked.connect(self._save)
        self.btn_sil.clicked.connect(self._delete)
        self.spin_boyuna.valueChanged.connect(self._redraw)
        self.spin_enine.valueChanged.connect(self._redraw)
        self.combo_sira_yapisi.currentIndexChanged.connect(self._redraw)
        self.view.resizeEvent = lambda e: self._redraw()

   
    def _selected_bolum_id(self):
        return self.fixed_bolum_id if not self.is_admin else self.combo_bolum.currentData()

    def _validate(self):
        b_id = self._selected_bolum_id()
        if not b_id:
            return False, "Bölüm seçiniz."
        kod = self.ent_kod.text().strip()
        ad = self.ent_ad.text().strip()
        if not kod or not ad:
            return False, "Kod ve Ad boş olamaz."
        return True, (
            b_id,
            kod,
            ad,
            self.spin_kapasite.value(),
            self.spin_boyuna.value(),
            self.spin_enine.value(),
            int(self.combo_sira_yapisi.currentText()),
        )

    def _clear(self):
        self.selected_derslik_id = None
        self.table.clearSelection()
        if self.is_admin:
            self.combo_bolum.setCurrentIndex(0)
        self.ent_kod.clear()
        self.ent_ad.clear()
        self.spin_kapasite.setValue(1)
        self.spin_boyuna.setValue(1)
        self.spin_enine.setValue(1)
        self.combo_sira_yapisi.setCurrentIndex(0)
        self._redraw()

    def _save(self):
        ok, data = self._validate()
        if not ok:
            QMessageBox.warning(self, "Hata", data)
            return

        b_id, kod, ad, kapasite, boyuna, enine, sira = data
        try:
            with get_conn() as conn:
                cur = conn.cursor()
                if self.selected_derslik_id:
                    cur.execute(
                        q(f"""
                            UPDATE derslikler
                            SET bolum_id=?, kod=?, ad=?, kapasite=?,
                                {self.col_row}=?, {self.col_col}=?, {self.col_grp}=?
                            WHERE id=?
                        """),
                        (b_id, kod, ad, kapasite, boyuna, enine, sira, self.selected_derslik_id),
                    )
                else:
                    cur.execute(
                        q(f"""
                            INSERT INTO derslikler
                                (bolum_id, kod, ad, kapasite, {self.col_row}, {self.col_col}, {self.col_grp})
                            VALUES (?,?,?,?,?,?,?)
                        """),
                        (b_id, kod, ad, kapasite, boyuna, enine, sira),
                    )
                conn.commit()
            self._load_all()
            self._clear()
            self.derslikler_kaydedildi.emit()
        except Exception as e:
            QMessageBox.critical(self, "Kayıt Hatası", str(e))

    def _delete(self):
        if not self.selected_derslik_id:
            QMessageBox.warning(self, "Uyarı", "Lütfen tablodan bir satır seçiniz.")
            return
        if QMessageBox.question(self, "Sil", "Seçili derslik silinsin mi?",
                                QMessageBox.Yes | QMessageBox.No) == QMessageBox.No:
            return
        try:
            with get_conn() as conn:
                cur = conn.cursor()
                cur.execute("DELETE FROM derslikler WHERE id=?", (self.selected_derslik_id,))
                conn.commit()
            self._load_all()
            self._clear()
        except Exception as e:
            QMessageBox.critical(self, "Silme Hatası", str(e))

    def _on_select(self):
        items = self.table.selectedItems()
        if not items:
            return
        row = self.table.row(items[0])
        rid = int(self.table.item(row, 0).text())
        self.selected_derslik_id = rid
        self.ent_kod.setText(self.table.item(row, 2).text())
        self.ent_ad.setText(self.table.item(row, 3).text())
        self.spin_kapasite.setValue(int(self.table.item(row, 4).text()))
        self.spin_boyuna.setValue(int(self.table.item(row, 5).text()))
        self.spin_enine.setValue(int(self.table.item(row, 6).text()))
        sira_text = self.table.item(row, 7).text()
        idx = self.combo_sira_yapisi.findText(sira_text)
        if idx != -1:
            self.combo_sira_yapisi.setCurrentIndex(idx)
        self._redraw()

    def _load_all(self):
        where, params = ("", ())
        if not self.is_admin:
            where = "WHERE d.bolum_id = ?"
            params = (self.fixed_bolum_id,)
        with get_conn() as conn:
            cur = conn.cursor()
            sql = f"""
                SELECT d.id, b.ad, d.kod, d.ad, d.kapasite, 
                       d.{self.col_row}, d.{self.col_col}, d.{self.col_grp}
                FROM derslikler d
                JOIN bolumler b ON b.id = d.bolum_id
                {where}
                ORDER BY b.ad, d.kod
            """
            cur.execute(q(sql), params)
            rows = cur.fetchall()
        self._fill_table(rows)
        if rows and not self.is_admin:
            self.derslikler_kaydedildi.emit()

    def _search(self):
        sid = self.search_id.text().strip()
        query = self.search_q.text().strip()
        where, params = ("", [])
        if not self.is_admin:
            where = "WHERE d.bolum_id = ?"
            params.append(self.fixed_bolum_id)
        if sid:
            where += (" AND " if where else "WHERE ") + "d.id=?"
            params.append(sid)
        if query:
            where += (" AND " if where else "WHERE ") + "(d.kod LIKE ? OR d.ad LIKE ?)"
            params.extend([f"%{query}%", f"%{query}%"])
        with get_conn() as conn:
            cur = conn.cursor()
            sql = f"""
                SELECT d.id, b.ad, d.kod, d.ad, d.kapasite,
                       d.{self.col_row}, d.{self.col_col}, d.{self.col_grp}
                FROM derslikler d
                JOIN bolumler b ON b.id = d.bolum_id
                {where}
                ORDER BY b.ad, d.kod
            """
            cur.execute(q(sql), tuple(params))
            self._fill_table(cur.fetchall())

    def _fill_table(self, rows):
        self.table.setRowCount(len(rows))
        for r, data in enumerate(rows):
            for c, val in enumerate(data):
                self.table.setItem(r, c, QTableWidgetItem(str(val)))

    def _redraw(self):
        """Oturma düzeni çizimi"""
        self.scene.clear()
        boyuna = self.spin_boyuna.value()
        enine = self.spin_enine.value()
        sira = int(self.combo_sira_yapisi.currentText())
        if boyuna <= 0 or enine <= 0:
            return

        w, h = self.view.width() - 20, self.view.height() - 20
        if w <= 0 or h <= 0:
            return

        pad = 16
        cell_w = (w - 2 * pad) / enine
        cell_h = (h - 2 * pad) / boyuna

        pen = QPen(QColor("#cfd8dc"))
        brush = QColor(GREEN)
        brush.setAlphaF(0.35)

        for r in range(boyuna):
            for c in range(enine):
                x0 = pad + c * cell_w + 3
                y0 = pad + r * cell_h + 3
                rect = QGraphicsRectItem(x0, y0, cell_w - 6, cell_h - 6)
                rect.setPen(pen)
                rect.setBrush(brush)
                self.scene.addItem(rect)

        self.scene.setSceneRect(0, 0, w, h)
        self.view.fitInView(self.scene.sceneRect(), Qt.KeepAspectRatio)
