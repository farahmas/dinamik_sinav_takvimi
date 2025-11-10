# ui/schedule_wizard.py 
import os
from datetime import datetime, timedelta
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QTextEdit, QListWidget, QListWidgetItem, QCheckBox, QMessageBox,
    QFrame, QScrollArea, QComboBox, QCalendarWidget
)
from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QFont, QColor, QPalette
from core.schedule import build_exam_schedule
from core.db import get_conn
from PySide6.QtGui import QTextCharFormat
from core import session as core_session


class ScheduleWizard(QWidget):
    """🎓 Modern 2-column Exam Scheduling Page"""

    def __init__(self, app=None, role="koord"):
        super().__init__()
        self.app = app
        self.role = role
        self.selected_courses = []
        self.exception_durations = {}
        self._build_ui()
        self._load_courses()

    
    def _build_ui(self):
        self.setStyleSheet("""
            QWidget {
                background-color: #0f1c2b;
                color: #e6edf5;
                font-family: 'Segoe UI';
                font-size: 13px;
            }
            QLineEdit, QComboBox {
                background-color: #112b3d;
                border: 1px solid #1b3b56;
                border-radius: 6px;
                padding: 6px;
                color: white;
            }
            QPushButton {
                border-radius: 6px;
                font-weight: bold;
                padding: 8px 10px;
            }
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(Qt.AlignTop)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        title = QLabel("📘 Sınav Programı Oluşturma")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("Segoe UI", 18, QFont.Bold))
        title.setStyleSheet("color: white; margin-bottom: 10px;")
        main_layout.addWidget(title)

        
        content = QHBoxLayout()
        content.setSpacing(20)
        main_layout.addLayout(content)

        
        left_col = QVBoxLayout()
        left_col.addWidget(self._make_card("🧾 Ders Seçimi", self._build_course_section()))
        left_col.addWidget(self._make_card("📅 Tarih ve Tatil Günleri", self._build_date_section()))
        content.addLayout(left_col)

      
        right_col = QVBoxLayout()
        right_col.addWidget(self._make_card("⚙️ Sınav Kısıtları", self._build_param_section()))
        right_col.addWidget(self._make_card("🚀 Program Oluşturma", self._build_result_section()))
        content.addLayout(right_col)

    def _make_card(self, title, widget):
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame {
                background-color: #14273f;
                border-radius: 12px;
                border: 1px solid #1e3a5f;
            }
        """)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)
        lbl = QLabel(title)
        lbl.setStyleSheet("font-weight: bold; color: #7cd6ff; font-size: 14px;")
        layout.addWidget(lbl)
        layout.addWidget(widget)
        return frame

    def _build_course_section(self):
        frame = QFrame()
        layout = QVBoxLayout(frame)
        self.course_list = QListWidget()
        self.course_list.setSelectionMode(QListWidget.MultiSelection)
        self.course_list.setStyleSheet("""
            QListWidget {
                background-color: #112b3d;
                border: 1px solid #1b3b56;
                border-radius: 8px;
            }
        """)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.course_list)
        layout.addWidget(scroll, stretch=1)

        btn_toggle = QPushButton("🔁 Tümünü Seç / Kaldır")
        btn_toggle.setStyleSheet("background-color: #183b57; color: white;")
        btn_toggle.clicked.connect(self._toggle_all)
        layout.addWidget(btn_toggle, alignment=Qt.AlignRight)
        return frame

    def _build_date_section(self):
        frame = QFrame()
        layout = QVBoxLayout(frame)

        layout.addWidget(QLabel("Başlangıç Tarihi:"))
        self.calendar_start = QCalendarWidget()
        self.calendar_start.setStyleSheet(self._calendar_style())
        layout.addWidget(self.calendar_start)

        layout.addWidget(QLabel("Bitiş Tarihi:"))
        self.calendar_end = QCalendarWidget()
        self.calendar_end.setStyleSheet(self._calendar_style())
        layout.addWidget(self.calendar_end)

        layout.addWidget(QLabel("Tatil Günleri (virgülle ayırın):"))
        self.input_holidays = QLineEdit()
        self.input_holidays.setPlaceholderText("örn: 2025-11-01, 01.11.2025 veya 1/11/2025")
        self.input_holidays.setToolTip("Tarihleri YYYY-MM-DD, DD.MM.YYYY veya DD/MM/YYYY biçiminde girebilirsiniz.")
        layout.addWidget(self.input_holidays)

        self._set_default_calendar_dates()
        return frame

    def _calendar_style(self):
        return """
            QCalendarWidget QWidget {
                alternate-background-color: #0f1c2b;
                color: #e6edf5;
            }
            QCalendarWidget QAbstractItemView:enabled {
                background-color: #112b3d;
                color: white;
                selection-background-color: #2e7d32;
                selection-color: white;
                border-radius: 6px;
            }
        """

    def _set_default_calendar_dates(self):
        """Set default date range starting from next Monday and disable weekends."""
        today = datetime.now().date()
        days_until_monday = (7 - today.weekday()) % 7 or 7
        next_monday = today + timedelta(days=days_until_monday)
        end_date = next_monday + timedelta(days=10)

        self.calendar_start.setSelectedDate(next_monday)
        self.calendar_end.setSelectedDate(end_date)

       
        self._disable_weekends(self.calendar_start)
        self._disable_weekends(self.calendar_end)
        
        def _is_weekend(qdate):
            return qdate.dayOfWeek() in (6, 7) 

        self.calendar_start.selectionChanged.connect(
            lambda: self.calendar_start.setSelectedDate(
                self.calendar_start.selectedDate()
                if not _is_weekend(self.calendar_start.selectedDate())
                else self.calendar_start.selectedDate().addDays(1)
            )
        )

        self.calendar_end.selectionChanged.connect(
            lambda: self.calendar_end.setSelectedDate(
                self.calendar_end.selectedDate()
                if not _is_weekend(self.calendar_end.selectedDate())
                else self.calendar_end.selectedDate().addDays(1)
            )
        )


    def _disable_weekends(self, calendar):
        """Visually disable weekends (Sat/Sun) on a QCalendarWidget."""
        fmt = QTextCharFormat()
        fmt.setForeground(QColor("#555a70"))  
        fmt.setBackground(QColor("#182233"))  

        year = datetime.now().year
        for month in range(1, 13):
            for day in range(1, 32):
                try:
                    date = datetime(year, month, day)
                    if date.weekday() in (5, 6): 
                        qdate = calendar.minimumDate().addDays(
                            (date - calendar.minimumDate().toPython()).days
                        )
                        calendar.setDateTextFormat(qdate, fmt)
                except ValueError:
                    continue
    
    def _build_param_section(self):
        frame = QFrame()
        layout = QVBoxLayout(frame)
        self.combo_exam_type = QComboBox()
        self.combo_exam_type.addItems(["Vize", "Final", "Bütünleme"])
        self.input_duration = QLineEdit("75")
        self.input_exceptions = QLineEdit()
        self.input_break = QLineEdit("15")
        self.chk_no_overlap = QCheckBox("Sınavlar aynı zamana denk gelmesin")
        self.chk_no_overlap.setChecked(True)

        layout.addWidget(QLabel("Sınav Türü:"))
        layout.addWidget(self.combo_exam_type)
        layout.addWidget(QLabel("Varsayılan Süre (dk):"))
        layout.addWidget(self.input_duration)
        layout.addWidget(QLabel("İstisna Süreler (örn: CSE101=90,BLM105=60):"))
        layout.addWidget(self.input_exceptions)
        layout.addWidget(QLabel("Bekleme Süresi (dk):"))
        layout.addWidget(self.input_break)
        layout.addWidget(self.chk_no_overlap)
        return frame

    def _build_result_section(self):
        frame = QFrame()
        layout = QVBoxLayout(frame)
        btn_row = QHBoxLayout()

        btn_run = QPushButton("📅 Programı Oluştur")
        btn_run.setStyleSheet("background-color: #2e7d32; color: white;")
        btn_run.clicked.connect(self._run_scheduler)

        btn_excel = QPushButton("📂 Excel Klasörünü Aç")
        btn_excel.setStyleSheet("background-color: #183b57; color: white;")
        btn_excel.clicked.connect(lambda: os.startfile("data"))

        btn_row.addWidget(btn_run)
        btn_row.addWidget(btn_excel)
        layout.addLayout(btn_row)

        self.result_box = QTextEdit()
        self.result_box.setReadOnly(True)
        self.result_box.setMinimumHeight(180)
        self.result_box.setStyleSheet("background-color: #0d1117; border-radius: 8px; padding: 8px;")
        layout.addWidget(self.result_box)
        return frame

    def _toggle_all(self):
        total = self.course_list.count()
        selected = len(self.course_list.selectedItems())
        for i in range(total):
            self.course_list.item(i).setSelected(selected < total)

    def _load_courses(self):
        """Load only department courses for coordinators, all for admin."""
        self.course_list.clear()
        try:
            user = getattr(core_session, "current_user", None)
            with get_conn() as cn:
                cur = cn.cursor()

                if user and user.rol == "koordinator":
                    cur.execute("""
                        SELECT id, kod, ad
                        FROM dersler
                        WHERE bolum_id = ?
                        ORDER BY kod
                    """, (user.bolum_id,))
                else:
                    cur.execute("SELECT id, kod, ad FROM dersler ORDER BY kod")

                rows = cur.fetchall()
                if not rows:
                    self.course_list.addItem(QListWidgetItem("⚠️ Hiç ders bulunamadı."))
                    return

                for cid, kod, ad in rows:
                    self.course_list.addItem(QListWidgetItem(f"{cid} - {kod} - {ad}"))

        except Exception as e:
            self.course_list.addItem(QListWidgetItem(f"[Hata] Dersler yüklenemedi: {e}"))

    
    def _run_scheduler(self):
        try:
            start_date = self.calendar_start.selectedDate().toPython()
            end_date = self.calendar_end.selectedDate().toPython()

            if end_date < start_date:
                QMessageBox.critical(self, "Hata", "Bitiş tarihi başlangıçtan önce olamaz.")
                return

            holidays = [h.strip() for h in self.input_holidays.text().split(",") if h.strip()]

            selected_ids = []
            for i in self.course_list.selectedItems():
                try:
                    selected_ids.append(int(i.text().split(" - ")[0]))
                except:
                    pass
            if not selected_ids:
                QMessageBox.warning(self, "Uyarı", "En az bir ders seçmelisiniz.")
                return

            default_duration = int(self.input_duration.text())
            exceptions = {}
            if self.input_exceptions.text().strip():
                for token in self.input_exceptions.text().split(","):
                    if "=" in token:
                        code, val = token.split("=")
                        exceptions[code.strip()] = int(val.strip())

           
            holidays = []
            for h in self.input_holidays.text().split(","):
                h = h.strip()
                if not h:
                    continue
                for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y"):
                    try:
                        parsed = datetime.strptime(h, fmt).date()
                        holidays.append(str(parsed))
                        break
                    except ValueError:
                        continue

           
            user = getattr(core_session, "current_user", None)
            if user and user.rol == "koordinator":
                with get_conn() as cn:
                    cur = cn.cursor()
                    for cid in selected_ids:
                        cur.execute("SELECT bolum_id FROM dersler WHERE id=?", (cid,))
                        row = cur.fetchone()
                        if not row or row[0] != user.bolum_id:
                            QMessageBox.warning(self, "Yetki Hatası", "Kendi bölümünüze ait olmayan bir dersi seçemezsiniz.")
                            return

            result = build_exam_schedule(
                exam_type=self.combo_exam_type.currentText().lower(),
                default_duration=default_duration,
                break_time=int(self.input_break.text()),
                avoid_overlap=self.chk_no_overlap.isChecked(),
                start_date=start_date,
                end_date=end_date,
                holidays=holidays,
                selected_courses=selected_ids,
                exception_durations=exceptions,
            )

            self._animate_result("success" if "✅" in result else "error")
            self.result_box.setText(result)
            QMessageBox.information(self, "Sonuç", result)

        except Exception as e:
            self._animate_result("error")
            self.result_box.setText(f"❌ Beklenmedik hata: {e}")
            QMessageBox.critical(self, "Hata", str(e))

   
    def _animate_result(self, mode="success"):
        color = QColor("#00ff80") if mode == "success" else QColor("#ff5555")
        anim = QPropertyAnimation(self.result_box, b"styleSheet")
        anim.setDuration(800)
        anim.setStartValue("background-color: #0d1117;")
        anim.setEndValue(f"background-color: {color.name()};")
        anim.setEasingCurve(QEasingCurve.OutQuad)
        anim.start()

    def reload_courses(self):
        """Reload course list from the database after Excel import."""
        print("🔁 ScheduleWizard: Reloading courses...")
        self._load_courses()

    def reload_rooms(self):
        """Reload classroom list to ensure up-to-date data."""
        try:
            with get_conn() as cn:
                cur = cn.cursor()
                cur.execute("SELECT COUNT(*) FROM derslikler")
                count = cur.fetchone()[0]
                print(f"🏫 Reloaded classrooms: {count} found.")
        except Exception as e:
            print(f"⚠️ Could not reload classrooms: {e}")


