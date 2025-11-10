# app.py
import sys
from pathlib import Path
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QStackedWidget, QMessageBox, QInputDialog
)
from PySide6.QtCore import Qt


SCRIPT_ROOT = Path(__file__).resolve().parent


try:
    from core.db import get_conn, q, USE_SQLITE, DEFAULT_SQLITE_PATH
    from core.auth import hash_password
    from core import session as core_session
    from core.session import User, login_as, logout
except ImportError as e:
    print(f"⚠️ Core modüller yüklenemedi: {e}")
    sys.path.append(str(SCRIPT_ROOT.parent))
    from core.db import get_conn, q, USE_SQLITE, DEFAULT_SQLITE_PATH
    from core.auth import hash_password
    from core import session as core_session
    from core.session import User, login_as, logout


from ui.login import LoginPage
from ui.admin import AdminHome
from ui.coord import CoordHome


class App(QMainWindow):
    """💠 Ana Uygulama Penceresi (Tüm yönlendirme ve oturum yönetimi)"""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Dinamik Sınav Takvimi")
        self.setGeometry(200, 100, 1200, 800)

        container = QWidget()
        self.setCentralWidget(container)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)

        self.stack = QStackedWidget()
        layout.addWidget(self.stack)
        self.pages = {}

      
        self.add_page("LoginPage", LoginPage)
        self.show_page("LoginPage")

    
    def add_page(self, name, PageClass):
        page = PageClass(self)
        self.pages[name] = page
        self.stack.addWidget(page)

    def show_page(self, name):
        if name not in self.pages:
            QMessageBox.warning(self, "Uyarı", f"'{name}' sayfası bulunamadı.")
            return
        self.stack.setCurrentWidget(self.pages[name])

   
    def route_after_login(self):
        """Rol tabanlı yönlendirme"""
        user = core_session.current_user
        if not user:
            QMessageBox.critical(self, "Hata", "Oturum bulunamadı, tekrar giriş yapın.")
            return self.show_page("LoginPage")

        if user.rol == "admin":
            if "AdminHome" not in self.pages:
                self.add_page("AdminHome", AdminHome)
            self.show_page("AdminHome")

        elif user.rol == "koordinator":
         
            if "CoordHome" in self.pages:
                old = self.pages.pop("CoordHome")
                try:
                    self.stack.removeWidget(old)
                    old.deleteLater()
                except Exception:
                    pass
            self.add_page("CoordHome", CoordHome)
            self.show_page("CoordHome")

        else:
            QMessageBox.warning(self, "Hata", f"Bilinmeyen rol: {user.rol}")
            self.show_page("LoginPage")

    def switch_to_coord_view(self):
        """Admin istediği koordinatör görünümüne geçebilir."""
        try:
            user = core_session.current_user
            if not user or user.rol != "admin":
                QMessageBox.warning(self, "Yetki Hatası", "Bu özelliği yalnızca admin kullanabilir.")
                return

            
            with get_conn() as cn:
                cur = cn.cursor()
                cur.execute("""
                    SELECT k.id, k.eposta, b.ad
                    FROM kullanicilar k
                    JOIN bolumler b ON b.id = k.bolum_id
                    WHERE k.rol = 'koordinator'
                    ORDER BY b.ad
                """)
                rows = cur.fetchall()

            if not rows:
                QMessageBox.information(self, "Bilgi", "Hiç koordinatör bulunamadı.")
                return

            
            options = [f"{b_ad} ({eposta})" for (_, eposta, b_ad) in rows]
            selected, ok = QInputDialog.getItem(
                self, "Koordinatör Seç", "Geçilecek Koordinatör:", options, 0, False
            )
            if not ok or not selected:
                return

            idx = options.index(selected)
            koord_id, eposta, bolum_ad = rows[idx]

            with get_conn() as cn:
                cur = cn.cursor()
                cur.execute("SELECT id, eposta, rol, bolum_id FROM kullanicilar WHERE id=?", (koord_id,))
                row = cur.fetchone()
                if not row:
                    QMessageBox.warning(self, "Hata", "Koordinatör bilgisi alınamadı.")
                    return

                uid, eposta, rol, bolum_id = row
                if rol != "koordinator":
                    QMessageBox.warning(self, "Hata", "Seçilen kullanıcı koordinatör değildir.")
                    return

           
            self.previous_admin_user = user
            login_as(User(id=uid, eposta=eposta, rol=rol, bolum_id=bolum_id))
            print(f"🔄 Admin '{user.eposta}' -> {bolum_ad} koordinatör görünümüne geçti")

           
            if "CoordHome" in self.pages:
                old = self.pages.pop("CoordHome")
                self.stack.removeWidget(old)
                old.deleteLater()

            # 
            self.add_page("CoordHome", CoordHome)
            self.show_page("CoordHome")

        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Geçiş yapılamadı:\n{e}")

    
    def logout_user(self):
        """Oturumu temizle ve giriş sayfasına dön."""
        try:
            logout()
        except Exception as e:
            print(f"Logout hatası: {e}")

        
        for name, page in list(self.pages.items()):
            if name != "LoginPage":
                self.stack.removeWidget(page)
                page.deleteLater()
                del self.pages[name]

        self.show_page("LoginPage")

