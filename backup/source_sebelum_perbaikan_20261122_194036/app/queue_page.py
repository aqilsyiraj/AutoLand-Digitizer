"""
AutoLand Digitizer - Queue Page (Antrean Dokumen yang Ditingkatkan)
Dilengkapi panduan penggunaan interaktif, ringkasan status batch, tombol aksi yang jelas dan mudah dipahami,
serta indikator status pengerjaan yang ramah pengguna.
"""

import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QTableWidget, QTableWidgetItem, QHeaderView,
    QComboBox, QMessageBox, QFileDialog
)
from PySide6.QtCore import Qt, Signal

from config import STATUS_LIST, STATUS_MENUNGGU, STATUS_SELESAI, DOKUMEN_MASUK_DIR
from database.db import (
    get_documents_by_batch, get_document, delete_document,
    create_document, get_batch, get_batch_stats
)
from ui.components.status_badge import StatusBadge
from ui.components.guide_banner import GuideBanner

class QueuePage(QWidget):
    start_process_doc = Signal(int) # Kirim ID dokumen untuk mulai digitasi
    navigate_to_digitize = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.active_batch_id = None
        self._setup_ui()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 20, 24, 24)
        main_layout.setSpacing(14)

        # 1. Header & Tombol Import
        header_layout = QHBoxLayout()
        header_text = QVBoxLayout()
        header_text.setSpacing(3)
        title = QLabel("Antrean Dokumen Pertanahan")
        title.setStyleSheet("font-size: 20px; font-weight: 800; color: #0F172A;")
        header_text.addWidget(title)

        self.lbl_batch_info = QLabel("Pilih batch pekerjaan terlebih dahulu")
        self.lbl_batch_info.setStyleSheet("color: #64748B; font-size: 13px;")
        header_text.addWidget(self.lbl_batch_info)
        header_layout.addLayout(header_text)

        header_layout.addStretch()

        self.btn_import_pdf = QPushButton("+ Import File PDF...")
        self.btn_import_pdf.setProperty("class", "btn-primary")
        self.btn_import_pdf.setStyleSheet("""
            QPushButton {
                background-color: #1E40AF;
                color: #FFFFFF;
                font-size: 13px;
                font-weight: 700;
                padding: 10px 18px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #1D4ED8;
            }
        """)
        self.btn_import_pdf.clicked.connect(self._import_pdf_dialog)
        header_layout.addWidget(self.btn_import_pdf)

        main_layout.addLayout(header_layout)

        # 2. Banner Petunjuk Penggunaan Menu Antrean
        queue_instructions = [
            "Klik tombol biru <b>'+ Import File PDF...'</b> di pojok kanan atas untuk memasukkan satu atau beberapa file PDF scan tanah.",
            "Klik tombol hijau <b>'▶ Mulai Digitasi'</b> pada baris dokumen untuk memulai alur pemotongan denah, input hak, dan tracing AutoCAD.",
            "Jika dokumen telah selesai diproses (status <b>SELESAI</b>), tombol <b>'📁 Buka DWG'</b> akan aktif untuk membuka gambar di AutoCAD.",
            "Gunakan kolom <b>Pencarian</b> atau <b>Filter Status</b> untuk menyaring dokumen yang sedang dikerjakan atau belum selesai."
        ]
        self.guide_banner = GuideBanner("Petunjuk Penggunaan Antrean Dokumen", queue_instructions)
        main_layout.addWidget(self.guide_banner)

        # 3. Bar Ringkasan Metrik Batch Cepat
        self.summary_bar = QFrame()
        self.summary_bar.setStyleSheet("""
            QFrame {
                background-color: #FFFFFF;
                border: 1px solid #E2E8F0;
                border-radius: 8px;
                padding: 6px 14px;
            }
        """)
        sb_layout = QHBoxLayout(self.summary_bar)
        sb_layout.setContentsMargins(10, 4, 10, 4)
        sb_layout.setSpacing(20)

        self.lbl_stat_total = QLabel("Total Dokumen: <b>0</b>")
        self.lbl_stat_total.setStyleSheet("color: #1E293B; font-size: 12px;")
        sb_layout.addWidget(self.lbl_stat_total)

        self.lbl_stat_selesai = QLabel("Selesai: <b style='color:#059669;'>0</b>")
        self.lbl_stat_selesai.setStyleSheet("color: #1E293B; font-size: 12px;")
        sb_layout.addWidget(self.lbl_stat_selesai)

        self.lbl_stat_sisa = QLabel("Belum Selesai: <b style='color:#D97706;'>0</b>")
        self.lbl_stat_sisa.setStyleSheet("color: #1E293B; font-size: 12px;")
        sb_layout.addWidget(self.lbl_stat_sisa)

        sb_layout.addStretch()

        # Filter & Search Controls
        lbl_cari = QLabel("Cari:")
        lbl_cari.setStyleSheet("font-weight: 600; color: #475569; font-size: 12px;")
        sb_layout.addWidget(lbl_cari)

        self.input_search = QLineEdit()
        self.input_search.setPlaceholderText("Ketik nama file, nomor hak...")
        self.input_search.setFixedWidth(200)
        self.input_search.textChanged.connect(self.load_data)
        sb_layout.addWidget(self.input_search)

        lbl_filter = QLabel("Status:")
        lbl_filter.setStyleSheet("font-weight: 600; color: #475569; font-size: 12px;")
        sb_layout.addWidget(lbl_filter)

        self.combo_status = QComboBox()
        self.combo_status.addItem("SEMUA")
        for s in STATUS_LIST:
            self.combo_status.addItem(s)
        self.combo_status.currentTextChanged.connect(self.load_data)
        sb_layout.addWidget(self.combo_status)

        self.btn_refresh = QPushButton("Segarkan")
        self.btn_refresh.setProperty("class", "btn-secondary")
        self.btn_refresh.clicked.connect(self.load_data)
        sb_layout.addWidget(self.btn_refresh)

        main_layout.addWidget(self.summary_bar)

        # 4. Tabel Antrean Dokumen
        self.table_queue = QTableWidget()
        self.table_queue.setColumnCount(8)
        self.table_queue.setHorizontalHeaderLabels([
            "No", "Nama File PDF", "Identitas Resmi Dokumen", "Luas Dokumen (m²)",
            "Luas Tracing (m²)", "Faktor Scaling", "Status Pengerjaan", "Aksi / Tindakan"
        ])
        self.table_queue.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table_queue.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table_queue.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table_queue.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table_queue.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table_queue.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.table_queue.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeToContents)
        self.table_queue.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeToContents)
        self.table_queue.verticalHeader().setVisible(False)
        self.table_queue.setSelectionBehavior(QTableWidget.SelectRows)
        self.table_queue.setEditTriggers(QTableWidget.NoEditTriggers)

        main_layout.addWidget(self.table_queue, 1)

    def set_active_batch(self, batch_id: int):
        self.active_batch_id = batch_id
        if batch_id:
            b = get_batch(batch_id)
            if b:
                self.lbl_batch_info.setText(f"Batch Aktif: <b>Desa {b['nama_desa']}</b>, Kec. {b['kecamatan']} ({b['kabupaten']})")
                self.btn_import_pdf.setEnabled(True)
            else:
                self.lbl_batch_info.setText("Batch tidak ditemukan.")
                self.btn_import_pdf.setEnabled(False)
        else:
            self.lbl_batch_info.setText("Silakan pilih batch aktif pada menu 'Batch Pekerjaan'.")
            self.btn_import_pdf.setEnabled(False)
        self.load_data()

    def load_data(self):
        """Memuat daftar dokumen pada batch aktif dengan tombol aksi yang jelas."""
        if not self.active_batch_id:
            self.table_queue.setRowCount(0)
            self.lbl_stat_total.setText("Total Dokumen: <b>0</b>")
            self.lbl_stat_selesai.setText("Selesai: <b style='color:#059669;'>0</b>")
            self.lbl_stat_sisa.setText("Belum Selesai: <b style='color:#D97706;'>0</b>")
            return

        # Update ringkasan statistik
        stats = get_batch_stats(self.active_batch_id)
        self.lbl_stat_total.setText(f"Total Dokumen: <b>{stats['total']}</b>")
        self.lbl_stat_selesai.setText(f"Selesai: <b style='color:#059669;'>{stats['selesai']}</b>")
        self.lbl_stat_sisa.setText(f"Belum Selesai: <b style='color:#D97706;'>{stats['sisa']}</b>")

        status_filter = self.combo_status.currentText()
        search_query = self.input_search.text().strip()

        docs = get_documents_by_batch(self.active_batch_id, status_filter=status_filter, search_query=search_query)
        self.table_queue.setRowCount(len(docs))

        for row, doc in enumerate(docs):
            doc_id = doc["id"]
            status = doc.get("status", STATUS_MENUNGGU)
            is_completed = (status == STATUS_SELESAI)

            # 0. No
            item_no = QTableWidgetItem(str(row + 1))
            item_no.setTextAlignment(Qt.AlignCenter)
            self.table_queue.setItem(row, 0, item_no)

            # 1. Nama PDF
            item_pdf = QTableWidgetItem(doc["nama_pdf"])
            self.table_queue.setItem(row, 1, item_pdf)

            # 2. Identitas Dokumen
            identitas = doc.get("identitas_dokumen") or "-"
            item_id = QTableWidgetItem(identitas)
            item_id.setTextAlignment(Qt.AlignCenter)
            if identitas != "-":
                item_id.setFont(item_id.font())
                item_id.setForeground(Qt.darkBlue)
            self.table_queue.setItem(row, 2, item_id)

            # 3. Luas Dokumen
            luas_doc = doc.get("luas_dokumen")
            luas_str = f"{luas_doc:.2f}" if luas_doc else "-"
            item_ld = QTableWidgetItem(luas_str)
            item_ld.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table_queue.setItem(row, 3, item_ld)

            # 4. Luas Tracing
            luas_awal = doc.get("luas_awal")
            luas_awal_str = f"{luas_awal:.2f}" if luas_awal else "-"
            item_la = QTableWidgetItem(luas_awal_str)
            item_la.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table_queue.setItem(row, 4, item_la)

            # 5. Faktor Scaling
            scale_fac = doc.get("faktor_scaling")
            scale_str = f"{scale_fac:.6f}" if scale_fac else "-"
            item_sf = QTableWidgetItem(scale_str)
            item_sf.setTextAlignment(Qt.AlignCenter)
            self.table_queue.setItem(row, 5, item_sf)

            # 6. Status Badge
            badge = StatusBadge(status)
            self.table_queue.setCellWidget(row, 6, badge)

            # 7. Tombol Aksi yang Jelas dan Informatif
            act_widget = QWidget()
            act_layout = QHBoxLayout(act_widget)
            act_layout.setContentsMargins(4, 2, 4, 2)
            act_layout.setSpacing(6)

            if is_completed:
                # Tombol Buka DWG (Hijau)
                btn_dwg = QPushButton("📁 Buka DWG")
                btn_dwg.setStyleSheet("""
                    QPushButton {
                        background-color: #059669;
                        color: #FFFFFF;
                        font-weight: 700;
                        padding: 5px 10px;
                        border-radius: 5px;
                    }
                    QPushButton:hover { background-color: #047857; }
                """)
                dwg_path = doc.get("path_dwg", "")
                btn_dwg.setEnabled(bool(dwg_path and os.path.exists(dwg_path)))
                btn_dwg.setToolTip("Buka file DWG hasil digitasi di AutoCAD")
                btn_dwg.clicked.connect(lambda checked=False, p=dwg_path: self._open_dwg(p))
                act_layout.addWidget(btn_dwg)

                # Tombol Edit / Ulang
                btn_edit = QPushButton("Lihat / Ulang")
                btn_edit.setProperty("class", "btn-secondary")
                btn_edit.setToolTip("Buka kembali wizard digitasi dokumen ini")
                btn_edit.clicked.connect(lambda checked=False, id_=doc_id: self.start_process_doc.emit(id_))
                act_layout.addWidget(btn_edit)
            else:
                # Tombol Mulai Digitasi (Biru Mencolok)
                btn_proc = QPushButton("▶ Mulai Digitasi")
                btn_proc.setStyleSheet("""
                    QPushButton {
                        background-color: #2563EB;
                        color: #FFFFFF;
                        font-weight: 700;
                        padding: 6px 14px;
                        border-radius: 5px;
                    }
                    QPushButton:hover { background-color: #1D4ED8; }
                """)
                btn_proc.setToolTip("Buka proses pemotongan denah dan integrasi AutoCAD untuk dokumen ini")
                btn_proc.clicked.connect(lambda checked=False, id_=doc_id: self.start_process_doc.emit(id_))
                act_layout.addWidget(btn_proc)

            # Tombol Hapus (Merah)
            btn_del = QPushButton("🗑️")
            btn_del.setProperty("class", "btn-danger")
            btn_del.setFixedWidth(32)
            btn_del.setToolTip("Hapus dokumen ini dari antrean")
            btn_del.clicked.connect(lambda checked=False, id_=doc_id: self._delete_doc(id_))
            act_layout.addWidget(btn_del)

            self.table_queue.setCellWidget(row, 7, act_widget)

    def _import_pdf_dialog(self):
        if not self.active_batch_id:
            QMessageBox.warning(self, "Peringatan", "Pilih batch aktif terlebih dahulu sebelum mengimpor PDF.")
            return

        file_paths, _ = QFileDialog.getOpenFileNames(
            self, "Pilih Dokumen PDF Denah Tanah", "", "File PDF (*.pdf)"
        )
        if not file_paths:
            return

        import shutil
        added_count = 0
        for path in file_paths:
            filename = os.path.basename(path)
            dest_folder = DOKUMEN_MASUK_DIR / f"Batch_{self.active_batch_id}"
            dest_folder.mkdir(parents=True, exist_ok=True)
            local_pdf_path = dest_folder / filename
            try:
                shutil.copy2(path, str(local_pdf_path))
                used_path = str(local_pdf_path)
            except Exception:
                used_path = path

            create_document(
                batch_id=self.active_batch_id,
                nama_pdf=filename,
                path_pdf=used_path,
                status=STATUS_MENUNGGU
            )
            added_count += 1

        QMessageBox.information(
            self, "Import Dokumen Berhasil",
            f"Berhasil menambahkan {added_count} dokumen PDF ke dalam antrean!\n\n"
            "Silakan klik tombol '▶ Mulai Digitasi' pada baris dokumen untuk memulai proses pemotongan dan penarikan ke AutoCAD."
        )
        self.load_data()

    def _open_dwg(self, dwg_path: str):
        if os.path.exists(dwg_path):
            os.startfile(dwg_path)
        else:
            QMessageBox.warning(self, "File Tidak Ditemukan", f"File DWG tidak ditemukan di:\n{dwg_path}")

    def _delete_doc(self, doc_id: int):
        doc = get_document(doc_id)
        if not doc:
            return
        reply = QMessageBox.question(
            self, "Konfirmasi Hapus Dokumen",
            f"Apakah Anda yakin ingin menghapus dokumen berikut?\n\n"
            f"• File: {doc['nama_pdf']}\n"
            f"• Identitas: {doc.get('identitas_dokumen') or '-'}\n\n"
            "Tindakan ini tidak dapat dibatalkan.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            delete_document(doc_id)
            self.load_data()
