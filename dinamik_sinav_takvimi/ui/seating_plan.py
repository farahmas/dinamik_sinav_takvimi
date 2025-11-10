



# ui/seating_plan.py
import os
from pathlib import Path
from fpdf import FPDF
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QGraphicsView, QGraphicsScene,
    QFrame, QMessageBox, QSplitter, QDialog
)
from PySide6.QtGui import QFont, QColor, QPen
from PySide6.QtCore import Qt
from PySide6.QtPdfWidgets import QPdfView
from PySide6.QtPdf import QPdfDocument

from core.db import get_conn, q
from core.errors import ErrorCodes, format_error
from core.seating import build_seating_plan

from core.seating import _is_seat_visible
import core.session as session

from PySide6.QtPrintSupport import QPrinter
from PySide6.QtGui import QPainter

from PySide6.QtWidgets import QGraphicsScene
from PySide6.QtGui import QPen, QColor, QFont
from PySide6.QtCore import Qt
from PySide6.QtGui import QFontMetrics



class SeatingScene(QGraphicsScene):
    

    def __init__(self, room_name, rows, cols, group_type, seat_data):
        super().__init__()
        self.room_name = room_name
        self.rows = rows

        if group_type == 2:
            self.cols = 10
        elif group_type == 3:
            self.cols = 9
        elif group_type == 4:
            self.cols = 12
        else:
            self.cols = cols

        self.group_type = group_type
        self.seat_data = seat_data
        self.draw_scene()
            
    def draw_scene(self):
        
        self.clear()

      
        masa_h = 8
        sandalye_w, sandalye_h = 22, 22
        gap_y = 40
        koridor = 40
        start_x, start_y = 80, 100

        
        title = self.addText(f"{self.room_name}", QFont("Segoe UI", 12, QFont.Bold))
        title.setDefaultTextColor(Qt.white)
        title.setPos(start_x, start_y - 70)

        
        self.addRect(start_x - 40, start_y - 50, 520, 20,
                    QPen(QColor("#bcd0d6")), QColor("#2c3e50"))
        tahta_yazi = self.addText("TAHTA", QFont("Segoe UI", 9, QFont.Bold))
        tahta_yazi.setDefaultTextColor(Qt.white)
        tahta_yazi.setPos(start_x + 210, start_y - 47)

        if self.group_type == 2:
            blok_sayisi = 5
            sandalye_pattern = ["B", "Ö"]
        elif self.group_type == 3:
            blok_sayisi = 3
            sandalye_pattern = ["Ö", "B", "Ö"]
        elif self.group_type == 4:
            blok_sayisi = 3
            sandalye_pattern = ["Ö", "B", "B", "Ö"]
        else:
            blok_sayisi = 3
            sandalye_pattern = ["Ö", "B", "Ö"]

        for r in range(1, self.rows + 1):
            current_x = start_x
            masa_y = start_y + (r - 1) * (sandalye_h + gap_y)

            masa_genislik = (len(sandalye_pattern) * sandalye_w + (len(sandalye_pattern) - 1) * 2 + koridor) * blok_sayisi
            self.addRect(current_x - 20, masa_y - 10, masa_genislik, masa_h,
                        QPen(QColor("#7cd6ff")), QColor("#16344d"))

            visible_col = 0
            for b in range(blok_sayisi):
                for i, koltuk in enumerate(sandalye_pattern):
                    
                    if koltuk == "Ö":
                        visible_col += 1
                        ogr = self.seat_data.get((r, visible_col))
                    else:
                        ogr = None

                    x = current_x + i * (sandalye_w + 2)
                    y = masa_y + 5


                    if koltuk == "B":
                        color = QColor("#22384d")
                    elif ogr:
                        color = QColor("#4CAF50")
                    else:
                        color = QColor("#1b3b56")

                    rect = self.addRect(x, y, sandalye_w, sandalye_h,
                                        QPen(QColor("#bcd0d6")), QColor(color))

                    if ogr and koltuk == "Ö":
                        parts = ogr.split(" ", 1)
                        ad = parts[0]
                        soyad = parts[1] if len(parts) > 1 else ""

                        font = QFont("Segoe UI", 7, QFont.Bold)
                        fm = QFontMetrics(font)
                        text_height = fm.height()

                        name_block_height = text_height * 2 + 2
                        text_x = x + (sandalye_w - fm.horizontalAdvance(ad)) / 2
                        text_y = y + (sandalye_h - name_block_height) / 2

                        t1 = self.addText(ad, font)
                        t1.setDefaultTextColor(Qt.white)
                        t1.setPos(text_x, text_y)

                        text_x2 = x + (sandalye_w - fm.horizontalAdvance(soyad)) / 2
                        t2 = self.addText(soyad, font)
                        t2.setDefaultTextColor(Qt.white)
                        t2.setPos(text_x2, text_y + text_height)

                current_x += len(sandalye_pattern) * (sandalye_w + 2) + koridor