def initialize_database():
    """Veritabanını oluşturur ve varsayılan verileri ekler."""
    try:
        if USE_SQLITE:
            db_path = DEFAULT_SQLITE_PATH
            db_path.parent.mkdir(parents=True, exist_ok=True)
            schema_file = SCRIPT_ROOT / "core" / "schema.sqlite.sql"
        else:
            schema_file = SCRIPT_ROOT / "core" / "schema.pg.sql"

        with open(schema_file, "r", encoding="utf-8") as f:
            schema_sql = f.read()

        with get_conn() as conn:
            if hasattr(conn, "executescript"):
                conn.executescript(schema_sql)
            else:
                conn.cursor().execute(schema_sql)
            conn.commit()
        print(f"✅ Şema yüklendi: {schema_file}")

        with get_conn() as conn:
            cur = conn.cursor()
            bolumler = [
                (1, "Bilgisayar Müh."), (2, "Yazılım Müh."), (3, "Elektrik Müh."),
                (4, "Elektronik Müh."), (5, "İnşaat Müh.")
            ]
            for bid, ad in bolumler:
                cur.execute(q("INSERT OR IGNORE INTO bolumler(id, ad) VALUES (?, ?)"), (bid, ad))
            cur.execute(q("INSERT OR IGNORE INTO kullanicilar(eposta, sifre_hash, rol) VALUES (?, ?, ?)"),
                        ("admin@kou.edu.tr", hash_password("12345"), "admin"))
            conn.commit()
        print("✅ Varsayılan kullanıcılar eklendi.")

        try:
            with get_conn() as cn:
                cur = cn.cursor()
                cur.executescript("""
                    UPDATE derslikler SET kapasite=42, satir=7, sutun=3, sira_grup=3 WHERE ad='301';
                    UPDATE derslikler SET kapasite=48, satir=8, sutun=3, sira_grup=4 WHERE ad='Büyük Amfi';
                    UPDATE derslikler SET kapasite=42, satir=7, sutun=3, sira_grup=3 WHERE ad='303';
                    UPDATE derslikler SET kapasite=30, satir=6, sutun=5, sira_grup=2 WHERE ad='EDA';
                    UPDATE derslikler SET kapasite=42, satir=7, sutun=3, sira_grup=3 WHERE ad='305';
                """)
                cn.commit()
            print("✅ Tüm derslikler tabloya göre güncellendi.")
        except Exception as e:
            print(f"⚠️ Derslik güncelleme sırasında hata: {e}")

    except Exception as e:
        QMessageBox.critical(None, "Veritabanı Hatası", f"Veritabanı yüklenemedi:\n{e}")
        sys.exit(1)



if __name__ == "__main__":
    app = QApplication(sys.argv)
    initialize_database()

    window = App()
    window.show()
    sys.exit(app.exec())





    

