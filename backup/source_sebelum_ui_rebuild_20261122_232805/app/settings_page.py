"""Pengaturan: template DWG, koneksi AutoCAD, backup data, dan paket offline."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
    QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from config import APP_NAME, APP_SUBTITLE, APP_VERSION, DB_PATH, DEFAULT_TEMPLATE_PATH
from database.db import get_all_batches, get_setting, set_setting
from services.autocad_service import autocad_service
from services.backup_service import (
    create_database_backup, export_work_package, import_work_package,
    restore_database_backup,
)
from ui.components.form_field import InlineField
from ui.components.guide_banner import GuideBanner
from ui.components.page_header import PageHeader
from ui.components.section_card import SectionCard


class SettingsPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 12, 18, 12)
        layout.setSpacing(8)
        layout.addWidget(PageHeader(
            "Pengaturan & Pemeliharaan",
            "Template DWG, koneksi AutoCAD 2021, cadangan data, dan pertukaran paket offline.",
        ))

        layout.addWidget(GuideBanner("Sebelum mulai", [
            "Aplikasi terhubung langsung ke <b>AutoCAD Desktop 2021</b> melalui COM. Uji koneksi sebelum memproses dokumen.",
            "Jika template kantor belum tersedia, aplikasi membuat DWG baru otomatis.",
            "Lakukan <b>Backup Database</b> secara berkala agar riwayat pekerjaan aman.",
            "Gunakan paket offline untuk memindahkan satu batch ke komputer lain tanpa internet.",
        ]))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background:transparent;border:none;")
        container = QWidget()
        content = QVBoxLayout(container)
        content.setContentsMargins(0, 0, 4, 0)
        content.setSpacing(8)

        content.addWidget(self._build_autocard_section())
        content.addWidget(self._build_backup_section())
        content.addWidget(self._build_package_section())
        content.addWidget(self._build_about_section())
        content.addStretch()
        scroll.setWidget(container)
        layout.addWidget(scroll, 1)

    def _build_autocard_section(self) -> QWidget:
        card = SectionCard(
            "1. Integrasi AutoCAD & Template DWG",
            "Template resmi kantor bersifat opsional.",
        )
        self.input_tpl_path = QLineEdit()
        self.input_tpl_path.setText(get_setting("template_dwg_path", str(DEFAULT_TEMPLATE_PATH)))
        self.input_tpl_path.setMinimumWidth(280)
        card.body_layout.addWidget(InlineField(
            "Template DWG",
            "Lokasi file .dwg resmi. Kosong/placeholder berarti DWG baru dibuat otomatis.",
            self.input_tpl_path,
        ))

        browse_row = QHBoxLayout()
        browse_row.setSpacing(8)
        btn_browse = QPushButton("Pilih File DWG")
        btn_browse.setProperty("class", "btn-secondary")
        btn_browse.setToolTip("Cari file template DWG di komputer lalu simpan lokasinya")
        btn_browse.clicked.connect(self._browse_template)
        browse_row.addWidget(btn_browse)

        btn_default = QPushButton("Gunakan Default")
        btn_default.setProperty("class", "btn-secondary")
        btn_default.setToolTip("Kembalikan lokasi template ke folder bawaan aplikasi")
        btn_default.clicked.connect(self._reset_default_template)
        browse_row.addWidget(btn_default)
        browse_row.addStretch()
        card.body_layout.addLayout(browse_row)

        test_row = QHBoxLayout()
        test_row.setSpacing(8)
        btn_test = QPushButton("Uji Koneksi AutoCAD")
        btn_test.setProperty("class", "btn-primary")
        btn_test.setToolTip("Hubungkan ke AutoCAD Desktop 2021 yang sedang berjalan atau jalankan aplikasinya")
        btn_test.clicked.connect(self._test_acad_connection)
        test_row.addWidget(btn_test)

        self.lbl_test_result = QLabel("Status: belum diuji")
        self.lbl_test_result.setObjectName("PageSubtitle")
        self.lbl_test_result.setWordWrap(True)
        test_row.addWidget(self.lbl_test_result, 1)
        card.body_layout.addLayout(test_row)
        return card

    def _build_backup_section(self) -> QWidget:
        card = SectionCard("2. Database Lokal & Cadangan", "Data disimpan di komputer ini.")
        path = QLabel(f"File database: <b>{DB_PATH}</b>")
        path.setObjectName("PageSubtitle")
        path.setTextFormat(Qt.RichText)
        path.setWordWrap(True)
        card.body_layout.addWidget(path)

        row = QHBoxLayout()
        row.setSpacing(8)
        btn_backup = QPushButton("Cadangkan Database")
        btn_backup.setProperty("class", "btn-success")
        btn_backup.setToolTip("Simpan salinan database SQLite ke folder backup")
        btn_backup.clicked.connect(self._backup_db)
        row.addWidget(btn_backup)

        btn_restore = QPushButton("Pulihkan dari File (.db)")
        btn_restore.setProperty("class", "btn-warning")
        btn_restore.setToolTip("Ganti database saat ini dengan berkas cadangan")
        btn_restore.clicked.connect(self._restore_db)
        row.addWidget(btn_restore)
        row.addStretch()
        card.body_layout.addLayout(row)
        return card

    def _build_package_section(self) -> QWidget:
        card = SectionCard(
            "3. Pertukaran Paket Pekerjaan",
            "Pindahkan satu batch ke komputer lain melalui flashdisk.",
        )
        self.combo_package_batch = QComboBox()
        for batch in get_all_batches():
            self.combo_package_batch.addItem(
                f"Desa {batch['nama_desa']} ({batch['kecamatan']}) — ID {batch['id']}",
                batch["id"],
            )
        if self.combo_package_batch.count() == 0:
            self.combo_package_batch.addItem("Belum ada batch", None)
        card.body_layout.addWidget(InlineField(
            "Batch", "Pilih batch yang akan dimasukkan ke paket ZIP.",
            self.combo_package_batch,
        ))

        row = QHBoxLayout()
        row.setSpacing(8)
        btn_export = QPushButton("Ekspor Paket")
        btn_export.setProperty("class", "btn-secondary")
        btn_export.setToolTip("Buat satu ZIP berisi PDF, crop denah, DWG, dan data batch")
        btn_export.clicked.connect(self._export_package)
        row.addWidget(btn_export)

        btn_import = QPushButton("Impor Paket")
        btn_import.setProperty("class", "btn-secondary")
        btn_import.setToolTip("Terima paket pekerjaan dari komputer lain")
        btn_import.clicked.connect(self._import_package)
        row.addWidget(btn_import)
        row.addStretch()
        card.body_layout.addLayout(row)
        return card

    def _build_about_section(self) -> QWidget:
        card = SectionCard("4. Tentang Aplikasi")
        name = QLabel(f"{APP_NAME} v{APP_VERSION}")
        name.setStyleSheet("font-size:16px;font-weight:800;color:#1E40AF;")
        card.body_layout.addWidget(name)
        sub = QLabel(APP_SUBTITLE)
        sub.setObjectName("PageSubtitle")
        card.body_layout.addWidget(sub)
        spec = QLabel(
            "Arsitektur: 100% offline lokal • Windows COM Automation • "
            "Penomoran identitas pertanahan standar"
        )
        spec.setObjectName("PageSubtitle")
        card.body_layout.addWidget(spec)
        return card

    def _browse_template(self):
        path, _ = QFileDialog.getOpenFileName(self, "Pilih Template DWG", "", "AutoCAD Drawing (*.dwg)")
        if path:
            self.input_tpl_path.setText(path)
            set_setting("template_dwg_path", path)
            QMessageBox.information(self, "Pengaturan Disimpan", f"Template DWG disetel ke:\n{path}")

    def _reset_default_template(self):
        self.input_tpl_path.setText(str(DEFAULT_TEMPLATE_PATH))
        set_setting("template_dwg_path", str(DEFAULT_TEMPLATE_PATH))
        QMessageBox.information(self, "Pengaturan Disimpan", "Lokasi template dikembalikan ke default aplikasi.")

    def _test_acad_connection(self):
        ok, msg = autocad_service.connect(launch_if_closed=True)
        self.lbl_test_result.setText(f"{'Berhasil' if ok else 'Gagal'}: {msg}")
        if ok:
            QMessageBox.information(self, "Koneksi AutoCAD Berhasil", msg)
        else:
            QMessageBox.warning(
                self, "Koneksi AutoCAD Gagal",
                f"{msg}\n\nPastikan AutoCAD 2021 terpasang, lisensi aktif, dan tidak ada dialog modal.",
            )

    def _backup_db(self):
        ok, result = create_database_backup()
        if ok:
            QMessageBox.information(self, "Backup Berhasil", f"Database disimpan di:\n{result}")
        else:
            QMessageBox.critical(self, "Backup Gagal", result)

    def _restore_db(self):
        path, _ = QFileDialog.getOpenFileName(self, "Pilih Backup Database", "", "Database Backup (*.db)")
        if not path:
            return
        reply = QMessageBox.question(
            self, "Pulihkan Database",
            "Data saat ini akan digantikan oleh berkas cadangan. Lanjutkan?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            ok, msg = restore_database_backup(path)
            if ok:
                QMessageBox.information(self, "Pemulihan Berhasil", msg)
            else:
                QMessageBox.critical(self, "Pemulihan Gagal", msg)

    def _export_package(self):
        batch_id = self.combo_package_batch.currentData()
        if not batch_id:
            QMessageBox.warning(self, "Tidak Ada Batch", "Belum ada batch yang bisa diekspor.")
            return
        batch = get_all_batches()
        batch = next((b for b in batch if b["id"] == batch_id), None)
        safe = (batch["nama_desa"] if batch else "Batch").replace(" ", "_")
        path, _ = QFileDialog.getSaveFileName(
            self, "Simpan Paket Pekerjaan", f"Paket_Batch_{safe}.zip", "ZIP Archives (*.zip)"
        )
        if not path:
            return
        ok, msg = export_work_package(batch_id, path)
        if ok:
            QMessageBox.information(self, "Ekspor Paket Berhasil", msg)
        else:
            QMessageBox.critical(self, "Ekspor Paket Gagal", msg)

    def _import_package(self):
        path, _ = QFileDialog.getOpenFileName(self, "Pilih Paket Pekerjaan", "", "ZIP Archives (*.zip)")
        if not path:
            return
        ok, msg = import_work_package(path)
        if ok:
            QMessageBox.information(self, "Impor Paket Berhasil", msg)
        else:
            QMessageBox.critical(self, "Impor Paket Gagal", msg)
