# ui/coord.py 
import sys
import os
import platform
import subprocess
from ui.schedule_wizard import ScheduleWizard
from ui.seating_plan import SeatingPlan as SeatingPlanTab
from core.session import logout

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QStackedWidget,
    QFrame, QMessageBox, QGridLayout, QDialog, QListWidget, QListWidgetItem
)
from PySide6.QtGui import QPixmap, QFont
from PySide6.QtCore import Qt, QTimer

SCRIPT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

try:
    from core.db import get_conn, q
    from core import session as core_session
except ImportError:
    print("⚠️ core modülleri yüklenemedi.")
    get_conn = None
    core_session = None

try:
    from ui.rooms import RoomsTab
except ImportError:
    RoomsTab = None

try:
    from ui.courses import CoursesTab
except ImportError:
    CoursesTab = None

try:
    from ui.import_courses import ImportCoursesTab
except ImportError:
    ImportCoursesTab = None

try:
    from ui.students import StudentsTab
except ImportError:
    StudentsTab = None

try:
    from ui.import_students import ImportStudentsTab
except ImportError:
    ImportStudentsTab = None


class CoordHome(QWidget):
    """Koordinatör ana ekranı (💺 Oturma Planı entegre, bölüm bazlı filtreli)"""
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.views = {}
        self.menu_buttons = {}
        self.active_btn = None
        self.data_dir = os.path.join(SCRIPT_ROOT, "data")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        sidebar = self._build_sidebar()
        main_content = self._build_main_content()

        layout.addWidget(sidebar)
        layout.addWidget(main_content)

        self._post_init_setup()

    
    def _build_sidebar(self):
        sidebar = QFrame()
        sidebar.setStyleSheet("background-color: #0f2535; border-right: 2px solid #1b3b56;")
        sidebar.setFixedWidth(240)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        
        logo_path = os.path.join(SCRIPT_ROOT, "assets", "kou.png")
        if os.path.exists(logo_path):
            logo = QLabel()
            pix = QPixmap(logo_path).scaled(90, 90, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            logo.setPixmap(pix)
            logo.setAlignment(Qt.AlignCenter)
            layout.addWidget(logo)

       
        title = QLabel("KOÜ Sınav Takvimi")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("color: white; font-weight: bold; font-size: 16px;")
        layout.addWidget(title)

        
        menu_items = [
            ("Gösterge Paneli", "dashboard", "📊"),
            ("Derslik Yönetimi", "rooms", "🏫"),
            ("Ders Listesi Yükle", "import_courses", "🗂️"),
            ("Öğrenci Listesi Yükle", "import_students", "🧾"),
            ("Ders Listesi", "courses", "📚"),
            ("Öğrenci Arama", "student", "🔎"),
            ("Sınav Programı", "schedule", "🗓️"),
            ("Oturma Planı", "seating_plan", "💺"), 
        ]

        style = """
            QPushButton {
                background-color: #183b57;
                color: white;
                text-align: left;
                border-radius: 6px;
                padding: 8px 10px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #1f4d73; }
            QPushButton:checked { background-color: #2e7d32; }
        """

        for text, key, emoji in menu_items:
            btn = QPushButton(f"{emoji}  {text}")
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(style)
            btn.setCheckable(True)
            btn.clicked.connect(lambda _, k=key, b=btn: self.switch_view(k, b))
            layout.addWidget(btn)
            self.menu_buttons[key] = btn

        layout.addStretch()
        return sidebar

   

    def _build_main_content(self):
        main = QFrame()
        main.setStyleSheet("background-color: #112b3d;")

        layout = QVBoxLayout(main)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        dept_name = self._get_dept_name_of_user()
        user_email = getattr(core_session.current_user, "eposta", "Koordinatör")
        top_bar = QLabel(f"Hoş geldin, {user_email}  (Bölüm: {dept_name})")
        top_bar.setAlignment(Qt.AlignRight)
        top_bar.setStyleSheet("color: white; font-size: 13px; font-weight: bold;")
        layout.addWidget(top_bar)

        self.stack = QStackedWidget()
        layout.addWidget(self.stack)
        self._create_views()

        
        footer = QFrame()
        f_layout = QHBoxLayout(footer)
        f_layout.setContentsMargins(0, 0, 0, 0)
        f_layout.setSpacing(8)

        btn_back = QPushButton("Login Ekranına Dön")
        btn_exit = QPushButton("Çıkış")

        base_style = """
            QPushButton {
                background-color: #183b57;
                color: white;
                padding: 6px 10px;
                border-radius: 6px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #1f4d73; }
        """
        btn_back.setStyleSheet(base_style)
        btn_exit.setStyleSheet("""
            QPushButton {
                background-color: #c94a4a;
                color: white;
                padding: 6px 10px;
                border-radius: 6px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #e06c6c; }
        """)
        btn_back.clicked.connect(self.go_login)
        btn_exit.clicked.connect(self.exit_app)

        f_layout.addStretch()
        f_layout.addWidget(btn_back)
        f_layout.addWidget(btn_exit)
        layout.addWidget(footer)
        return main

   
    def _create_views(self):
        self.views["dashboard"] = self._dashboard_view()
        self.stack.addWidget(self.views["dashboard"])

        if RoomsTab:
            self.views["rooms"] = RoomsTab(self.app)
            self.stack.addWidget(self.views["rooms"])
        if CoursesTab:
            self.views["courses"] = CoursesTab(self, self.app)
            self.stack.addWidget(self.views["courses"])
        if ImportCoursesTab:
            self.views["import_courses"] = ImportCoursesTab(self, self.app)
            self.stack.addWidget(self.views["import_courses"])
            self.views["import_courses"].data_imported.connect(self._refresh_data_views)
        if ImportStudentsTab:
            self.views["import_students"] = ImportStudentsTab(self, self.app)
            self.stack.addWidget(self.views["import_students"])
            self.views["import_students"].data_imported.connect(self._refresh_data_views)
        if StudentsTab:
            self.views["student"] = StudentsTab(self, self.app)
            self.stack.addWidget(self.views["student"])
        if "schedule" in self.views:
            self.views["import_courses"].data_imported.connect(self.views["schedule"].reload_courses)
        if "schedule" in self.views:
            self.views["rooms"].data_imported.connect(self.views["schedule"].reload_rooms)


        self.views["schedule"] = ScheduleWizard(self.app)
        self.stack.addWidget(self.views["schedule"])
        self.views["seating_plan"] = SeatingPlanTab(self.app)
        self.stack.addWidget(self.views["seating_plan"])

    
    def _dashboard_view(self):

        frame = QFrame()
        frame.setStyleSheet("background-color: #112b3d; border-radius: 10px;")
        layout = QGridLayout(frame)
        layout.setSpacing(20)
        layout.setContentsMargins(20, 20, 20, 20)

        self.lbl_dept = QLabel("0")
        self.lbl_users = QLabel("0")
        self.lbl_courses = QLabel("0")
        self.lbl_exams = QLabel("0")

        for lbl in [self.lbl_dept, self.lbl_users, self.lbl_courses, self.lbl_exams]:
            lbl.setStyleSheet("color: #2e7d32; font-size: 22pt; font-weight: bold;")
            lbl.setAlignment(Qt.AlignCenter)

        def make_card(icon, title, value_label: QLabel, detail_button=None):
            card = QFrame()
            card.setStyleSheet("""
                QFrame {
                    background-color: #15314b;
                    border-radius: 10px;
                    border: 1px solid #1b3b56;
                }
                QLabel { background-color: transparent; }
            """)
            grid = QGridLayout(card)
            grid.setContentsMargins(16, 16, 16, 16)
            grid.setSpacing(8)

            lbl_icon = QLabel(icon)
            lbl_icon.setFont(QFont("Segoe UI Emoji", 28))
            lbl_icon.setStyleSheet("color: white;")

            lbl_title = QLabel(title)
            lbl_title.setStyleSheet("color: #bcd0d6; font-weight: bold; font-size: 12pt;")

            btn_detail = detail_button or QPushButton("Detaya Git")
            btn_detail.setEnabled(bool(detail_button))
            btn_detail.setStyleSheet("""
                QPushButton {
                    background-color: #2e7d32;
                    color: white;
                    font-weight: bold;
                    border-radius: 6px;
                    padding: 6px 10px;
                }
                QPushButton:hover { background-color: #388e3c; }
                QPushButton:disabled { background-color: #183b57; color: #556677; }
            """)

            grid.addWidget(lbl_icon, 0, 0)
            grid.addWidget(lbl_title, 1, 0)
            grid.addWidget(value_label, 2, 0)
            grid.addWidget(btn_detail, 3, 0, Qt.AlignLeft)
            return card

        btn_excel = QPushButton("Detaya Git")
        btn_excel.setStyleSheet("""
            QPushButton {
                background-color: #2e7d32;
                color: white;
                font-weight: bold;
                border-radius: 6px;
                padding: 6px 10px;
            }
            QPushButton:hover { background-color: #388e3c; }
        """)
        btn_excel.clicked.connect(self._show_excel_files)

        layout.addWidget(make_card("🏫", "Bölümünüz", self.lbl_dept), 0, 0)
        layout.addWidget(make_card("👥", "Koordinatör Sayısı", self.lbl_users), 0, 1)
        layout.addWidget(make_card("📘", "Ders Sayısı", self.lbl_courses), 1, 0)
        layout.addWidget(make_card("🗓️", "Oluşturulan Sınav Programı", self.lbl_exams, btn_excel), 1, 1)

        def update_dashboard():
            try:
                bid = getattr(core_session.current_user, "bolum_id", None)
                dept_name = self._get_dept_name_of_user()
                normalized_name = dept_name.replace(" ", "_").replace("ı", "i").replace("İ", "I")

                with get_conn() as cn:
                    cur = cn.cursor()
                    cur.execute("SELECT COUNT(*) FROM kullanicilar WHERE rol='koordinator' AND bolum_id=?", (bid,))
                    users = cur.fetchone()[0]
                    cur.execute("SELECT COUNT(*) FROM dersler WHERE bolum_id=?", (bid,))
                    courses = cur.fetchone()[0]
                    cur.execute("SELECT COUNT(*) FROM bolumler WHERE id=?", (bid,))
                    dept = cur.fetchone()[0]

                os.makedirs(self.data_dir, exist_ok=True)
                exams = len([
                    f for f in os.listdir(self.data_dir)
                    if f.endswith(".xlsx") and normalized_name in f
                ])

                self.lbl_dept.setText(str(dept))
                self.lbl_users.setText(str(users))
                self.lbl_courses.setText(str(courses))
                self.lbl_exams.setText(str(exams))
            except Exception as e:
                print(f"Dashboard verisi alınamadı: {e}")

        update_dashboard()
        timer = QTimer(self)
        timer.timeout.connect(update_dashboard)
        timer.start(3000)  

        return frame

    
    def _get_dept_name_of_user(self):
        if not core_session or not core_session.current_user:
            return "Bölüm Yok"
        bid = getattr(core_session.current_user, "bolum_id", None)
        if not bid:
            return "Bölüm Yok"
        try:
            with get_conn() as cn:
                cur = cn.cursor()
                cur.execute(q("SELECT ad FROM bolumler WHERE id = ?"), (bid,))
                row = cur.fetchone()
                return row[0] if row else "Bilinmeyen Bölüm"
        except Exception:
            return "Hata"

    
    def _post_init_setup(self):
        default = "rooms" if "rooms" in self.views else "dashboard"
        if default in self.menu_buttons and default in self.views:
            self.menu_buttons[default].setChecked(True)
            self.stack.setCurrentWidget(self.views[default])
            self.active_btn = self.menu_buttons[default]

    def switch_view(self, key, button):
        if key == "schedule" and key in self.views:
            view = self.views[key]
            if hasattr(view, "reload_courses"):
                view.reload_courses()
            if hasattr(view, "reload_rooms"):
                view.reload_rooms()

        if self.active_btn:
            self.active_btn.setChecked(False)
        button.setChecked(True)
        self.active_btn = button

        if key in self.views:
            view = self.views[key]
            self.stack.setCurrentWidget(view)

            if key == "seating_plan" and hasattr(view, "reload_data"):
                try:
                    view.reload_data()
                    print("🔄 Oturma planı verileri yenilendi.")
                except Exception as e:
                    print(f"Oturma planı yenileme hatası: {e}")
        else:
            QMessageBox.warning(self, "Uyarı", f"'{key}' görünümü bulunamadı.")


    def go_login(self):
        try:
            logout()
        except Exception:
            pass
        self.app.show_page("LoginPage")

    def _show_excel_files(self):
        if not os.path.exists(self.data_dir):
            QMessageBox.information(self, "Bilgi", f"'{self.data_dir}' klasörü bulunamadı.")
            return

        dept_name = self._get_dept_name_of_user()
        normalized_name = dept_name.replace(" ", "_").replace("ı", "i").replace("İ", "I")
        files = [
            f for f in os.listdir(self.data_dir)
            if f.endswith(".xlsx") and normalized_name in f
        ]

        if not files:
            QMessageBox.information(self, "Bilgi", "Hiç Excel dosyası bulunamadı.")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Oluşturulan Sınav Programı Dosyaları")
        dialog.setFixedSize(600, 400)
        dialog.setStyleSheet("background-color: #0f2535; color: white;")

        layout = QVBoxLayout(dialog)
        label = QLabel("Açmak için bir dosyaya çift tıklayın:")
        label.setStyleSheet("font-size: 11pt; padding: 5px;")
        layout.addWidget(label)

        list_widget = QListWidget()
        list_widget.setStyleSheet("""
            QListWidget {
                background-color: #112b3d;
                border: 1px solid #1b3b56;
                font-size: 11pt;
            }
            QListWidget::item:hover { background-color: #1f4d73; }
            QListWidget::item:selected { background-color: #2e7d32; }
        """)
        list_widget.addItems(files)
        layout.addWidget(list_widget)
        list_widget.itemDoubleClicked.connect(self._open_excel_file)

        btn_close = QPushButton("Kapat")
        btn_close.setStyleSheet("background-color: #183b57; font-weight: bold; padding: 8px;")
        btn_close.clicked.connect(dialog.close)
        layout.addWidget(btn_close)

        dialog.exec()

    def _open_excel_file(self, item: QListWidgetItem):
        filename = item.text()
        filepath = os.path.join(self.data_dir, filename)
        try:
            sys_ = platform.system()
            if sys_ == "Windows":
                os.startfile(filepath)
            elif sys_ == "Darwin":
                subprocess.call(["open", filepath])
            else:
                subprocess.call(["xdg-open", filepath])
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Dosya açılamadı:\n{filepath}\n\n{e}")

    def exit_app(self):
        confirm = QMessageBox.question(
            self, "Çıkış", "Uygulamadan çıkmak istiyor musunuz?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if confirm == QMessageBox.Yes:
            try:
                logout()
            except Exception:
                pass
            self.app.close()

    def _refresh_data_views(self):
        print("🔄 Data imported — refreshing coordinator views...")

        if "courses" in self.views and hasattr(self.views["courses"], "_search"):
            self.views["courses"]._search()

        if "student" in self.views and hasattr(self.views["student"], "_search"):
            self.views["student"]._search()

        if "dashboard" in self.views:
            dash_widget = self.views["dashboard"]
            for child in dash_widget.children():
                if hasattr(child, "update_dashboard"):
                    try:
                        child.update_dashboard()
                    except Exception as e:
                        print(f"Dashboard refresh error: {e}")