class SeatingPlan(QWidget):
    """💺 Ders Bazlı Oturma Planı — Görsel + PDF + Önizleme"""

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.selected_exam_id = None
        self.seats_by_room = {}

        self._build_ui()
        self._load_exams()

    def _build_ui(self):
        """Sade sınav listesi ekranı (artık oturma planı burada çizilmiyor)"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Başlık
        lbl_list = QLabel("🧾 Sınav Listesi")
        lbl_list.setStyleSheet("color:#7cd6ff; font-weight:bold; font-size:16px;")
        layout.addWidget(lbl_list)

        # Tablo (sınav listesi)
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Sınav Adı", "Tarih", "Saat", "Derslik"])
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self._select_exam)
        layout.addWidget(self.table)

        # Buton satırı
        btn_row = QHBoxLayout()
        self.btn_create = QPushButton("📋 Oturma Planı Oluştur")
        self.btn_create.setStyleSheet(
            "background-color:#2e7d32; color:white; font-weight:bold; padding:8px 12px; border-radius:8px;"
        )
        btn_row.addStretch()
        btn_row.addWidget(self.btn_create)
        layout.addLayout(btn_row)

        # Bağlantı
        self.btn_create.clicked.connect(self._create_plan)



    def _load_exams(self):
        """Veritabanından sınav listesini yükler (bölüme göre filtrelenmiş)."""
        self.table.setRowCount(0)

        if not session.current_user:
            QMessageBox.warning(self, "Oturum", "Lütfen tekrar giriş yapın.")
            return

        try:
            with get_conn() as cn:
                cur = cn.cursor()

                sql = """
                    SELECT s.id, d.ad, z.gun, z.baslama_saat, 
                        IFNULL(GROUP_CONCAT(dl.ad, ', '), 'Derslik atanmadı')
                    FROM sinavlar s
                    JOIN dersler d ON d.id = s.ders_id
                    JOIN sinav_zamanlari z ON z.id = s.zaman_id
                    LEFT JOIN sinav_derslikleri sd ON sd.sinav_id = s.id
                    LEFT JOIN derslikler dl ON dl.id = sd.derslik_id
                """

                if session.current_user.rol != "admin":
                    sql += f" WHERE d.bolum_id = {session.current_user.bolum_id}"

                sql += " GROUP BY s.id ORDER BY z.gun, z.baslama_saat"

                cur.execute(q(sql))
                results = cur.fetchall()

                for r, row in enumerate(results):
                    self.table.insertRow(r)
                    for c, val in enumerate(row[1:]):
                        self.table.setItem(r, c, QTableWidgetItem(str(val or "")))
                    self.table.item(r, 0).setData(Qt.UserRole, row[0])

        except Exception as e:
            QMessageBox.critical(self, "Hata", format_error(ErrorCodes.OTURMA, str(e)))

    def reload_data(self):
        """Reload the latest exam list from the database."""
        try:
            print("🔄 Oturma planı yeniden yükleniyor...")
            self._load_exams()
            print("✅ Oturma planı listesi yenilendi.")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Oturma planı yenilenemedi:\n{e}")

    
    def _load_students_table(self):
        self.table_students.setRowCount(0)
        if not self.selected_exam_id:
            return
        try:
            with get_conn() as cn:
                cur = cn.cursor()
                cur.execute(q("""
                    SELECT o.kod, o.ad, d.ad, ok.r, ok.c
                    FROM oturma_koltuklari ok
                    JOIN ogrenciler o ON o.id = ok.ogrenci_id
                    JOIN sinav_derslikleri sd ON sd.id = ok.sinav_derslik_id
                    JOIN derslikler d ON d.id = sd.derslik_id
                    WHERE sd.sinav_id = ?
                    ORDER BY d.ad, ok.r, ok.c
                """), (self.selected_exam_id,))
                rows = cur.fetchall()

           
            self.table_students.setColumnCount(5)
            self.table_students.setHorizontalHeaderLabels(["Öğrenci No", "Ad Soyad", "Derslik", "Sıra", "Sütun"])

            self.table_students.setRowCount(len(rows))
            for r, (ogr_no, ogr_ad, derslik_ad, row_val, col_val) in enumerate(rows):
                self.table_students.setItem(r, 0, QTableWidgetItem(str(ogr_no)))
                self.table_students.setItem(r, 1, QTableWidgetItem(ogr_ad))
                self.table_students.setItem(r, 2, QTableWidgetItem(derslik_ad))
                self.table_students.setItem(r, 3, QTableWidgetItem(str(row_val)))
                self.table_students.setItem(r, 4, QTableWidgetItem(str(col_val)))

        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Öğrenciler yüklenemedi:\n{e}")

    
    def _draw_plan(self):
        """Seçilen sınava ait oturma planı verisini hazırlar (çizim yok — sadece veri hazırlığı)."""
        if not self.selected_exam_id:
            return
        try:
            self.seats_by_room.clear()

            with get_conn() as cn:
                cur = cn.cursor()

                cur.execute(q("""
                    SELECT d.ad, d.satir, d.sutun, d.sira_grup
                    FROM sinav_derslikleri sd
                    JOIN derslikler d ON d.id = sd.derslik_id
                    WHERE sd.sinav_id = ?
                """), (self.selected_exam_id,))
                derslik_yapilari = cur.fetchall()

                cur.execute(q("""
                    SELECT d.ad, ok.r, ok.c, o.ad
                    FROM oturma_koltuklari ok
                    JOIN ogrenciler o ON o.id = ok.ogrenci_id
                    JOIN sinav_derslikleri sd ON sd.id = ok.sinav_derslik_id
                    JOIN derslikler d ON d.id = sd.derslik_id
                    WHERE sd.sinav_id = ?
                """), (self.selected_exam_id,))
                rows = cur.fetchall()

            for derslik, satir, sutun, grup in derslik_yapilari:
                self.seats_by_room.setdefault(derslik, {
                    "satir": satir,
                    "sutun": sutun,
                    "grup": grup,
                    "seats": {}
                })

            for derslik, r, c, ad in rows:
                if derslik in self.seats_by_room:
                    self.seats_by_room[derslik]["seats"][(r, c)] = ad

            if not self.seats_by_room:
                QMessageBox.information(self, "Bilgi", "Bu sınava ait oturma verisi bulunamadı.")
                return

            return self.seats_by_room

        except Exception as e:
            QMessageBox.critical(self, "Çizim Hatası", f"Oturma planı verisi hazırlanamadı:\n{e}")
            return None


    
    def _select_exam(self):
        """Tabloda bir sınav seçildiğinde o sınavın ID’sini kaydeder."""
        items = self.table.selectedItems()
        if not items:
            self.selected_exam_id = None
            return

        self.selected_exam_id = items[0].data(Qt.UserRole)

        print(f"Seçilen sınav ID: {self.selected_exam_id}")


    

    def _create_plan(self):
        """Sınavın oturma planını oluşturur ve tam ekran oturma düzeni penceresini açar."""
        if not self.selected_exam_id:
            QMessageBox.warning(self, "Uyarı", "Lütfen bir sınav seçiniz.")
            return

        try:
            msg = build_seating_plan(self.selected_exam_id)

            if "❌" in msg:
                QMessageBox.warning(self, "Uyarı", msg)
                return  
            else:
                QMessageBox.information(self, "Bilgi", msg)

            seats_data = self._draw_plan()
            if not seats_data:
                QMessageBox.warning(self, "Uyarı", "Oturma planı verisi bulunamadı.")
                return

            from ui.seating_plan import SeatingViewDialog

            dialog = SeatingViewDialog(
                self.selected_exam_id,
                self.table.item(self.table.currentRow(), 0).text()
            )
            dialog.exec()

        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Oturma planı oluşturulamadı:\n{e}")


class SeatingViewDialog(QDialog):
    """Tam ekran oturma düzeni sayfası (her sınav için ayrı açılır)"""

    def __init__(self, exam_id, exam_name):
        super().__init__()
        self.exam_id = exam_id
        self.exam_name = exam_name
        self.seats_by_room = {}
        self.scene = QGraphicsScene()

        self.setWindowTitle(f"Oturma Planı — {exam_name}")
        self.resize(1200, 800)
        self.setStyleSheet("background-color:#0f1c2b; color:white;")

        self._build_ui()
        self._load_data()
        self._draw_first_room()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        header = QHBoxLayout()
        title = QLabel(f"📘 {self.exam_name}")
        title.setStyleSheet("font-size:18px; font-weight:bold; color:#7cd6ff;")
        header.addWidget(title)

        header.addStretch()

        self.btn_back = QPushButton("⬅️ Geri")
        self.btn_back.setStyleSheet("background-color:#183b57; color:white; padding:6px; border-radius:6px;")
        self.btn_back.clicked.connect(self.close)
        header.addWidget(self.btn_back)

        self.btn_pdf = QPushButton("📄 PDF Kaydet")
        self.btn_pdf.setStyleSheet("background-color:#2e7d32; color:white; padding:6px; border-radius:6px;")
        self.btn_pdf.clicked.connect(self._export_pdf)
        header.addWidget(self.btn_pdf)

        layout.addLayout(header)

        lbl_rooms = QLabel("🏫 Derslikler:")
        lbl_rooms.setStyleSheet("font-weight:bold; color:#7cd6ff; margin-top:5px;")
        layout.addWidget(lbl_rooms)

        self.room_buttons_layout = QHBoxLayout()
        layout.addLayout(self.room_buttons_layout)

        self.view = QGraphicsView()
        self.view.setScene(self.scene)
        self.view.setStyleSheet("""
            background-color:#0f1c2b;
            border:1px solid #1b3b56;
            border-radius:8px;
        """)
        layout.addWidget(self.view, stretch=1)


    def _load_data(self):
        
        from core.db import get_conn, q
        self.seats_by_room.clear()

        try:
            with get_conn() as cn:
                cur = cn.cursor()

                cur.execute(q("""
                    SELECT d.ad, d.satir, d.sutun, d.sira_grup
                    FROM sinav_derslikleri sd
                    JOIN derslikler d ON d.id = sd.derslik_id
                    WHERE sd.sinav_id = ?
                """), (self.exam_id,))
                derslikler = cur.fetchall()

                
                cur.execute(q("""
                    SELECT d.ad, ok.r, ok.c, o.ad
                    FROM oturma_koltuklari ok
                    JOIN ogrenciler o ON o.id = ok.ogrenci_id
                    JOIN sinav_derslikleri sd ON sd.id = ok.sinav_derslik_id
                    JOIN derslikler d ON d.id = sd.derslik_id
                    WHERE sd.sinav_id = ?
                """), (self.exam_id,))
                rows = cur.fetchall()

            
            for derslik, satir, sutun, grup in derslikler:
                self.seats_by_room.setdefault(derslik, {
                    "satir": satir,
                    "sutun": sutun,
                    "grup": grup,
                    "seats": {}
                })

            for derslik, r, c, ad in rows:
                if derslik in self.seats_by_room:
                    self.seats_by_room[derslik]["seats"][(r, c)] = ad

            
            while self.room_buttons_layout.count():
                item = self.room_buttons_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()

           
            for room_name in self.seats_by_room.keys():
                btn = QPushButton(room_name)
                btn.setCursor(Qt.PointingHandCursor)
                btn.setStyleSheet("""
                    QPushButton {
                        background-color:#183b57;
                        color:white;
                        padding:8px 12px;
                        border-radius:6px;
                        font-weight:bold;
                    }
                    QPushButton:hover {
                        background-color:#225c7a;
                    }
                    QPushButton:pressed {
                        background-color:#163d55;
                    }
                """)
                btn.clicked.connect(self._make_room_callback(room_name))

                self.room_buttons_layout.addWidget(btn)

        except Exception as e:
            QMessageBox.critical(self, "Veri Hatası", f"Oturma verileri yüklenemedi:\n{e}")

    def _make_room_callback(self, room_name):
        
        return lambda _: self._draw_room(room_name)
        


    def _draw_first_room(self):
        """Varsayılan olarak ilk sınıfı çizer."""
        if not self.seats_by_room:
            QMessageBox.information(self, "Bilgi", "Bu sınav için tanımlı derslik bulunamadı.")
            return
        first_room = next(iter(self.seats_by_room))
        self._draw_room(first_room)


    def _draw_room(self, room_name):
        try:
            if room_name not in self.seats_by_room:
                QMessageBox.warning(self, "Uyarı", f"{room_name} için veri bulunamadı.")
                return

            data = self.seats_by_room[room_name]
            satir, sutun, grup, seats = data["satir"], data["sutun"], data["grup"], data["seats"]

            self.scene.clear()
            scene = SeatingScene(room_name, satir, sutun, grup, seats)
            self.view.setScene(scene)
            self.scene = scene
            self.view.fitInView(self.scene.sceneRect(), Qt.KeepAspectRatio)
            self.view.setRenderHint(QPainter.Antialiasing, True)
            self.view.setRenderHint(QPainter.TextAntialiasing, True)
        except Exception as e:
            QMessageBox.critical(self, "Çizim Hatası", str(e))



    def _export_pdf(self):
        """PDF çıktısı al"""
        try:
            from core.pdf_export import export_scene_to_pdf
            os.makedirs("data/oturma_planlari", exist_ok=True)
            path = f"data/oturma_planlari/oturma_plan_{self.exam_id}.pdf"
            export_scene_to_pdf(self.scene, path)
            QMessageBox.information(self, "PDF", f"✅ PDF kaydedildi:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "PDF Hata", str(e))



