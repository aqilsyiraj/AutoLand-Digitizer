"""
AutoLand Digitizer - Batch Page (dengan Panduan & Form yang Jelas)
Manajemen batch pekerjaan berdasarkan desa atau wilayah kerja pertanahan.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QTableWidget, QTableWidgetItem, QHeaderView,
    QDateEdit, QTextEdit, QMessageBox, QSplitter
)
from PySide6.QtCore import Qt, QDate, Signal

from database.db import (
    create_batch, get_all_batches, get_batch, update_batch,
    delete_batch, get_batch_stats
)
from ui.components.guide_banner import GuideBanner

class BatchPage(QWidget):
    batch_changed = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.active_batch_id = None
        self.editing_batch_id = None
        self._setup_ui()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 20, 24, 24)
        main_layout.setSpacing(14)

        # Header
        header_layout = QVBoxLayout()
        header_layout.setSpacing(3)
        title = QLabel("Manajemen Batch Pekerjaan Wilayah")
        title.setStyleSheet("font-size: 20px; font-weight: 800; color: #0F172A;")
        header_layout.addWidget(title)

        subtitle = QLabel("Kelompokkan berkas digitalisasi dokumen pertanahan berdasarkan Desa/Kelurahan, Kecamatan, dan Kabupaten.")
        subtitle.setStyleSheet("color: #64748B; font-size: 13px;")
        header_layout.addWidget(subtitle)
        main_layout.addLayout(header_layout)

        # Panduan Menu Batch
        batch_guide = [
            "<b>Satu Batch = Satu Desa/Kelurahan:</b> Seluruh dokumen PDF dan hasil DWG akan dikelompokkan dalam satu folder batch.",
            "Isi formulir di sebelah kiri (Nama Desa, Kecamatan, Kabupaten, Tanggal, Operator) lalu klik <b>'Simpan Batch'</b>.",
            "Klik tombol hijau <b>'Pilih Aktif'</b> pada tabel sebelah kanan untuk menetapkan batch yang sedang Anda kerjakan.",
            "Setelah memilih batch aktif, silakan beralih ke menu <b>'Antrean Dokumen'</b> untuk mengimpor file PDF."
        ]
        self.guide_banner = GuideBanner("Petunjuk Penggunaan Batch Pekerjaan", batch_guide)
        main_layout.addWidget(self.guide_banner)

        # Splitter: Kiri Formulir Input, Kanan Daftar Batch
        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)

        # === PANEL KIRI: FORMULIR INPUT ===
        form_frame = QFrame()
        form_frame.setStyleSheet("""
            QFrame {
                background-color: #FFFFFF;
                border-radius: 8px;
                border: 1px solid #E2E8F0;
                padding: 16px;
            }
        """)
        form_layout = QVBoxLayout(form_frame)
        form_layout.setSpacing(10)

        self.lbl_form_title = QLabel("Formulir Batch Wilayah Baru")
        self.lbl_form_title.setStyleSheet("font-size: 14px; font-weight: 800; color: #1E293B;")
        form_layout.addWidget(self.lbl_form_title)

        # Nama Desa
        form_layout.addWidget(QLabel("Nama Desa / Kelurahan *"))
        self.input_desa = QLineEdit()
        self.input_desa.setPlaceholderText("Contoh: Sukamaju")
        form_layout.addWidget(self.input_desa)

        # Kecamatan
        form_layout.addWidget(QLabel("Kecamatan *"))
        self.input_kecamatan = QLineEdit()
        self.input_kecamatan.setPlaceholderText("Contoh: Cikarang Barat")
        form_layout.addWidget(self.input_kecamatan)

        # Kabupaten
        form_layout.addWidget(QLabel("Kabupaten / Kota *"))
        self.input_kabupaten = QLineEdit()
        self.input_kabupaten.setPlaceholderText("Contoh: Bekasi")
        form_layout.addWidget(self.input_kabupaten)

        # Tanggal Pekerjaan
        form_layout.addWidget(QLabel("Tanggal Pekerjaan *"))
        self.input_tanggal = QDateEdit()
        self.input_tanggal.setDate(QDate.currentDate())
        self.input_tanggal.setCalendarPopup(True)
        form_layout.addWidget(self.input_tanggal)

        # Operator (Opsional)
        form_layout.addWidget(QLabel("Nama Operator (Opsional)"))
        self.input_operator = QLineEdit()
        self.input_operator.setPlaceholderText("Contoh: Budi Santoso")
        form_layout.addWidget(self.input_operator)

        # Keterangan
        form_layout.addWidget(QLabel("Keterangan Tambahan"))
        self.input_keterangan = QTextEdit()
        self.input_keterangan.setPlaceholderText("Catatan proyek, nomor surat tugas, dll.")
        self.input_keterangan.setMaximumHeight(70)
        form_layout.addWidget(self.input_keterangan)

        # Tombol Simpan & Batal
        btn_layout = QHBoxLayout()
        self.btn_reset_form = QPushButton("Batal / Reset")
        self.btn_reset_form.setProperty("class", "btn-secondary")
        self.btn_reset_form.clicked.connect(self._reset_form)
        btn_layout.addWidget(self.btn_reset_form)

        self.btn_save_batch = QPushButton("Simpan Batch Wilayah")
        self.btn_save_batch.setStyleSheet("""
            QPushButton {
                background-color: #1E40AF;
                color: #FFFFFF;
                font-weight: 700;
                padding: 10px;
                border-radius: 6px;
            }
            QPushButton:hover { background-color: #1D4ED8; }
        """)
        self.btn_save_batch.clicked.connect(self._save_batch)
        btn_layout.addWidget(self.btn_save_batch)
        form_layout.addLayout(btn_layout)

        form_layout.addStretch()
        splitter.addWidget(form_frame)

        # === PANEL KANAN: DAFTAR BATCH ===
        list_frame = QFrame()
        list_frame.setStyleSheet("""
            QFrame {
                background-color: #FFFFFF;
                border-radius: 8px;
                border: 1px solid #E2E8F0;
                padding: 16px;
            }
        """)
        list_layout = QVBoxLayout(list_frame)
        list_layout.setSpacing(10)

        list_header = QHBoxLayout()
        list_title = QLabel("Daftar Batch Wilayah Terdaftar")
        list_title.setStyleSheet("font-size: 14px; font-weight: 800; color: #1E293B;")
        list_header.addWidget(list_title)
        list_header.addStretch()

        self.btn_refresh = QPushButton("Segarkan")
        self.btn_refresh.setProperty("class", "btn-secondary")
        self.btn_refresh.clicked.connect(self.load_data)
        list_header.addWidget(self.btn_refresh)
        list_layout.addLayout(list_header)

        self.table_batches = QTableWidget()
        self.table_batches.setColumnCount(7)
        self.table_batches.setHorizontalHeaderLabels([
            "ID", "Desa / Kelurahan", "Kecamatan", "Kabupaten", "Tanggal", "Progres Dokumen", "Aksi / Tindakan"
        ])
        self.table_batches.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table_batches.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table_batches.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table_batches.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table_batches.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table_batches.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.table_batches.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeToContents)
        self.table_batches.verticalHeader().setVisible(False)
        self.table_batches.setSelectionBehavior(QTableWidget.SelectRows)
        self.table_batches.setEditTriggers(QTableWidget.NoEditTriggers)
        list_layout.addWidget(self.table_batches)

        splitter.addWidget(list_frame)
        splitter.setSizes([330, 670])
        main_layout.addWidget(splitter, 1)

    def load_data(self):
        batches = get_all_batches()
        self.table_batches.setRowCount(len(batches))

        for row, b in enumerate(batches):
            b_id = b["id"]
            stats = get_batch_stats(b_id)

            item_id = QTableWidgetItem(str(b_id))
            item_id.setTextAlignment(Qt.AlignCenter)
            self.table_batches.setItem(row, 0, item_id)

            item_desa = QTableWidgetItem(b["nama_desa"])
            if b_id == self.active_batch_id:
                item_desa.setText(f"★ {b['nama_desa']} (Batch Aktif)")
                item_desa.setFont(item_desa.font())
                item_desa.setForeground(Qt.darkBlue)
            self.table_batches.setItem(row, 1, item_desa)

            self.table_batches.setItem(row, 2, QTableWidgetItem(b["kecamatan"]))
            self.table_batches.setItem(row, 3, QTableWidgetItem(b["kabupaten"]))

            item_tgl = QTableWidgetItem(b["tanggal"])
            item_tgl.setTextAlignment(Qt.AlignCenter)
            self.table_batches.setItem(row, 4, item_tgl)

            doc_str = f"{stats['selesai']} / {stats['total']} ({stats['persen']}%)"
            item_doc = QTableWidgetItem(doc_str)
            item_doc.setTextAlignment(Qt.AlignCenter)
            self.table_batches.setItem(row, 5, item_doc)

            # Tombol Aksi
            action_widget = QWidget()
            act_layout = QHBoxLayout(action_widget)
            act_layout.setContentsMargins(4, 2, 4, 2)
            act_layout.setSpacing(6)

            is_active = (b_id == self.active_batch_id)
            btn_select = QPushButton("✓ Aktif" if is_active else "Pilih Aktif")
            btn_select.setStyleSheet(f"""
                QPushButton {{
                    background-color: {'#059669' if is_active else '#2563EB'};
                    color: #FFFFFF;
                    font-weight: 700;
                    padding: 5px 12px;
                    border-radius: 5px;
                }}
            """)
            btn_select.setEnabled(not is_active)
            btn_select.setToolTip("Pilih batch ini untuk dikerjakan")
            btn_select.clicked.connect(lambda checked=False, id_=b_id: self._select_batch(id_))
            act_layout.addWidget(btn_select)

            btn_edit = QPushButton("Edit")
            btn_edit.setProperty("class", "btn-secondary")
            btn_edit.setToolTip("Ubah nama desa, kecamatan, atau operator")
            btn_edit.clicked.connect(lambda checked=False, id_=b_id: self._edit_batch(id_))
            act_layout.addWidget(btn_edit)

            btn_del = QPushButton("Hapus")
            btn_del.setProperty("class", "btn-danger")
            btn_del.setToolTip("Hapus batch dan seluruh berkas di dalamnya")
            btn_del.clicked.connect(lambda checked=False, id_=b_id: self._delete_batch(id_))
            act_layout.addWidget(btn_del)

            self.table_batches.setCellWidget(row, 6, action_widget)

    def _select_batch(self, batch_id: int):
        self.active_batch_id = batch_id
        self.load_data()
        self.batch_changed.emit(batch_id)

    def _save_batch(self):
        desa = self.input_desa.text().strip()
        kec = self.input_kecamatan.text().strip()
        kab = self.input_kabupaten.text().strip()
        tgl = self.input_tanggal.date().toString("yyyy-MM-dd")
        op = self.input_operator.text().strip()
        ket = self.input_keterangan.toPlainText().strip()

        if not desa or not kec or not kab:
            QMessageBox.warning(self, "Validasi Input", "Nama Desa, Kecamatan, dan Kabupaten wajib diisi!")
            return

        if self.editing_batch_id:
            update_batch(self.editing_batch_id, desa, kec, kab, tgl, op, ket)
            QMessageBox.information(self, "Sukses", f"Batch Desa '{desa}' berhasil diperbarui.")
            self.editing_batch_id = None
            self.lbl_form_title.setText("Formulir Batch Wilayah Baru")
            self.btn_save_batch.setText("Simpan Batch Wilayah")
        else:
            new_id = create_batch(desa, kec, kab, tgl, op, ket)
            self.active_batch_id = new_id
            self.batch_changed.emit(new_id)
            QMessageBox.information(
                self, "Batch Berhasil Dibuat",
                f"Batch Desa '{desa}' berhasil dibuat dan ditetapkan sebagai batch aktif!\n\n"
                "Silakan beralih ke menu 'Antrean Dokumen' untuk mulai mengimpor berkas PDF."
            )

        self._reset_form()
        self.load_data()

    def _edit_batch(self, batch_id: int):
        b = get_batch(batch_id)
        if not b:
            return
        self.editing_batch_id = batch_id
        self.lbl_form_title.setText(f"Edit Batch ID {batch_id}")
        self.btn_save_batch.setText("Perbarui Data Batch")

        self.input_desa.setText(b["nama_desa"])
        self.input_kecamatan.setText(b["kecamatan"])
        self.input_kabupaten.setText(b["kabupaten"])
        if b["tanggal"]:
            self.input_tanggal.setDate(QDate.fromString(b["tanggal"], "yyyy-MM-dd"))
        self.input_operator.setText(b.get("operator", "") or "")
        self.input_keterangan.setPlainText(b.get("keterangan", "") or "")

    def _delete_batch(self, batch_id: int):
        b = get_batch(batch_id)
        if not b:
            return
        reply = QMessageBox.question(
            self, "Konfirmasi Hapus Batch",
            f"Apakah Anda yakin ingin menghapus Batch Desa '{b['nama_desa']}'?\n\n"
            "PERINGATAN: Seluruh antrean dokumen, denah crop, dan data hasil digitasi di dalamnya akan ikut terhapus!",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            delete_batch(batch_id)
            if self.active_batch_id == batch_id:
                self.active_batch_id = None
                self.batch_changed.emit(0)
            self.load_data()

    def _reset_form(self):
        self.editing_batch_id = None
        self.lbl_form_title.setText("Formulir Batch Wilayah Baru")
        self.btn_save_batch.setText("Simpan Batch Wilayah")
        self.input_desa.clear()
        self.input_kecamatan.clear()
        self.input_kabupaten.clear()
        self.input_tanggal.setDate(QDate.currentDate())
        self.input_operator.clear()
        self.input_keterangan.clear()
