# ui/user_management.py 
import sys
import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QFormLayout,
    QLabel, QLineEdit, QPushButton, QMessageBox, QComboBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QFrame
)
from PySide6.QtGui import QFont
from PySide6.QtCore import Qt


try:
    from core.db import get_conn, q
    from core.auth import hash_password
    
    from core import session as core_session 
except ImportError:
    print("HATA: user_management.py, core modüllerini yükleyemedi.")
    pass


NAVY = "#0f2535"
CARD = "#112b3d"
TEXT = "#e8f5e9"
SUBTEXT = "#bcd0d6"
GREEN = "#2e7d32"
RED = "#c94a4a"


class UserManagementTab(QWidget):
    """
    Kullanıcı Yönetimi sayfası (Tkinter UserManagementPage'in PySide6 karşılığı)
    ui/rooms.py'nin düzenini (sol panel/sağ panel) kullanır.
    """
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.bolumler_map_by_name = {}
        self.bolumler_map_by_id = {}  

        self.init_ui()
        self.connect_signals()
        self._load_departments() 
        self._load_users()       
    def init_ui(self):
        """Arayüzü (UI) oluşturur."""
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0) 
        main_layout.setSpacing(20)

      
        left_panel = QFrame()
        left_layout = QVBoxLayout(left_panel)
        left_panel.setStyleSheet(f"background-color: {CARD}; border-radius: 8px;")
        left_panel.setFixedWidth(400)
        
        form_title = QLabel("Yeni Kullanıcı Ekle")
        form_title.setFont(QFont("Segoe UI", 13, QFont.Bold))
        form_title.setStyleSheet(f"color: {SUBTEXT}; padding: 5px;")
        left_layout.addWidget(form_title)

      
        self.form = QWidget()
        form_layout = QFormLayout(self.form)
        form_layout.setContentsMargins(10, 10, 10, 10)
        form_layout.setSpacing(10)
        form_layout.setLabelAlignment(Qt.AlignRight)
        
        self.ent_mail = QLineEdit()
        self.ent_pass = QLineEdit()
        self.ent_pass.setEchoMode(QLineEdit.Password) # Tkinter: show="•"
        
        self.cmb_role = QComboBox()
        self.cmb_role.addItems(["admin", "koordinator"])
        
        self.cmb_dept = QComboBox()
        
       
        form_layout.addRow("E-posta:", self.ent_mail)
        form_layout.addRow("Şifre:", self.ent_pass)
        form_layout.addRow("Rol:", self.cmb_role)
        form_layout.addRow("Bölüm:", self.cmb_dept)
        
        left_layout.addWidget(self.form)
        
   
        self.btn_ekle = QPushButton("Kullanıcı Ekle")
        self.btn_ekle.setStyleSheet(f"background-color: {GREEN}; font-weight: bold; padding: 8px;")
        left_layout.addWidget(self.btn_ekle, alignment=Qt.AlignRight)

        left_layout.addStretch()
        main_layout.addWidget(left_panel)

 
        right_panel = QFrame()
        right_layout = QVBoxLayout(right_panel)
        right_panel.setStyleSheet(f"background-color: {CARD}; border-radius: 8px;")
        
        list_title = QLabel("Kayıtlı Kullanıcılar")
        list_title.setFont(QFont("Segoe UI", 13, QFont.Bold))
        list_title.setStyleSheet(f"color: {SUBTEXT}; padding: 5px;")
        right_layout.addWidget(list_title)
        
        
        self.table = QTableWidget()
        cols = ("id", "eposta", "rol", "bolum")
        self.table.setColumnCount(len(cols))
        self.table.setHorizontalHeaderLabels(["ID", "E-posta", "Rol", "Bölüm"])
        
       
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents) # ID
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents) # Rol
        
        right_layout.addWidget(self.table)
    
        self.btn_sil = QPushButton("Seçili Kullanıcıyı Sil")
        self.btn_sil.setStyleSheet(f"background-color: {RED}; font-weight: bold; padding: 8px;")
        right_layout.addWidget(self.btn_sil, alignment=Qt.AlignRight)
        
        main_layout.addWidget(right_panel, stretch=1)

    def connect_signals(self):
        """Butonları ve olayları fonksiyonlara bağlar."""
        self.btn_ekle.clicked.connect(self._add_user)
        self.btn_sil.clicked.connect(self._delete_user)
        
        self.cmb_role.currentTextChanged.connect(self._on_role_changed)

    
    def _on_role_changed(self, role):
        """Rol 'admin' ise bölüm seçmeyi engeller."""
        if role == 'admin':
            self.cmb_dept.setEnabled(False)
            self.cmb_dept.setCurrentIndex(0) 
        else:
            self.cmb_dept.setEnabled(True)

    def _load_departments(self):
        """Bölüm verilerini veritabanından çeker ve ComboBox'ı doldurur."""
        try:
            with get_conn() as conn:
                cur = conn.cursor()
                cur.execute("SELECT id, ad FROM bolumler ORDER BY id")
                rows = cur.fetchall()
                
             
                self.bolumler_map_by_id.clear()
                self.bolumler_map_by_name.clear()
                self.cmb_dept.clear()
                
                
                self.cmb_dept.addItem("— Admin (Bölüm Yok) —", userData=None)
                
                for bolum_id, bolum_ad in rows:
                    self.bolumler_map_by_id[bolum_id] = bolum_ad
                    self.bolumler_map_by_name[bolum_ad] = bolum_id
                    self.cmb_dept.addItem(bolum_ad, userData=bolum_id)
                    
            self.cmb_role.setCurrentIndex(1) 
            self.cmb_dept.setCurrentIndex(1) 
            
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Bölüm listesi yüklenemedi:\n{e}")

    def _load_users(self):
        """Kullanıcıları veritabanından çeker ve tabloyu doldurur."""
        self.table.setRowCount(0) 
        try:
            with get_conn() as conn:
                cur = conn.cursor()
                
                cur.execute("""
                    SELECT k.id, k.eposta, k.rol, COALESCE(b.ad, '—')
                    FROM kullanicilar k
                    LEFT JOIN bolumler b ON b.id = k.bolum_id
                    ORDER BY k.id
                """)
                rows = cur.fetchall()
                
                self.table.setRowCount(len(rows))
                for row_idx, row_data in enumerate(rows):
                    (uid, eposta, rol, bolum) = row_data
                    self.table.setItem(row_idx, 0, QTableWidgetItem(str(uid)))
                    self.table.setItem(row_idx, 1, QTableWidgetItem(eposta))
                    self.table.setItem(row_idx, 2, QTableWidgetItem(rol))
                    self.table.setItem(row_idx, 3, QTableWidgetItem(bolum))
                    
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Kullanıcılar yüklenemedi:\n{e}")

    def _add_user(self):
        """Formdaki bilgileri alıp yeni kullanıcı ekler."""
        mail = self.ent_mail.text().strip()
        pw = self.ent_pass.text().strip()
        role = self.cmb_role.currentText()
        
        
        bolum_id = self.cmb_dept.currentData() 
        
        if role == 'admin':
            bolum_id = None 
            
        if not mail or "@" not in mail:
            QMessageBox.warning(self, "Uyarı", "Geçerli bir e-posta girin.")
            return
        if not pw:
            QMessageBox.warning(self, "Uyarı", "Şifre giriniz.")
            return
        if role == 'koordinator' and bolum_id is None:
            QMessageBox.warning(self, "Uyarı", "Koordinatör için bir bölüm seçmelisiniz.")
            return

        try:
            with get_conn() as conn:
                c = conn.cursor()
              
                c.execute(
                    q("INSERT INTO kullanicilar(eposta, sifre_hash, rol, bolum_id) VALUES(?, ?, ?, ?)"),
                    (mail, hash_password(pw), role, bolum_id),
                )
                conn.commit()
            
            QMessageBox.information(self, "Bilgi", "Kullanıcı başarıyla eklendi.")
            self._clear_form()
            self._load_users() 
            
        except Exception as e:
            if "UNIQUE" in str(e).upper():
                QMessageBox.critical(self, "Hata", "Bu e-posta adresi zaten kullanılıyor.")
            else:
                QMessageBox.critical(self, "Hata", f"Kullanıcı eklenemedi:\n{e}")

    def _delete_user(self):
        """Tablodan seçili kullanıcıyı siler."""
        selected_rows = self.table.selectedItems()
        if not selected_rows:
            QMessageBox.warning(self, "Uyarı", "Silinecek kullanıcı seçilmedi.")
            return
        
      
        selected_row_index = selected_rows[0].row()
        uid_item = self.table.item(selected_row_index, 0)
        uid = int(uid_item.text())
        
        eposta_item = self.table.item(selected_row_index, 1)
        eposta = eposta_item.text()

        if core_session.current_user and core_session.current_user.id == uid:
            QMessageBox.critical(self, "Hata", "Kendinizi silemezsiniz.")
            return

        if not QMessageBox.question(self, "Onay", 
                                  f"'{eposta}' kullanıcısını silmek istediğinizden emin misiniz?",
                                  QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            return
            
        try:
            with get_conn() as conn:
                c = conn.cursor()
                c.execute("DELETE FROM kullanicilar WHERE id=?", (uid,))
                conn.commit()
            
            self._load_users() 
            QMessageBox.information(self, "Bilgi", "Kullanıcı silindi.")
            
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Kullanıcı silinemedi:\n{e}")

    def _clear_form(self):
        """Kullanıcı ekleme formunu temizler."""
        self.ent_mail.clear()
        self.ent_pass.clear()
        self.cmb_role.setCurrentIndex(1) 
        self.cmb_dept.setCurrentIndex(1) 


        