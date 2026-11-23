"""
AutoLand Digitizer - Report & Recap Page (dengan Panduan & Validasi Batch)
Pemeriksaan kelengkapan batch, rekapitulasi data, serta ekspor Excel (.xlsx), CSV, dan arsip ZIP.
"""

import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QPushButton, QFrame, QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox, QFileDialog
)
from PySide6.QtCore import Qt

from database.db import get_all_batches, get_batch, get_documents_by_batch
from services.export_service import (
    check_batch_readiness, export_batch_to_excel, export_batch_to_csv, export_batch_to_zip
)
from ui.components.guide_banner import GuideBanner

class ReportPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.active_batch_id = None
        self._setup_ui()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 20, 24, 24)
        main_layout.setSpacing(14)

        # Header
        header_layout = QHBoxLayout()
        header_text = QVBoxLayout()
        header_text.setSpacing(3)
        title = QLabel("Rekapitulasi & Ekspor Laporan Batch")
        title.setStyleSheet("font-size: 20px; font-weight: 800; color: #0F172A;")
        header_text.addWidget(title)

        subtitle = QLabel("Pemeriksaan status berkas, penyusunan rekapitulasi resmi, dan pengemasan paket arsip pekerjaan.")
        subtitle.setStyleSheet("color: #64748B; font-size: 13px;")
        header_text.addWidget(subtitle)
        header_layout.addLayout(header_text)
        header_layout.addStretch()

        main_layout.addLayout(header_layout)

        # Panduan Rekapitulasi
        report_guide = [
            "Pilih <b>Batch Wilayah</b> yang ingin dibuatkan rekapitulasinya pada dropdown di bawah.",
            "Periksa <b>Status Kesiapan Batch</b>: Pastikan berwarna hijau (100% Selesai) agar laporan final valid.",
            "Klik tombol biru <b>'📊 Ekspor Excel (.xlsx)'</b> untuk mencetak rekapitulasi berformat tabel resmi pertanahan.",
            "Klik tombol hijau <b>'📦 Buat Paket ZIP'</b> untuk mengarsipkan seluruh file DWG beserta rekapitulasi Excel ke dalam satu file ZIP."
        ]
        self.guide_banner = GuideBanner("Petunjuk Penggunaan Rekapitulasi & Ekspor", report_guide)
        main_layout.addWidget(self.guide_banner)

        # Batch Selector Card
        sel_card = QFrame()
        sel_card.setStyleSheet("background-color: #FFFFFF; border-radius: 8px; border: 1px solid #E2E8F0; padding: 12px;")
        s_layout = QHBoxLayout(sel_card)
        s_layout.setContentsMargins(12, 6, 12, 6)
        s_layout.setSpacing(12)

        lbl_b = QLabel("Pilih Batch Wilayah:")
        lbl_b.setStyleSheet("font-weight: 700; color: #1E293B;")
        s_layout.addWidget(lbl_b)

        self.combo_batches = QComboBox()
        self.combo_batches.currentIndexChanged.connect(self._on_batch_changed)
        s_layout.addWidget(self.combo_batches, 1)

        self.btn_refresh = QPushButton("Segarkan")
        self.btn_refresh.setProperty("class", "btn-secondary")
        self.btn_refresh.clicked.connect(self.load_batches)
        s_layout.addWidget(self.btn_refresh)

        main_layout.addWidget(sel_card)

        # Readiness Banner
        self.readiness_card = QFrame()
        self.readiness_card.setStyleSheet("border-radius: 8px; padding: 12px;")
        r_layout = QHBoxLayout(self.readiness_card)
        self.lbl_readiness = QLabel("Status Kesiapan Batch...")
        self.lbl_readiness.setStyleSheet("font-size: 13px; font-weight: 700;")
        r_layout.addWidget(self.lbl_readiness)
        main_layout.addWidget(self.readiness_card)

        # Tombol Ekspor
        export_btn_card = QFrame()
        export_btn_card.setStyleSheet("background-color: #FFFFFF; border-radius: 8px; border: 1px solid #E2E8F0; padding: 12px;")
        eb_layout = QHBoxLayout(export_btn_card)
        eb_layout.setSpacing(12)

        self.btn_export_excel = QPushButton("📊 Ekspor Excel Resmi (.xlsx)")
        self.btn_export_excel.setStyleSheet("""
            QPushButton {
                background-color: #1E40AF;
                color: #FFFFFF;
                font-weight: 700;
                padding: 10px 18px;
                border-radius: 6px;
            }
            QPushButton:hover { background-color: #1D4ED8; }
        """)
        self.btn_export_excel.clicked.connect(self._export_excel)
        eb_layout.addWidget(self.btn_export_excel)

        self.btn_export_csv = QPushButton("📄 Ekspor CSV (.csv)")
        self.btn_export_csv.setProperty("class", "btn-secondary")
        self.btn_export_csv.setStyleSheet("font-weight: 600; padding: 10px 14px;")
        self.btn_export_csv.clicked.connect(self._export_csv)
        eb_layout.addWidget(self.btn_export_csv)

        self.btn_export_zip = QPushButton("📦 Buat Paket ZIP (Seluruh DWG + Excel)")
        self.btn_export_zip.setStyleSheet("""
            QPushButton {
                background-color: #059669;
                color: #FFFFFF;
                font-weight: 700;
                padding: 10px 18px;
                border-radius: 6px;
            }
            QPushButton:hover { background-color: #047857; }
        """)
        self.btn_export_zip.clicked.connect(self._export_zip)
        eb_layout.addWidget(self.btn_export_zip)

        eb_layout.addStretch()
        main_layout.addWidget(export_btn_card)

        # Preview Tabel Rekapitulasi
        self.table_preview = QTableWidget()
        self.table_preview.setColumnCount(9)
        self.table_preview.setHorizontalHeaderLabels([
            "No", "Identitas Resmi Dokumen", "Jenis Hak", "Nomor Hak", "Nomor GS",
            "Tahun", "Luas Dok (m²)", "Luas Akhir (m²)", "Status"
        ])
        self.table_preview.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table_preview.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        for i in range(2, 9):
            self.table_preview.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeToContents)
        self.table_preview.verticalHeader().setVisible(False)
        self.table_preview.setSelectionBehavior(QTableWidget.SelectRows)
        self.table_preview.setEditTriggers(QTableWidget.NoEditTriggers)

        main_layout.addWidget(self.table_preview, 1)

    def load_batches(self):
        batches = get_all_batches()
        self.combo_batches.clear()
        if not batches:
            self.combo_batches.addItem("Tidak ada batch yang tersedia", None)
            return

        for b in batches:
            label = f"Desa {b['nama_desa']} ({b['kecamatan']}, {b['kabupaten']}) - ID {b['id']}"
            self.combo_batches.addItem(label, b["id"])

        if self.active_batch_id:
            idx = self.combo_batches.findData(self.active_batch_id)
            if idx >= 0:
                self.combo_batches.setCurrentIndex(idx)

    def set_active_batch(self, batch_id: int):
        self.active_batch_id = batch_id
        self.load_batches()

    def _on_batch_changed(self, index: int):
        batch_id = self.combo_batches.currentData()
        if not batch_id:
            return
        self.active_batch_id = batch_id
        self._refresh_batch_details(batch_id)

    def _refresh_batch_details(self, batch_id: int):
        readiness = check_batch_readiness(batch_id)
        if readiness["is_ready"]:
            self.readiness_card.setStyleSheet("background-color: #ECFDF5; border: 1.5px solid #10B981; border-radius: 8px; padding: 12px;")
            self.lbl_readiness.setText(f"✓ Seluruh dokumen dalam batch telah SELESAI ({readiness['selesai']} berkas). Batch siap diekspor secara final!")
            self.lbl_readiness.setStyleSheet("color: #047857; font-weight: 700;")
        else:
            self.readiness_card.setStyleSheet("background-color: #FEF2F2; border: 1.5px solid #EF4444; border-radius: 8px; padding: 12px;")
            self.lbl_readiness.setText(
                f"⚠ Perhatian: Terdapat {readiness['pending_count']} dari {readiness['total']} dokumen yang BELUM SELESAI. "
                "Disarankan menyelesaikan seluruh dokumen sebelum mengekspor rekapitulasi final."
            )
            self.lbl_readiness.setStyleSheet("color: #B91C1C; font-weight: 700;")

        docs = get_documents_by_batch(batch_id)
        self.table_preview.setRowCount(len(docs))
        for row, doc in enumerate(docs):
            self.table_preview.setItem(row, 0, QTableWidgetItem(str(row + 1)))
            self.table_preview.setItem(row, 1, QTableWidgetItem(doc.get("identitas_dokumen", "-")))
            self.table_preview.setItem(row, 2, QTableWidgetItem(doc.get("jenis_hak", "-")))
            self.table_preview.setItem(row, 3, QTableWidgetItem(doc.get("nomor_hak", "-")))
            self.table_preview.setItem(row, 4, QTableWidgetItem(doc.get("nomor_gs", "-")))
            self.table_preview.setItem(row, 5, QTableWidgetItem(doc.get("tahun", "-")))
            
            ld = doc.get("luas_dokumen")
            self.table_preview.setItem(row, 6, QTableWidgetItem(f"{ld:.2f}" if ld else "-"))
            
            la = doc.get("luas_akhir")
            self.table_preview.setItem(row, 7, QTableWidgetItem(f"{la:.2f}" if la else "-"))
            
            self.table_preview.setItem(row, 8, QTableWidgetItem(doc.get("status", "-")))

    def _confirm_if_pending(self) -> bool:
        if not self.active_batch_id:
            return False
        readiness = check_batch_readiness(self.active_batch_id)
        if not readiness["is_ready"]:
            reply = QMessageBox.warning(
                self, "Konfirmasi Ekspor Batch Belum Selesai",
                f"Terdapat {readiness['pending_count']} dokumen yang belum berstatus SELESAI.\n\n"
                "Apakah Anda yakin tetap ingin mengekspor rekapitulasi saat ini?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            return reply == QMessageBox.Yes
        return True

    def _export_excel(self):
        if not self.active_batch_id:
            QMessageBox.warning(self, "Pilih Batch", "Pilih batch terlebih dahulu.")
            return
        if not self._confirm_if_pending():
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Simpan Rekapitulasi Excel", f"Rekapitulasi_Batch_{self.active_batch_id}.xlsx", "Excel Files (*.xlsx)"
        )
        if not file_path:
            return

        ok, msg = export_batch_to_excel(self.active_batch_id, file_path)
        if ok:
            QMessageBox.information(self, "Ekspor Berhasil", f"File Excel berhasil disimpan di:\n{msg}")
        else:
            QMessageBox.critical(self, "Ekspor Gagal", msg)

    def _export_csv(self):
        if not self.active_batch_id:
            QMessageBox.warning(self, "Pilih Batch", "Pilih batch terlebih dahulu.")
            return
        if not self._confirm_if_pending():
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Simpan Rekapitulasi CSV", f"Rekapitulasi_Batch_{self.active_batch_id}.csv", "CSV Files (*.csv)"
        )
        if not file_path:
            return

        ok, msg = export_batch_to_csv(self.active_batch_id, file_path)
        if ok:
            QMessageBox.information(self, "Ekspor Berhasil", f"File CSV berhasil disimpan di:\n{msg}")
        else:
            QMessageBox.critical(self, "Ekspor Gagal", msg)

    def _export_zip(self):
        if not self.active_batch_id:
            QMessageBox.warning(self, "Pilih Batch", "Pilih batch terlebih dahulu.")
            return
        if not self._confirm_if_pending():
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Simpan Paket ZIP", f"Paket_Digitasi_Batch_{self.active_batch_id}.zip", "ZIP Archives (*.zip)"
        )
        if not file_path:
            return

        ok, msg = export_batch_to_zip(self.active_batch_id, file_path)
        if ok:
            QMessageBox.information(self, "Ekspor Berhasil", f"Paket arsip ZIP berhasil dibuat di:\n{msg}")
        else:
            QMessageBox.critical(self, "Ekspor Gagal", msg)
