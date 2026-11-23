"""Pengaturan: template DWG, koneksi AutoCAD, backup data, dan paket offline."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from config import (
    APP_NAME,
    APP_SUBTITLE,
    APP_VERSION,
    DB_PATH,
    DEFAULT_TEMPLATE_PATH,
    STATUS_SELESAI,
)
from database.db import get_all_batches, get_all_documents, get_setting, set_setting
from services.autocad_service import autocad_service
from services.backup_service import (
    create_database_backup,
    export_work_package,
    import_work_package,
    restore_database_backup,
)
from ui.components.button import Button
from ui.components.form_field import InlineField
from ui.components.guide_banner import GuideBanner
from ui.components.page_header import PageHeader
from ui.components.section_card import SectionCard
from ui.components.stat_card import StatCard
from ui.motion.qt_motion import fade_in, pulse, SmoothScrollArea


class SettingsPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(14)

        layout.addWidget(
            PageHeader(
                "Pengaturan",
                "Template DWG, koneksi AutoCAD 2021, cadangan data, dan paket offline.",
                eyebrow="Sistem",
            )
        )

        # ---------- Status sistem ----------
        stats = QHBoxLayout()
        stats.setSpacing(12)
        self.card_batches = StatCard("Batch", "0", "Wilayah terdaftar", "#1D4ED8")
        self.card_docs = StatCard("Dokumen", "0", "Total di database", "#0F766E")
        self.card_db = StatCard("Ukuran database", "0", "SQLite lokal", "#B45309")
        self.card_acad = StatCard("AutoCAD 2021", "Offline", "Status koneksi", "#64748B")
        for card in (
            self.card_batches,
            self.card_docs,
            self.card_db,
            self.card_acad,
        ):
            stats.addWidget(card, 1)
        layout.addLayout(stats)

        layout.addWidget(
            GuideBanner(
                "Sebelum mulai",
                [
                    "Aplikasi terhubung langsung ke <b>AutoCAD Desktop 2021</b> melalui COM.",
                    "Jika template kantor belum tersedia, DWG baru dibuat otomatis.",
                    "Lakukan <b>Cadangkan Database</b> secara berkala.",
                    "Gunakan paket offline untuk memindahkan satu batch tanpa internet.",
                ],
            )
        )

        # ---------- Kartu pengaturan ----------
        scroll = SmoothScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background:transparent;border:none;")
        container = QWidget()
        grid = QGridLayout(container)
        grid.setContentsMargins(0, 0, 4, 0)
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(14)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)

        grid.addWidget(self._build_autocad_section(), 0, 0, 1, 2)
        grid.addWidget(self._build_backup_section(), 1, 0)
        grid.addWidget(self._build_package_section(), 1, 1)
        grid.addWidget(self._build_about_section(), 2, 0, 1, 2)
        grid.setRowStretch(3, 1)

        scroll.setWidget(container)
        layout.addWidget(scroll, 1)
        fade_in(scroll, duration=240)

        self._refresh_status()

    def _refresh_status(self):
        batches = get_all_batches()
        documents = get_all_documents()
        selesai = sum(1 for d in documents if d.get("status") == STATUS_SELESAI)
        self.card_batches.set_value(str(len(batches)))
        self.card_docs.set_value(str(len(documents)), f"{selesai} dokumen selesai")

        db_size = "—"
        try:
            size_bytes = DB_PATH.stat().st_size if DB_PATH.exists() else 0
            db_size = f"{size_bytes / 1024:.1f} KB"
        except Exception:
            pass
        self.card_db.set_value(db_size)

        status = autocad_service.get_status()
        connected = bool(status.get("connected"))
        self.card_acad.set_value("Terhubung" if connected else "Offline")
        self.card_acad.value_label.setProperty("tone", "success" if connected else "muted")
        self.card_acad.value_label.style().unpolish(self.card_acad.value_label)
        self.card_acad.value_label.style().polish(self.card_acad.value_label)
        self.card_acad.setToolTip(
            status.get("version") or status.get("error") or "AutoCAD Desktop 2021"
        )

    def _build_autocad_section(self) -> QWidget:
        card = SectionCard(
            "1. AutoCAD & Template DWG",
            "Koneksi langsung ke AutoCAD Desktop 2021. Template resmi kantor bersifat opsional.",
        )
        self.input_tpl_path = QLineEdit()
        self.input_tpl_path.setText(
            get_setting("template_dwg_path", str(DEFAULT_TEMPLATE_PATH))
        )
        card.body_layout.addWidget(
            InlineField(
                "Template DWG",
                "Lokasi file .dwg resmi. Kosong/placeholder berarti DWG baru dibuat otomatis.",
                self.input_tpl_path,
            )
        )

        browse = QHBoxLayout()
        browse.setSpacing(8)
        browse.addWidget(
            Button(
                "Pilih File DWG",
                size="sm",
                tone="secondary",
                tooltip="Cari file template DWG lalu simpan lokasinya",
                on_click=self._browse_template,
            )
        )
        browse.addWidget(
            Button(
                "Gunakan Default",
                size="sm",
                tone="secondary",
                tooltip="Kembalikan lokasi template ke folder bawaan aplikasi",
                on_click=self._reset_default_template,
            )
        )
        browse.addStretch()
        card.body_layout.addLayout(browse)

        test = QHBoxLayout()
        test.setSpacing(10)
        test.addWidget(
            Button(
                "Uji Koneksi AutoCAD",
                size="md",
                tone="primary",
                tooltip="Hubungkan ke AutoCAD Desktop 2021 yang berjalan atau jalankan aplikasinya",
                on_click=self._test_acad_connection,
            )
        )
        self.lbl_test_result = QLabel("Status: belum diuji")
        self.lbl_test_result.setObjectName("PageSubtitle")
        self.lbl_test_result.setWordWrap(True)
        test.addWidget(self.lbl_test_result, 1)
        card.body_layout.addLayout(test)
        return card

    def _build_backup_section(self) -> QWidget:
        card = SectionCard(
            "2. Database & Cadangan", "Data disimpan di komputer ini."
        )
        path = QLabel(f"File database: <b>{DB_PATH}</b>")
        path.setObjectName("PageSubtitle")
        path.setTextFormat(Qt.RichText)
        path.setWordWrap(True)
        card.body_layout.addWidget(path)

        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(
            Button(
                "Cadangkan Database",
                size="sm",
                tone="success",
                tooltip="Simpan salinan database SQLite ke folder backup",
                on_click=self._backup_db,
            )
        )
        row.addWidget(
            Button(
                "Pulihkan (.db)",
                size="sm",
                tone="warn",
                tooltip="Ganti database saat ini dengan berkas cadangan",
                on_click=self._restore_db,
            )
        )
        row.addStretch()
        card.body_layout.addLayout(row)
        card.body_layout.addStretch(1)
        return card

    def _build_package_section(self) -> QWidget:
        card = SectionCard(
            "3. Paket Pekerjaan",
            "Pindahkan satu batch ke komputer lain lewat flashdisk.",
        )
        self.combo_package_batch = QComboBox()
        for batch in get_all_batches():
            self.combo_package_batch.addItem(
                f"Desa {batch['nama_desa']} ({batch['kecamatan']}) — ID {batch['id']}",
                batch["id"],
            )
        if self.combo_package_batch.count() == 0:
            self.combo_package_batch.addItem("Belum ada batch", None)
        card.body_layout.addWidget(
            InlineField(
                "Batch",
                "Pilih batch yang akan dimasukkan ke paket ZIP.",
                self.combo_package_batch,
            )
        )

        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(
            Button(
                "Ekspor Paket",
                size="sm",
                tone="secondary",
                tooltip="Buat ZIP berisi PDF, crop denah, DWG, dan data batch",
                on_click=self._export_package,
            )
        )
        row.addWidget(
            Button(
                "Impor Paket",
                size="sm",
                tone="secondary",
                tooltip="Terima paket pekerjaan dari komputer lain",
                on_click=self._import_package,
            )
        )
        row.addStretch()
        card.body_layout.addLayout(row)
        card.body_layout.addStretch(1)
        return card

    def _build_about_section(self) -> QWidget:
        card = SectionCard("4. Tentang Aplikasi")
        row = QHBoxLayout()
        row.setSpacing(18)

        left = QVBoxLayout()
        left.setSpacing(2)
        name = QLabel(f"{APP_NAME} v{APP_VERSION}")
        name.setObjectName("SectionTitle")
        left.addWidget(name)
        sub = QLabel(APP_SUBTITLE)
        sub.setObjectName("PageSubtitle")
        sub.setWordWrap(True)
        left.addWidget(sub)
        row.addLayout(left, 1)

        spec = QLabel(
            "Arsitektur: 100% offline lokal • Windows COM Automation • "
            "Penomoran identitas pertanahan standar"
        )
        spec.setObjectName("PageSubtitle")
        spec.setWordWrap(True)
        spec.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        row.addWidget(spec, 1)
        card.body_layout.addLayout(row)
        return card

    def _browse_template(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Pilih Template DWG", "", "AutoCAD Drawing (*.dwg)"
        )
        if path:
            self.input_tpl_path.setText(path)
            set_setting("template_dwg_path", path)
            QMessageBox.information(
                self, "Pengaturan Disimpan", f"Template DWG disetel ke:\n{path}"
            )

    def _reset_default_template(self):
        self.input_tpl_path.setText(str(DEFAULT_TEMPLATE_PATH))
        set_setting("template_dwg_path", str(DEFAULT_TEMPLATE_PATH))
        QMessageBox.information(
            self,
            "Pengaturan Disimpan",
            "Lokasi template dikembalikan ke default aplikasi.",
        )

    def _test_acad_connection(self):
        ok, msg = autocad_service.connect(launch_if_closed=True)
        self.lbl_test_result.setText(f"{'Berhasil' if ok else 'Gagal'}: {msg}")
        self._refresh_status()
        if ok:
            pulse(self.lbl_test_result, cycles=1)
            QMessageBox.information(self, "Koneksi AutoCAD Berhasil", msg)
        else:
            QMessageBox.warning(
                self,
                "Koneksi AutoCAD Gagal",
                f"{msg}\n\nPastikan AutoCAD 2021 terpasang, lisensi aktif, "
                "dan tidak ada dialog modal.",
            )

    def _backup_db(self):
        ok, result = create_database_backup()
        if ok:
            QMessageBox.information(
                self, "Backup Berhasil", f"Database disimpan di:\n{result}"
            )
        else:
            QMessageBox.critical(self, "Backup Gagal", result)

    def _restore_db(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Pilih Backup Database", "", "Database Backup (*.db)"
        )
        if not path:
            return
        reply = QMessageBox.question(
            self,
            "Pulihkan Database",
            "Data saat ini akan digantikan oleh berkas cadangan. Lanjutkan?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
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
            QMessageBox.warning(
                self, "Tidak Ada Batch", "Belum ada batch yang bisa diekspor."
            )
            return
        batches = get_all_batches()
        batch = next((b for b in batches if b["id"] == batch_id), None)
        safe = (batch["nama_desa"] if batch else "Batch").replace(" ", "_")
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Simpan Paket Pekerjaan",
            f"Paket_Batch_{safe}.zip",
            "ZIP Archives (*.zip)",
        )
        if not path:
            return
        ok, msg = export_work_package(batch_id, path)
        if ok:
            QMessageBox.information(self, "Ekspor Paket Berhasil", msg)
        else:
            QMessageBox.critical(self, "Ekspor Paket Gagal", msg)

    def _import_package(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Pilih Paket Pekerjaan", "", "ZIP Archives (*.zip)"
        )
        if not path:
            return
        ok, msg = import_work_package(path)
        if ok:
            QMessageBox.information(self, "Impor Paket Berhasil", msg)
        else:
            QMessageBox.critical(self, "Impor Paket Gagal", msg)
