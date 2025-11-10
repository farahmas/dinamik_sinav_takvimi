#ui/login.py
import os
import json
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton,
    QLineEdit, QStackedWidget, QMessageBox, QCheckBox
)
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt
from core.db import get_conn, q
from core.auth import check_password
from core.session import login_as, User

CFG_PATH = ".dst_config.json"


def _load_logo(size=(140, 140)):
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(base_dir, "assets", "kou.png")
    if not os.path.exists(path):
        print("⚠️ Logo bulunamadı:", path)
        return None
    pixmap = QPixmap(path)
    return pixmap.scaled(size[0], size[1], Qt.KeepAspectRatio, Qt.SmoothTransformation)


def load_cfg():
    if os.path.exists(CFG_PATH):
        try:
            return json.load(open(CFG_PATH, "r", encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_cfg(cfg: dict):
    try:
        json.dump(cfg, open(CFG_PATH, "w", encoding="utf-8"))
    except Exception:
        pass


class LoginPage(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app

        self.setStyleSheet("""
            QWidget {
                background-color: #0f2535;
                color: #e8f5e9;
                font-family: 'Segoe UI';
                font-size: 13px;
            }
            QPushButton {
                background-color: #2e7d32;
                color: white;
                border-radius: 6px;
                padding: 10px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #43a047; }
            QLineEdit {
                background-color: #102d44;
                border: 1px solid #1b3a57;
                border-radius: 5px;
                padding: 6px;
                color: white;
            }
            QLabel { color: #e8f5e9; }
        """)

        self.cfg = load_cfg()
        self.last_role = self.cfg.get("last_tab", "admin")
        self.last_email = {
            "admin": self.cfg.get("last_email_admin", ""),
            "koordinator": self.cfg.get("last_email_koord", "")
        }
        self.remember_me = bool(self.cfg.get("remember_me", True))
        self.active_role = None

        self.stack = QStackedWidget()
        layout = QVBoxLayout(self)
        layout.addWidget(self.stack)

        self.page_landing = QWidget()
        self.page_form = QWidget()
        self.stack.addWidget(self.page_landing)
        self.stack.addWidget(self.page_form)

        self._build_landing()
        self._build_form()
        self.show_page("landing")

        self.input_pw.returnPressed.connect(self._do_login)

    def _build_landing(self):
        layout = QVBoxLayout(self.page_landing)
        layout.setAlignment(Qt.AlignCenter)

        logo = _load_logo()
        if logo:
            lbl_logo = QLabel()
            lbl_logo.setPixmap(logo)
            lbl_logo.setAlignment(Qt.AlignCenter)
            layout.addWidget(lbl_logo)

        title = QLabel("🗓️ Dinamik Sınav Takvimi")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size:20px; font-weight:bold; color:white; margin-bottom:20px;")
        layout.addWidget(title)

        btn_admin = QPushButton("👩‍💼 Akademik / Admin Giriş")
        btn_admin.clicked.connect(lambda: self._open_form("admin"))
        btn_koord = QPushButton("🏫 Bölüm Koordinatörü Girişi")
        btn_koord.clicked.connect(lambda: self._open_form("koordinator"))

        layout.addWidget(btn_admin)
        layout.addWidget(btn_koord)

        info = QLabel("Admin tüm bölümlere erişir; Koordinatör yalnızca kendi bölümünü yönetir.")
        info.setAlignment(Qt.AlignCenter)
        info.setStyleSheet("color:#bcd0d6; margin-top:12px; font-size:11px;")
        layout.addWidget(info)

    def _build_form(self):
        layout = QVBoxLayout(self.page_form)
        layout.setAlignment(Qt.AlignTop)

        logo = _load_logo((110, 110))
        if logo:
            lbl_logo = QLabel()
            lbl_logo.setPixmap(logo)
            lbl_logo.setAlignment(Qt.AlignCenter)
            layout.addWidget(lbl_logo)

        title = QLabel("Giriş Yap")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size:18px; font-weight:bold; margin-bottom:10px;")
        layout.addWidget(title)

        self.input_email = QLineEdit()
        self.input_email.setPlaceholderText("E-posta")

        self.input_pw = QLineEdit()
        self.input_pw.setEchoMode(QLineEdit.Password)
        self.input_pw.setPlaceholderText("Şifre")

        self.chk_show_pw = QCheckBox("Şifreyi göster")
        self.chk_show_pw.stateChanged.connect(
            lambda s: self.input_pw.setEchoMode(QLineEdit.Normal if s else QLineEdit.Password)
        )

        self.chk_remember = QCheckBox("Beni hatırla")
        self.chk_remember.setChecked(self.remember_me)

        self.lbl_error = QLabel("")
        self.lbl_error.setStyleSheet("color:#ff6b6b; font-weight:bold;")

        btn_login = QPushButton("Giriş")
        btn_login.clicked.connect(self._do_login)

        btn_back = QPushButton("← Geri")
        btn_back.setStyleSheet("background-color:#183b57;")
        btn_back.clicked.connect(lambda: self.show_page("landing"))

        layout.addWidget(self.input_email)
        layout.addWidget(self.input_pw)
        layout.addWidget(self.chk_show_pw)
        layout.addWidget(self.chk_remember)
        layout.addWidget(self.lbl_error)
        layout.addWidget(btn_login)
        layout.addWidget(btn_back)

    def show_page(self, name):
        self.stack.setCurrentWidget(self.page_landing if name == "landing" else self.page_form)

    def _open_form(self, role):
        self.active_role = role
        self.input_email.setText(self.last_email.get(role, ""))
        self.input_pw.setText("")
        self.lbl_error.setText("")
        self.show_page("form")

    def _do_login(self):
        if not self.active_role:
            QMessageBox.warning(self, "Uyarı", "Lütfen önce rol seçin (Admin ya da Koordinatör).")
            return

        email = self.input_email.text().strip()
        pw = self.input_pw.text().strip()
        role = self.active_role

        if not email:
            self.lbl_error.setText("E-posta boş olamaz.")
            return
        if "@" not in email or "." not in email:
            self.lbl_error.setText("Geçerli bir e-posta giriniz.")
            return
        if not pw:
            self.lbl_error.setText("Şifre boş olamaz.")
            return

        try:
            with get_conn() as conn:
                cur = conn.cursor()
                cur.execute(q("SELECT id, rol, bolum_id, sifre_hash FROM kullanicilar WHERE eposta = ?"), (email,))
                row = cur.fetchone()
                if not row:
                    self.lbl_error.setText("Kullanıcı bulunamadı.")
                    return

                uid, rol_db, bolum_id, sifre_hash = row
                if rol_db != role:
                    self.lbl_error.setText(f"Bu kullanıcı '{rol_db}' rolündedir.")
                    return
                if not check_password(pw, sifre_hash):
                    self.lbl_error.setText("Şifre hatalı.")
                    return

                cfg = load_cfg()
                cfg["remember_me"] = bool(self.chk_remember.isChecked())
                cfg["last_tab"] = role
                if self.chk_remember.isChecked():
                    if role == "admin":
                        cfg["last_email_admin"] = email
                    else:
                        cfg["last_email_koord"] = email
                save_cfg(cfg)

                user_obj = User(id=uid, eposta=email, rol=rol_db, bolum_id=bolum_id)
                login_as(user_obj)

                from core import session as core_session
                print("✅ Oturum açıldı:", core_session.current_user)

            self.app.route_after_login()

        except Exception as e:
            QMessageBox.critical(self, "Giriş Hatası", str(e))