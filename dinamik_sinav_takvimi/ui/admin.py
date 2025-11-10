# ui/admin.py — optimize edilmiş + SeatingPlan entegre sürüm
import sys
import os
import platform
import subprocess
from ui.schedule_wizard import ScheduleWizard
from core.session import logout
from ui.rooms import RoomsTab
from ui.seating_plan import SeatingPlan as SeatingPlanTab

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QStackedWidget,
    QFrame, QMessageBox, QGridLayout, QDialog, QListWidget, QListWidgetItem
)
from PySide6.QtGui import QPixmap, QFont
from PySide6.QtCore import Qt, QTimer

try:
    from core.db import get_conn
except ImportError:
    print("⚠️ core.db modülü bulunamadı.")
    get_conn = None


try:
    from ui.user_management import UserManagementTab
except ImportError:
    UserManagementTab = None

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

# === Proje kökü ===
SCRIPT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class AdminHome(QWidget):
    """Admin paneli ana görünümü (Oturma Planı entegre)"""
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.views = {}
        self.menu_buttons = {}
        self.active_btn = None
        self.active_role = "admin"

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        sidebar = self._build_sidebar()
        main_content = self._build_main_content()
        layout.addWidget(sidebar)
        layout.addWidget(main_content)

        if "dashboard" in self.menu_buttons and "dashboard" in self.views:
            self.menu_buttons["dashboard"].setChecked(True)
            self.stack.setCurrentWidget(self.views["dashboard"])
            self.active_btn = self.menu_buttons["dashboard"]

    # ---------------------------------------------------------
    # Sidebar
    # ---------------------------------------------------------
    def _build_sidebar(self):
        sidebar = QFrame()
        sidebar.setStyleSheet("""
            QFrame {
                background-color: #0f2535;
                border-right: 2px solid #1b3b56;
            }
        """)
        sidebar.setFixedWidth(240)

        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(20, 20, 20, 20)
        sidebar_layout.setSpacing(14)

        # Logo
        logo_path = os.path.join(SCRIPT_ROOT, "assets", "kou.png")
        if os.path.exists(logo_path):
            logo = QLabel()
            pix = QPixmap(logo_path).scaled(90, 90, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            logo.setPixmap(pix)
            logo.setAlignment(Qt.AlignCenter)
            sidebar_layout.addWidget(logo)

        # Başlık
        title = QLabel("KOÜ Sınav Takvimi")
        title.setStyleSheet("color: white; font-weight: bold; font-size: 16px;")
        title.setAlignment(Qt.AlignCenter)
        sidebar_layout.addWidget(title)

        # Görünüm geçiş butonu
        btn_switch = QPushButton("Koordinatör Görünümüne Geç")
        btn_switch.setStyleSheet("""
            QPushButton {
                background-color: #2e7d32;
                color: white;
                border-radius: 6px;
                padding: 6px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #388e3c; }
        """)
        btn_switch.clicked.connect(self.app.switch_to_coord_view)
        sidebar_layout.addWidget(btn_switch)

        # Menü butonları
        menu_items = [
            ("Gösterge Paneli", "dashboard", "📊"),
            ("Kullanıcı Yönetimi", "users", "👥"),
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
            sidebar_layout.addWidget(btn)
            self.menu_buttons[key] = btn

        sidebar_layout.addStretch()
        return sidebar

    def _build_main_content(self):
        main = QFrame()
        main.setStyleSheet("background-color: #112b3d;")
        main_layout = QVBoxLayout(main)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(10)

        top_bar = QLabel("🧑‍💼  Admin, hoş geldin!")
        top_bar.setAlignment(Qt.AlignRight)
        top_bar.setStyleSheet("color: white; font-size: 13px; font-weight: bold;")
        main_layout.addWidget(top_bar)

        self.stack = QStackedWidget()
        main_layout.addWidget(self.stack)

        self._create_views()

        footer = QFrame()
        f_layout = QHBoxLayout(footer)
        f_layout.setContentsMargins(0, 0, 0, 0)
        f_layout.setSpacing(8)

        btn_back = QPushButton("Login Ekranına Dön")
        btn_exit = QPushButton("Çıkış")

        btn_style = """
            QPushButton {
                background-color: #183b57;
                color: white;
                padding: 6px 10px;
                border-radius: 6px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #1f4d73; }
        """
        btn_back.setStyleSheet(btn_style)
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
        main_layout.addWidget(footer)
        return main


    def _create_views(self):
        self.views["dashboard"] = self._dashboard_view()
        self.stack.addWidget(self.views["dashboard"])

        if UserManagementTab:
            self.views["users"] = UserManagementTab(self.app)
            self.stack.addWidget(self.views["users"])

        if RoomsTab:
            self.views["rooms"] = RoomsTab(self.app)
            self.stack.addWidget(self.views["rooms"])
        if ImportCoursesTab:
            self.views["import_courses"] = ImportCoursesTab(self, self.app)
            self.stack.addWidget(self.views["import_courses"])
        if CoursesTab:
            self.views["courses"] = CoursesTab(self, self.app)
            self.stack.addWidget(self.views["courses"])
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

        self.views["schedule"] = ScheduleWizard(self.app, role="admin")
        self.stack.addWidget(self.views["schedule"])
        self.views["seating_plan"] = SeatingPlanTab(self.app)
        self.stack.addWidget(self.views["seating_plan"])
        print("✅ Loaded views:", list(self.views.keys()))



    def _dashboard_view(self):

        frame = QFrame()
        frame.setStyleSheet("background-color: #112b3d; border-radius: 10px;")
        layout = QGridLayout(frame)
        layout.setSpacing(20)
        layout.setContentsMargins(20, 20, 20, 20)

        self.lbl_users = QLabel("0")
        self.lbl_dept = QLabel("0")
        self.lbl_courses = QLabel("0")
        self.lbl_exams = QLabel("0")

        for lbl in [self.lbl_users, self.lbl_dept, self.lbl_courses, self.lbl_exams]:
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

        # --- Excel detail button ---
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

        layout.addWidget(make_card("👤", "Toplam Kullanıcı", self.lbl_users), 0, 0)
        layout.addWidget(make_card("🏫", "Toplam Bölüm", self.lbl_dept), 0, 1)
        layout.addWidget(make_card("📘", "Ders Sayısı", self.lbl_courses), 1, 0)
        layout.addWidget(make_card("🗓️", "Oluşturulan Sınav Programı", self.lbl_exams, btn_excel), 1, 1)

        def update_dashboard():
            try:
                with get_conn() as cn:
                    cur = cn.cursor()
                    cur.execute("SELECT COUNT(*) FROM bolumler")
                    dept = cur.fetchone()[0]
                    cur.execute("SELECT COUNT(*) FROM kullanicilar")
                    users = cur.fetchone()[0]
                    cur.execute("SELECT COUNT(*) FROM dersler")
                    courses = cur.fetchone()[0]
                data_dir = os.path.join(SCRIPT_ROOT, "data")
                os.makedirs(data_dir, exist_ok=True)
                exams = len([f for f in os.listdir(data_dir) if f.endswith('.xlsx')])

                self.lbl_users.setText(str(users))
                self.lbl_dept.setText(str(dept))
                self.lbl_courses.setText(str(courses))
                self.lbl_exams.setText(str(exams))
            except Exception as e:
                print(f"Dashboard DB Hatası: {e}")

        update_dashboard()
        timer = QTimer(self)
        timer.timeout.connect(update_dashboard)
        timer.start(3000) 

        return frame



    def _show_excel_files(self):
        data_dir = os.path.join(SCRIPT_ROOT, "data")
        if not os.path.exists(data_dir):
            QMessageBox.information(self, "Bilgi", f"'{data_dir}' klasörü bulunamadı.")
            return

        files = [f for f in os.listdir(data_dir) if f.endswith(".xlsx")]
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
        filepath = os.path.join(SCRIPT_ROOT, "data", filename)
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
        print("🔄 Data imported — refreshing views...")

        if "courses" in self.views and hasattr(self.views["courses"], "_search"):
            self.views["courses"]._search()

        if "student" in self.views and hasattr(self.views["student"], "_search"):
            self.views["student"]._search()
