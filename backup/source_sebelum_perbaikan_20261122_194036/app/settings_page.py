"""
AutoLand Digitizer - Settings Page (dengan Panduan & Pemeliharaan Sistem)
Pengaturan konfigurasi template DWG, koneksi AutoCAD, mode simulasi, serta backup dan restore database.
"""

import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QCheckBox, QMessageBox, QFileDialog,
    QScrollArea
)
from PySide6.QtCore import Qt

from config import (
    DEFAULT_TEMPLATE_PATH, DB_PATH, APP_NAME, APP_VERSION, APP_SUBTITLE
)
from database.db import get_setting, set_setting, get_all_batches
from services.autocad_service import autocad_service
from services.backup_service import (
    create_database_backup, restore_database_backup,
    export_work_package, import_work_package
)
from ui.components.guide_banner import GuideBanner

class SettingsPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 20, 24, 24)
        main_layout.setSpacing(14)

        # Header
        header_layout = QVBoxLayout()
        header_text = QLabel("Pengaturan & Pemeliharaan Sistem")
        header_text.setStyleSheet("font-size: 20px; font-weight: 800; color: #0F172A;")
        header_layout.addWidget(header_text)

        sub = QLabel("Konfigurasi template DWG, integrasi AutoCAD Desktop, cadangan database, dan pertukaran data.")
        sub.setStyleSheet("color: #64748B; font-size: 13px;")
        header_layout.addWidget(sub)
        main_layout.addLayout(header_layout)

        # Panduan Pengaturan
        settings_guide = [
            "<b>AutoCAD Desktop & Template:</b> Tentukan lokasi template DWG default yang memuat kop/etiket gambar kantor pertanahan Anda.",
            "<b>Mode Simulasi AutoCAD:</b> Centang opsi ini jika Anda ingin menguji atau mendemokan seluruh fitur aplikasi di laptop/komputer yang belum terpasang AutoCAD.",
            "<b>Cadangkan Database (Backup):</b> Simpan cadangan data SQLite ke folder backup secara berkala agar riwayat digitalisasi aman dari kehilangan data.",
            "<b>Paket Offline (Flashdisk):</b> Gunakan fitur Ekspor/Impor Paket untuk memindahkan pekerjaan satu desa ke komputer rekan kerja tanpa internet."
        ]
        self.guide_banner = GuideBanner("Petunjuk Pengaturan & Pemeliharaan", settings_guide)
        main_layout.addWidget(self.guide_banner)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background: transparent; border: none;")

        container = QWidget()
        c_layout = QVBoxLayout(container)
        c_layout.setSpacing(14)

        # 1. Konfigurasi AutoCAD & Template DWG
        c_acad = QFrame()
        c_acad.setStyleSheet("background-color: #FFFFFF; border-radius: 8px; border: 1px solid #E2E8F0; padding: 16px;")
        ca_layout = QVBoxLayout(c_acad)
        ca_layout.setSpacing(12)

        lbl_c1 = QLabel("1. Integrasi AutoCAD & Template DWG")
        lbl_c1.setStyleSheet("font-size: 14px; font-weight: 800; color: #1E293B;")
        ca_layout.addWidget(lbl_c1)

        # Template DWG Path
        lbl_tpl = QLabel("Lokasi File Template DWG:")
        lbl_tpl.setProperty("class", "field-label")
        ca_layout.addWidget(lbl_tpl)

        tpl_row = QHBoxLayout()
        self.input_tpl_path = QLineEdit()
        self.input_tpl_path.setText(get_setting("template_dwg_path", str(DEFAULT_TEMPLATE_PATH)))
        tpl_row.addWidget(self.input_tpl_path, 1)

        btn_browse_tpl = QPushButton("Pilih File DWG...")
        btn_browse_tpl.setProperty("class", "btn-secondary")
        btn_browse_tpl.clicked.connect(self._browse_template)
        tpl_row.addWidget(btn_browse_tpl)

        btn_default_tpl = QPushButton("Gunakan Default")
        btn_default_tpl.setProperty("class", "btn-secondary")
        btn_default_tpl.clicked.connect(self._reset_default_template)
        tpl_row.addWidget(btn_default_tpl)
        ca_layout.addLayout(tpl_row)

        # Mode Simulasi
        self.chk_simulation = QCheckBox("Aktifkan Mode Simulasi AutoCAD (Bagi Komputer Tanpa AutoCAD Desktop)")
        self.chk_simulation.setStyleSheet("font-weight: 700; color: #0284C7; margin-top: 6px;")
        self.chk_simulation.setChecked(autocad_service.simulation_mode)
        self.chk_simulation.toggled.connect(self._toggle_simulation)
        ca_layout.addWidget(self.chk_simulation)

        # Uji Koneksi
        acad_test_row = QHBoxLayout()
        btn_test_acad = QPushButton("🔌 Uji Koneksi AutoCAD Sekarang")
        btn_test_acad.setStyleSheet("""
            QPushButton {
                background-color: #1E40AF;
                color: #FFFFFF;
                font-weight: 700;
                padding: 9px 16px;
                border-radius: 6px;
            }
            QPushButton:hover { background-color: #1D4ED8; }
        """)
        btn_test_acad.clicked.connect(self._test_acad_connection)
        acad_test_row.addWidget(btn_test_acad)

        self.lbl_test_result = QLabel("Status: Siap diuji")
        self.lbl_test_result.setStyleSheet("color: #64748B; font-weight: 600;")
        acad_test_row.addWidget(self.lbl_test_result)
        acad_test_row.addStretch()
        ca_layout.addLayout(acad_test_row)

        c_layout.addWidget(c_acad)

        # 2. Database & Backup / Restore
        c_db = QFrame()
        c_db.setStyleSheet("background-color: #FFFFFF; border-radius: 8px; border: 1px solid #E2E8F0; padding: 16px;")
        cdb_layout = QVBoxLayout(c_db)
        cdb_layout.setSpacing(12)

        lbl_c2 = QLabel("2. Database Lokal & Cadangan Data (SQLite)")
        lbl_c2.setStyleSheet("font-size: 14px; font-weight: 800; color: #1E293B;")
        cdb_layout.addWidget(lbl_c2)

        db_path_info = QLabel(f"File Database SQLite: <b>{DB_PATH}</b>")
        db_path_info.setStyleSheet("color: #475569; font-size: 12px;")
        cdb_layout.addWidget(db_path_info)

        db_btn_row = QHBoxLayout()
        btn_backup = QPushButton("💾 Cadangkan Database Sekarang (Backup)")
        btn_backup.setStyleSheet("""
            QPushButton {
                background-color: #059669;
                color: #FFFFFF;
                font-weight: 700;
                padding: 9px 16px;
                border-radius: 6px;
            }
            QPushButton:hover { background-color: #047857; }
        """)
        btn_backup.clicked.connect(self._backup_db)
        db_btn_row.addWidget(btn_backup)

        btn_restore = QPushButton("🔄 Pulihkan Database dari File (.db)")
        btn_restore.setStyleSheet("""
            QPushButton {
                background-color: #D97706;
                color: #FFFFFF;
                font-weight: 700;
                padding: 9px 16px;
                border-radius: 6px;
            }
            QPushButton:hover { background-color: #B45309; }
        """)
        btn_restore.clicked.connect(self._restore_db)
        db_btn_row.addWidget(btn_restore)

        db_btn_row.addStretch()
        cdb_layout.addLayout(db_btn_row)

        c_layout.addWidget(c_db)

        # 3. Paket Pertukaran Offline (Flashdisk)
        c_pkg = QFrame()
        c_pkg.setStyleSheet("background-color: #FFFFFF; border-radius: 8px; border: 1px solid #E2E8F0; padding: 16px;")
        cpkg_layout = QVBoxLayout(c_pkg)
        cpkg_layout.setSpacing(12)

        lbl_c3 = QLabel("3. Pertukaran Paket Pekerjaan Antar Komputer (Offline via Flashdisk)")
        lbl_c3.setStyleSheet("font-size: 14px; font-weight: 800; color: #1E293B;")
        cpkg_layout.addWidget(lbl_c3)

        desc_pkg = QLabel(
            "Fitur ini memungkinkan Anda mengekspor satu batch pekerjaan (PDF, Denah Crop, DWG, dan database) "
            "ke dalam satu file ZIP untuk dikerjakan di komputer rekan lain tanpa memerlukan koneksi internet."
        )
        desc_pkg.setWordWrap(True)
        desc_pkg.setStyleSheet("color: #64748B; font-size: 12px;")
        cpkg_layout.addWidget(desc_pkg)

        pkg_btn_row = QHBoxLayout()
        btn_exp_pkg = QPushButton("📤 Ekspor Paket Pekerjaan...")
        btn_exp_pkg.setProperty("class", "btn-secondary")
        btn_exp_pkg.setStyleSheet("font-weight: 600; padding: 8px 14px;")
        btn_exp_pkg.clicked.connect(self._export_package)
        pkg_btn_row.addWidget(btn_exp_pkg)

        btn_imp_pkg = QPushButton("📥 Impor Paket Pekerjaan...")
        btn_imp_pkg.setProperty("class", "btn-secondary")
        btn_imp_pkg.setStyleSheet("font-weight: 600; padding: 8px 14px;")
        btn_imp_pkg.clicked.connect(self._import_package)
        pkg_btn_row.addWidget(btn_imp_pkg)

        pkg_btn_row.addStretch()
        cpkg_layout.addLayout(pkg_btn_row)

        c_layout.addWidget(c_pkg)

        # 4. Tentang Aplikasi
        c_about = QFrame()
        c_about.setStyleSheet("background-color: #FFFFFF; border-radius: 8px; border: 1px solid #E2E8F0; padding: 16px;")
        ca_layout2 = QVBoxLayout(c_about)
        ca_layout2.setSpacing(6)

        lbl_app_name = QLabel(f"{APP_NAME} v{APP_VERSION}")
        lbl_app_name.setStyleSheet("font-size: 15px; font-weight: 800; color: #1E40AF;")
        ca_layout2.addWidget(lbl_app_name)

        lbl_app_sub = QLabel(APP_SUBTITLE)
        lbl_app_sub.setStyleSheet("color: #475569; font-size: 12px;")
        ca_layout2.addWidget(lbl_app_sub)

        lbl_spec = QLabel("Arsitektur: 100% Offline Lokal Desktop | Windows COM Automation | Standar Penomoran Resmi Pertanahan")
        lbl_spec.setStyleSheet("color: #94A3B8; font-size: 11px;")
        ca_layout2.addWidget(lbl_spec)

        c_layout.addWidget(c_about)

        c_layout.addStretch()
        scroll.setWidget(container)
        main_layout.addWidget(scroll, 1)

    def _browse_template(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Pilih File Template DWG", "", "AutoCAD Drawing (*.dwg)")
        if file_path:
            self.input_tpl_path.setText(file_path)
            set_setting("template_dwg_path", file_path)
            QMessageBox.information(self, "Pengaturan Disimpan", f"Template DWG disetel ke:\n{file_path}")

    def _reset_default_template(self):
        self.input_tpl_path.setText(str(DEFAULT_TEMPLATE_PATH))
        set_setting("template_dwg_path", str(DEFAULT_TEMPLATE_PATH))
        QMessageBox.information(self, "Pengaturan Disimpan", "Template DWG dikembalikan ke lokasi default aplikasi.")

    def _toggle_simulation(self, checked: bool):
        autocad_service.simulation_mode = checked
        if checked:
            self.lbl_test_result.setText("Mode Simulasi Aktif (AutoCAD Virtual)")
            self.lbl_test_result.setStyleSheet("color: #D97706; font-weight: 700;")
        else:
            self.lbl_test_result.setText("Mode Nyata (Menghubungkan ke AutoCAD Desktop Asli)")
            self.lbl_test_result.setStyleSheet("color: #2563EB; font-weight: 700;")

    def _test_acad_connection(self):
        ok, msg = autocad_service.connect(launch_if_closed=True)
        if ok:
            self.lbl_test_result.setText(f"✓ Berhasil: {msg}")
            self.lbl_test_result.setStyleSheet("color: #059669; font-weight: 700;")
            QMessageBox.information(self, "Koneksi AutoCAD Berhasil", msg)
        else:
            self.lbl_test_result.setText(f"✗ Gagal: {msg}")
            self.lbl_test_result.setStyleSheet("color: #DC2626; font-weight: 700;")
            QMessageBox.warning(
                self, "Koneksi AutoCAD Gagal",
                f"{msg}\n\nTips:\nPastikan AutoCAD Desktop telah terpasang di komputer Anda. "
                "Jika ingin mencoba aplikasi tanpa AutoCAD, centang opsi 'Mode Simulasi'."
            )

    def _backup_db(self):
        ok, res = create_database_backup()
        if ok:
            QMessageBox.information(self, "Backup Berhasil", f"Database berhasil dicadangkan ke:\n{res}")
        else:
            QMessageBox.critical(self, "Backup Gagal", res)

    def _restore_db(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Pilih File Backup Database", "", "Database Backup (*.db)")
        if not file_path:
            return

        reply = QMessageBox.question(
            self, "Konfirmasi Pemulihan",
            "Apakah Anda yakin ingin memulihkan database dari file cadangan?\n"
            "Data saat ini akan digantikan oleh data dari file cadangan.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            ok, msg = restore_database_backup(file_path)
            if ok:
                QMessageBox.information(self, "Restore Berhasil", msg)
            else:
                QMessageBox.critical(self, "Restore Gagal", msg)

    def _export_package(self):
        batches = get_all_batches()
        if not batches:
            QMessageBox.warning(self, "Tidak Ada Batch", "Belum ada batch pekerjaan untuk diekspor.")
            return

        batch_id = batches[0]["id"]
        safe_desa = batches[0]["nama_desa"].replace(" ", "_")
        dest_zip, _ = QFileDialog.getSaveFileName(
            self, "Simpan Paket Pekerjaan", f"Paket_Batch_{safe_desa}.zip", "ZIP Archives (*.zip)"
        )
        if not dest_zip:
            return

        ok, msg = export_work_package(batch_id, dest_zip)
        if ok:
            QMessageBox.information(self, "Ekspor Paket Sukses", f"Paket pekerjaan berhasil diekspor ke:\n{msg}")
        else:
            QMessageBox.critical(self, "Gagal Ekspor", msg)

    def _import_package(self):
        zip_path, _ = QFileDialog.getOpenFileName(
            self, "Pilih Paket Pekerjaan", "", "ZIP Archives (*.zip)"
        )
        if not zip_path:
            return

        ok, msg = import_work_package(zip_path)
        if ok:
            QMessageBox.information(self, "Impor Paket Sukses", msg)
        else:
            QMessageBox.critical(self, "Gagal Impor", msg)
