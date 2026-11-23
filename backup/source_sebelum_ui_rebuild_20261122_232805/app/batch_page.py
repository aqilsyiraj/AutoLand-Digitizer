"""Manajemen batch wilayah: buat, pilih, ubah, dan hapus kelompok kerja desa."""

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtWidgets import (
    QDateEdit, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton,
    QSplitter, QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget,
)

from database.db import (
    create_batch, delete_batch, get_all_batches, get_batch,
    get_batch_stats, update_batch,
)
from ui.components.data_table import DataTable
from ui.components.form_field import FormField
from ui.components.guide_banner import GuideBanner
from ui.components.page_header import PageHeader
from ui.components.section_card import SectionCard


class BatchPage(QWidget):
    batch_changed = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.active_batch_id = None
        self.editing_batch_id = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 12, 18, 12)
        layout.setSpacing(8)
        layout.addWidget(PageHeader(
            "Batch / Desa",
            "Satu batch mewakili satu desa atau kelurahan. Semua PDF dan DWG tersimpan di dalamnya.",
        ))

        layout.addWidget(GuideBanner("Cara kerja batch", [
            "Isi formulir di sebelah kiri, lalu klik <b>Simpan Batch</b>. Tiga kolom pertama wajib diisi.",
            "Klik <b>Pilih</b> pada tabel untuk menetapkan batch yang sedang dikerjakan.",
            "Batch aktif ditandai di sidebar dan dipakai saat mengimpor PDF.",
            "Gunakan <b>Ubah</b> untuk memperbaiki data dan <b>Hapus</b> untuk menghapus batch beserta isinya.",
        ]))

        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self._build_form())
        splitter.addWidget(self._build_list())
        splitter.setSizes([330, 760])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter, 1)

    def _build_form(self) -> QWidget:
        card = SectionCard("Formulir Batch Wilayah")
        self.lbl_form_title = QLabel("Batch baru")
        self.lbl_form_title.setObjectName("SectionSubtitle")
        card.body_layout.addWidget(self.lbl_form_title)

        self.input_desa = QLineEdit()
        self.input_desa.setPlaceholderText("Contoh: Sukamaju")
        card.body_layout.addWidget(FormField(
            "Nama Desa / Kelurahan",
            "Nama folder hasil DWG.",
            self.input_desa, required=True,
        ))

        self.input_kecamatan = QLineEdit()
        self.input_kecamatan.setPlaceholderText("Contoh: Cikarang Barat")
        card.body_layout.addWidget(FormField(
            "Kecamatan", "Wilayah administratif desa.",
            self.input_kecamatan, required=True,
        ))

        self.input_kabupaten = QLineEdit()
        self.input_kabupaten.setPlaceholderText("Contoh: Bekasi")
        card.body_layout.addWidget(FormField(
            "Kabupaten / Kota", "Wilayah administratif atasnya.",
            self.input_kabupaten, required=True,
        ))

        self.input_tanggal = QDateEdit()
        self.input_tanggal.setDate(QDate.currentDate())
        self.input_tanggal.setCalendarPopup(True)
        card.body_layout.addWidget(FormField(
            "Tanggal Pekerjaan", "Klik untuk memilih dari kalender.",
            self.input_tanggal, required=True,
        ))

        self.input_operator = QLineEdit()
        self.input_operator.setPlaceholderText("Contoh: Budi Santoso")
        card.body_layout.addWidget(FormField(
            "Nama Operator", "Opsional. Dicatat pada riwayat.",
            self.input_operator,
        ))

        self.input_keterangan = QTextEdit()
        self.input_keterangan.setPlaceholderText("Contoh: Surat tugas No. 470/123/2026")
        self.input_keterangan.setMaximumHeight(64)
        card.body_layout.addWidget(FormField(
            "Keterangan Tambahan", "Opsional. Nomor surat tugas / catatan.",
            self.input_keterangan,
        ))

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        self.btn_reset_form = QPushButton("Kosongkan")
        self.btn_reset_form.setProperty("class", "btn-secondary")
        self.btn_reset_form.setToolTip("Hapus semua isian tanpa menyimpan")
        self.btn_reset_form.clicked.connect(self._reset_form)
        buttons.addWidget(self.btn_reset_form)

        self.btn_save_batch = QPushButton("Simpan Batch")
        self.btn_save_batch.setProperty("class", "btn-primary")
        self.btn_save_batch.setToolTip("Simpan batch baru atau perbarui batch yang sedang diedit")
        self.btn_save_batch.clicked.connect(self._save_batch)
        buttons.addWidget(self.btn_save_batch)
        card.body_layout.addLayout(buttons)
        card.body_layout.addStretch()
        return card

    def _build_list(self) -> QWidget:
        card = SectionCard("Daftar Batch Terdaftar", "Pilih satu batch aktif sebelum mengimpor PDF.")
        header = QHBoxLayout()
        header.addStretch()
        self.btn_refresh = QPushButton("Segarkan")
        self.btn_refresh.setProperty("class", "btn-secondary")
        self.btn_refresh.setToolTip("Muat ulang daftar batch dari database lokal")
        self.btn_refresh.clicked.connect(self.load_data)
        header.addWidget(self.btn_refresh)
        card.body_layout.addLayout(header)

        self.table_batches = DataTable(3)
        self.table_batches.setHorizontalHeaderLabels([
            "Desa / Wilayah", "Progres Dokumen", "Aksi",
        ])
        self.table_batches.set_columns([0, 100, 280], stretch_column=0)
        self.table_batches.verticalHeader().setDefaultSectionSize(48)
        self.table_batches.set_empty_text("Belum ada batch. Isi formulir di sebelah kiri untuk membuat batch pertama.")
        card.body_layout.addWidget(self.table_batches, 1)
        return card

    def load_data(self):
        batches = get_all_batches()
        self.table_batches.setRowCount(len(batches))

        for row, batch in enumerate(batches):
            b_id = batch["id"]
            stats = get_batch_stats(b_id)
            is_active = b_id == self.active_batch_id

            name = (
                f"Desa {batch['nama_desa']}\n"
                f"Kec. {batch['kecamatan']}"
                + ("  • AKTIF" if is_active else "")
            )
            item_desa = QTableWidgetItem(name)
            item_desa.setToolTip(
                f"Desa {batch['nama_desa']} — Kec. {batch['kecamatan']}, {batch['kabupaten']}"
            )
            if is_active:
                item_desa.setForeground(Qt.darkBlue)
            self.table_batches.setItem(row, 0, item_desa)

            progress = QTableWidgetItem(f"{stats['selesai']} / {stats['total']} ({stats['persen']}%)")
            progress.setTextAlignment(Qt.AlignCenter)
            self.table_batches.setItem(row, 1, progress)

            actions = QWidget()
            row_actions = QHBoxLayout(actions)
            row_actions.setContentsMargins(2, 1, 2, 1)
            row_actions.setSpacing(4)

            btn_select = QPushButton("Aktif" if is_active else "Pilih")
            btn_select.setProperty("class", "btn-row")
            btn_select.setProperty("role", "success" if is_active else "primary")
            btn_select.setEnabled(not is_active)
            btn_select.setToolTip("Jadikan batch ini sebagai batch aktif")
            btn_select.clicked.connect(lambda checked=False, id_=b_id: self._select_batch(id_))
            row_actions.addWidget(btn_select)

            btn_edit = QPushButton("Ubah")
            btn_edit.setProperty("class", "btn-row")
            btn_edit.setProperty("role", "secondary")
            btn_edit.setToolTip("Muat data batch ke formulir untuk diperbaiki")
            btn_edit.clicked.connect(lambda checked=False, id_=b_id: self._edit_batch(id_))
            row_actions.addWidget(btn_edit)

            btn_del = QPushButton("Hapus")
            btn_del.setProperty("class", "btn-row")
            btn_del.setProperty("role", "danger")
            btn_del.setToolTip("Hapus batch beserta seluruh dokumen di dalamnya")
            btn_del.clicked.connect(lambda checked=False, id_=b_id: self._delete_batch(id_))
            row_actions.addWidget(btn_del)
            self.table_batches.setCellWidget(row, 2, actions)

    def _select_batch(self, batch_id: int):
        self.active_batch_id = batch_id
        self.load_data()
        self.batch_changed.emit(batch_id)

    def _save_batch(self):
        desa = self.input_desa.text().strip()
        kec = self.input_kecamatan.text().strip()
        kab = self.input_kabupaten.text().strip()
        if not desa or not kec or not kab:
            QMessageBox.warning(
                self, "Data Belum Lengkap",
                "Nama Desa, Kecamatan, dan Kabupaten wajib diisi.",
            )
            return

        tgl = self.input_tanggal.date().toString("yyyy-MM-dd")
        operator = self.input_operator.text().strip()
        keterangan = self.input_keterangan.toPlainText().strip()

        if self.editing_batch_id:
            update_batch(self.editing_batch_id, desa, kec, kab, tgl, operator, keterangan)
            QMessageBox.information(self, "Batch Diperbarui", f"Data batch Desa {desa} berhasil diperbarui.")
            self.editing_batch_id = None
        else:
            new_id = create_batch(desa, kec, kab, tgl, operator, keterangan)
            self.active_batch_id = new_id
            self.batch_changed.emit(new_id)
            QMessageBox.information(
                self, "Batch Berhasil Dibuat",
                f"Batch Desa {desa} dibuat dan ditetapkan sebagai batch aktif.\n\n"
                "Lanjut ke menu '3. PDF & Antrean' untuk mengimpor dokumen.",
            )

        self._reset_form()
        self.load_data()

    def _edit_batch(self, batch_id: int):
        batch = get_batch(batch_id)
        if not batch:
            return
        self.editing_batch_id = batch_id
        self.lbl_form_title.setText(f"Mengubah Batch ID {batch_id}")
        self.btn_save_batch.setText("Perbarui Batch")

        self.input_desa.setText(batch["nama_desa"])
        self.input_kecamatan.setText(batch["kecamatan"])
        self.input_kabupaten.setText(batch["kabupaten"])
        if batch.get("tanggal"):
            self.input_tanggal.setDate(QDate.fromString(batch["tanggal"], "yyyy-MM-dd"))
        self.input_operator.setText(batch.get("operator") or "")
        self.input_keterangan.setPlainText(batch.get("keterangan") or "")

    def _delete_batch(self, batch_id: int):
        batch = get_batch(batch_id)
        if not batch:
            return
        reply = QMessageBox.question(
            self, "Hapus Batch",
            f"Hapus batch Desa {batch['nama_desa']}?\n\n"
            "Seluruh antrean dokumen, denah crop, dan hasil digitasi ikut terhapus.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            delete_batch(batch_id)
            if self.active_batch_id == batch_id:
                self.active_batch_id = None
                self.batch_changed.emit(0)
            self.load_data()

    def _reset_form(self):
        self.editing_batch_id = None
        self.lbl_form_title.setText("Batch baru")
        self.btn_save_batch.setText("Simpan Batch")
        self.input_desa.clear()
        self.input_kecamatan.clear()
        self.input_kabupaten.clear()
        self.input_tanggal.setDate(QDate.currentDate())
        self.input_operator.clear()
        self.input_keterangan.clear()
