"""Manajemen batch wilayah: buat, pilih, ubah, dan hapus kelompok kerja desa."""

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QDateEdit,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from database.db import (
    create_batch,
    delete_batch,
    get_all_batches,
    get_batch,
    get_batch_stats,
    update_batch,
)
from ui.components.button import Button
from ui.components.data_table import DataTable, RowActions
from ui.components.form_field import FormField
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
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(14)

        layout.addWidget(
            PageHeader(
                "Batch / Desa",
                "Satu batch mewakili satu desa. Semua PDF dan DWG tersimpan di dalamnya.",
                eyebrow="Data Master",
            )
        )

        body = QHBoxLayout()
        body.setSpacing(14)

        left = QWidget()
        left.setFixedWidth(340)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(12)
        left_layout.addWidget(self._build_form())
        left_layout.addWidget(self._build_active_card())
        left_layout.addStretch(1)
        body.addWidget(left)

        body.addWidget(self._build_list(), 1)
        layout.addLayout(body, 1)

    # ------------------------------------------------------------------
    # Formulir
    # ------------------------------------------------------------------
    def _build_form(self) -> QWidget:
        card = SectionCard(
            "Formulir Batch", "Isi data wilayah lalu simpan sebagai batch aktif."
        )
        self.lbl_form_title = QLabel("Batch baru")
        self.lbl_form_title.setObjectName("SectionSubtitle")
        card.body_layout.addWidget(self.lbl_form_title)

        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)

        self.input_desa = QLineEdit()
        self.input_desa.setPlaceholderText("Contoh: Sukamaju")
        grid.addWidget(
            FormField(
                "Desa / Kelurahan", "Nama folder hasil DWG.",
                self.input_desa, required=True,
            ),
            0, 0, 1, 2,
        )

        self.input_kecamatan = QLineEdit()
        self.input_kecamatan.setPlaceholderText("Contoh: Cikarang Barat")
        grid.addWidget(
            FormField(
                "Kecamatan", "Wilayah administratif.",
                self.input_kecamatan, required=True,
            ),
            1, 0,
        )

        self.input_kabupaten = QLineEdit()
        self.input_kabupaten.setPlaceholderText("Contoh: Bekasi")
        grid.addWidget(
            FormField(
                "Kabupaten / Kota", "Wilayah atasnya.",
                self.input_kabupaten, required=True,
            ),
            1, 1,
        )

        self.input_tanggal = QDateEdit()
        self.input_tanggal.setDate(QDate.currentDate())
        self.input_tanggal.setCalendarPopup(True)
        grid.addWidget(
            FormField("Tanggal", "Pilih dari kalender.", self.input_tanggal, required=True),
            2, 0,
        )

        self.input_operator = QLineEdit()
        self.input_operator.setPlaceholderText("Contoh: Budi Santoso")
        grid.addWidget(
            FormField("Operator", "Opsional, dicatat di riwayat.", self.input_operator),
            2, 1,
        )

        self.input_keterangan = QTextEdit()
        self.input_keterangan.setPlaceholderText("Contoh: Surat tugas No. 470/123/2026")
        self.input_keterangan.setFixedHeight(64)
        grid.addWidget(
            FormField("Keterangan", "Opsional: nomor surat tugas / catatan.", self.input_keterangan),
            3, 0, 1, 2,
        )

        card.body_layout.addLayout(grid, 0)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        self.btn_reset_form = Button(
            "Kosongkan", size="sm", tone="secondary",
            tooltip="Hapus semua isian tanpa menyimpan",
        )
        self.btn_reset_form.clicked.connect(self._reset_form)
        buttons.addWidget(self.btn_reset_form)

        self.btn_save_batch = Button(
            "Simpan Batch", size="md", tone="primary",
            tooltip="Simpan batch baru atau perbarui batch yang sedang diedit",
        )
        self.btn_save_batch.clicked.connect(self._save_batch)
        buttons.addWidget(self.btn_save_batch, 1)
        card.body_layout.addLayout(buttons)
        return card

    def _build_active_card(self) -> QWidget:
        card = SectionCard(
            "Batch Aktif", "Batch yang menerima impor PDF berikutnya."
        )
        self.lbl_active_name = QLabel("Belum ada batch dipilih")
        self.lbl_active_name.setObjectName("ActiveSummaryName")
        self.lbl_active_name.setWordWrap(True)
        card.body_layout.addWidget(self.lbl_active_name)

        self.lbl_active_meta = QLabel("Pilih satu batch pada tabel di sebelah kanan.")
        self.lbl_active_meta.setObjectName("PageSubtitle")
        self.lbl_active_meta.setWordWrap(True)
        card.body_layout.addWidget(self.lbl_active_meta)

        self.active_progress = QProgressBar()
        self.active_progress.setRange(0, 100)
        self.active_progress.setValue(0)
        self.active_progress.setTextVisible(False)
        self.active_progress.setFixedHeight(8)
        card.body_layout.addWidget(self.active_progress)
        return card

    # ------------------------------------------------------------------
    # Daftar batch
    # ------------------------------------------------------------------
    def _build_list(self) -> QWidget:
        card = SectionCard(
            "Daftar Batch", "Pilih satu batch aktif sebelum mengimpor PDF."
        )
        self.input_search = QLineEdit()
        self.input_search.setPlaceholderText("Cari desa atau kecamatan…")
        self.input_search.setMinimumWidth(210)
        self.input_search.textChanged.connect(self.load_data)
        card.add_action(self.input_search)

        self.btn_refresh = Button(
            "Segarkan", size="sm", tone="secondary",
            tooltip="Muat ulang daftar batch dari database lokal",
        )
        self.btn_refresh.clicked.connect(self.load_data)
        card.add_action(self.btn_refresh)

        self.table_batches = DataTable(3)
        self.table_batches.setHorizontalHeaderLabels(
            ["Desa / Wilayah", "Progres Dokumen", "Aksi"]
        )
        self.table_batches.set_columns([0, 128, 240], stretch_column=0)
        self.table_batches.verticalHeader().setDefaultSectionSize(44)
        self.table_batches.set_empty_text(
            "Belum ada batch. Isi formulir di sebelah kiri untuk membuat batch pertama."
        )
        card.body_layout.addWidget(self.table_batches, 1)
        return card

    def load_data(self):
        query = self.input_search.text().strip().lower() if hasattr(self, "input_search") else ""
        batches = get_all_batches()
        if query:
            batches = [
                b for b in batches
                if query in str(b.get("nama_desa", "")).lower()
                or query in str(b.get("kecamatan", "")).lower()
                or query in str(b.get("kabupaten", "")).lower()
            ]
        self.table_batches.setRowCount(len(batches))

        for row, batch in enumerate(batches):
            b_id = batch["id"]
            stats = get_batch_stats(b_id)
            is_active = b_id == self.active_batch_id

            name = f"Desa {batch['nama_desa']} — Kec. {batch['kecamatan']}"
            item_desa = QTableWidgetItem(("●  " if is_active else "") + name)
            item_desa.setToolTip(
                f"Desa {batch['nama_desa']} — Kec. {batch['kecamatan']}, {batch['kabupaten']}"
            )
            if is_active:
                item_desa.setForeground(QColor("#0F766E"))
                font = QFont("Segoe UI", 9)
                font.setBold(True)
                item_desa.setFont(font)
            self.table_batches.setItem(row, 0, item_desa)

            progress = QTableWidgetItem(
                f"{stats['selesai']} / {stats['total']}  ({stats['persen']}%)"
            )
            progress.setTextAlignment(Qt.AlignCenter)
            self.table_batches.setItem(row, 1, progress)

            btn_select = Button(
                "Aktif" if is_active else "Pilih",
                size="xs",
                tone="success" if is_active else "primary",
                tooltip="Jadikan batch ini sebagai batch aktif",
            )
            btn_select.setEnabled(not is_active)
            btn_select.clicked.connect(
                lambda checked=False, id_=b_id: self._select_batch(id_)
            )

            btn_edit = Button(
                "Ubah", size="xs", tone="secondary",
                tooltip="Muat data batch ke formulir untuk diperbaiki",
            )
            btn_edit.clicked.connect(
                lambda checked=False, id_=b_id: self._edit_batch(id_)
            )

            btn_del = Button(
                "Hapus", size="xs", tone="danger",
                tooltip="Hapus batch beserta seluruh dokumen di dalamnya",
            )
            btn_del.clicked.connect(
                lambda checked=False, id_=b_id: self._delete_batch(id_)
            )

            self.table_batches.setCellWidget(
                row, 2, RowActions([btn_select, btn_edit, btn_del])
            )

        self._refresh_active_card()

    def _refresh_active_card(self):
        if not self.active_batch_id:
            self.lbl_active_name.setText("Belum ada batch dipilih")
            self.lbl_active_meta.setText("Pilih satu batch pada tabel di sebelah kanan.")
            self.active_progress.setValue(0)
            return
        batch = get_batch(self.active_batch_id)
        if not batch:
            self.lbl_active_name.setText("Batch aktif tidak ditemukan")
            self.lbl_active_meta.setText("Pilih batch lain pada tabel.")
            self.active_progress.setValue(0)
            return
        stats = get_batch_stats(self.active_batch_id)
        self.lbl_active_name.setText(f"Desa {batch['nama_desa']}")
        self.lbl_active_meta.setText(
            f"Kec. {batch['kecamatan']}, {batch['kabupaten']} · "
            f"{stats['selesai']} dari {stats['total']} dokumen selesai."
        )
        self.active_progress.setValue(int(stats["persen"]))

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
                self,
                "Data Belum Lengkap",
                "Nama Desa, Kecamatan, dan Kabupaten wajib diisi.",
            )
            return

        tgl = self.input_tanggal.date().toString("yyyy-MM-dd")
        operator = self.input_operator.text().strip()
        keterangan = self.input_keterangan.toPlainText().strip()

        if self.editing_batch_id:
            update_batch(
                self.editing_batch_id, desa, kec, kab, tgl, operator, keterangan
            )
            QMessageBox.information(
                self, "Batch Diperbarui",
                f"Data batch Desa {desa} berhasil diperbarui.",
            )
            self.editing_batch_id = None
        else:
            new_id = create_batch(desa, kec, kab, tgl, operator, keterangan)
            self.active_batch_id = new_id
            self.batch_changed.emit(new_id)
            QMessageBox.information(
                self,
                "Batch Berhasil Dibuat",
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
            self,
            "Hapus Batch",
            f"Hapus batch Desa {batch['nama_desa']}?\n\n"
            "Seluruh antrean dokumen, denah crop, dan hasil digitasi ikut terhapus.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
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
