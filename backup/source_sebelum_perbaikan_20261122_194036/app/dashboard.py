"""
AutoLand Digitizer - Dashboard Page (dengan Panduan Alur Kerja Lengkap)
Halaman ikhtisar metrik statistik, status antrean, aksi cepat, riwayat aktivitas,
serta panduan alur kerja 4 tahap digitalisasi pertanahan.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QTableWidget, QTableWidgetItem, QHeaderView, QProgressBar
)
from PySide6.QtCore import Qt, Signal

from ui.components.stat_card import StatCard
from ui.components.guide_banner import GuideBanner
from database.db import get_overall_stats, get_recent_logs, get_all_batches, get_batch_stats

class DashboardPage(QWidget):
    navigate_to_page = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.active_batch_id = None
        self._setup_ui()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 20, 24, 24)
        main_layout.setSpacing(14)

        # 1. Header & Quick Action Buttons
        header_layout = QHBoxLayout()
        header_text_layout = QVBoxLayout()
        header_text_layout.setSpacing(3)

        title = QLabel("Dashboard Ringkasan Digitalisasi")
        title.setStyleSheet("font-size: 20px; font-weight: 800; color: #0F172A;")
        header_text_layout.addWidget(title)

        subtitle = QLabel("Pantau progres digitalisasi dokumen pertanahan, antrean batch, dan integrasi AutoCAD.")
        subtitle.setStyleSheet("color: #64748B; font-size: 13px;")
        header_text_layout.addWidget(subtitle)
        header_layout.addLayout(header_text_layout)

        header_layout.addStretch()

        self.btn_new_batch = QPushButton("+ Buat Batch Wilayah")
        self.btn_new_batch.setProperty("class", "btn-primary")
        self.btn_new_batch.clicked.connect(lambda: self.navigate_to_page.emit(1))
        header_layout.addWidget(self.btn_new_batch)

        self.btn_open_queue = QPushButton("📋 Buka Antrean Dokumen")
        self.btn_open_queue.setProperty("class", "btn-success")
        self.btn_open_queue.clicked.connect(lambda: self.navigate_to_page.emit(2))
        header_layout.addWidget(self.btn_open_queue)

        main_layout.addLayout(header_layout)

        # 2. Panduan Alur Kerja Ringkas 4 Langkah
        workflow_guide = [
            "<b>Tahap 1: Buat / Pilih Batch Wilayah</b> — Kelompokkan berkas berdasarkan Desa/Kelurahan pada menu 'Batch Pekerjaan'.",
            "<b>Tahap 2: Import PDF & Masuk Antrean</b> — Tambahkan file scan PDF denah pertanahan pada menu 'Antrean Dokumen'.",
            "<b>Tahap 3: Pemotongan & Integrasi AutoCAD</b> — Klik 'Mulai Digitasi' untuk memotong denah, melakukan tracing polyline (PL), dan scaling otomatis.",
            "<b>Tahap 4: Ekspor Rekapitulasi Resmi</b> — Setelah seluruh berkas selesai, buka menu 'Rekapitulasi' untuk ekspor Excel (.xlsx) dan paket arsip ZIP."
        ]
        self.guide_banner = GuideBanner("Panduan Ringkas Alur Kerja Digitalisasi (4 Tahap)", workflow_guide)
        main_layout.addWidget(self.guide_banner)

        # 3. Stat Cards Grid
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(12)

        self.card_total_batch = StatCard("Total Batch", "0", "Wilayah desa", "#2563EB")
        self.card_total_doc = StatCard("Total Dokumen", "0", "Dokumen PDF", "#0D9488")
        self.card_menunggu = StatCard("Menunggu", "0", "Belum diproses", "#64748B")
        self.card_proses = StatCard("Sedang Dikerjakan", "0", "Tracing / Scaling", "#F59E0B")
        self.card_selesai = StatCard("Selesai (DWG)", "0", "Telah disimpan", "#10B981")
        self.card_persen = StatCard("Progres Selesai", "0%", "Tingkat kelulusan", "#7C3AED")

        stats_layout.addWidget(self.card_total_batch)
        stats_layout.addWidget(self.card_total_doc)
        stats_layout.addWidget(self.card_menunggu)
        stats_layout.addWidget(self.card_proses)
        stats_layout.addWidget(self.card_selesai)
        stats_layout.addWidget(self.card_persen)

        main_layout.addLayout(stats_layout)

        # 4. Status Batch Aktif & Progress Bar
        self.batch_status_card = QFrame()
        self.batch_status_card.setStyleSheet("""
            QFrame {
                background-color: #FFFFFF;
                border-radius: 8px;
                border: 1px solid #E2E8F0;
                padding: 14px;
            }
        """)
        bsc_layout = QVBoxLayout(self.batch_status_card)
        bsc_layout.setSpacing(8)

        bsc_header = QHBoxLayout()
        self.lbl_batch_title = QLabel("Batch Aktif: Tidak Ada Batch Terpilih")
        self.lbl_batch_title.setStyleSheet("font-size: 13px; font-weight: 700; color: #1E293B;")
        bsc_header.addWidget(self.lbl_batch_title)

        bsc_header.addStretch()

        self.lbl_batch_percent = QLabel("0% Selesai")
        self.lbl_batch_percent.setStyleSheet("font-size: 13px; font-weight: 800; color: #10B981;")
        bsc_header.addWidget(self.lbl_batch_percent)
        bsc_layout.addLayout(bsc_header)

        self.batch_progress = QProgressBar()
        self.batch_progress.setValue(0)
        self.batch_progress.setTextVisible(False)
        self.batch_progress.setFixedHeight(8)
        self.batch_progress.setStyleSheet("""
            QProgressBar {
                background-color: #F1F5F9;
                border-radius: 4px;
            }
            QProgressBar::chunk {
                background-color: #10B981;
                border-radius: 4px;
            }
        """)
        bsc_layout.addWidget(self.batch_progress)

        main_layout.addWidget(self.batch_status_card)

        # 5. Riwayat Aktivitas Terbaru
        log_card = QFrame()
        log_card.setStyleSheet("""
            QFrame {
                background-color: #FFFFFF;
                border-radius: 8px;
                border: 1px solid #E2E8F0;
                padding: 14px;
            }
        """)
        log_layout = QVBoxLayout(log_card)
        log_layout.setSpacing(10)

        log_title = QLabel("Riwayat Aktivitas Terakhir")
        log_title.setStyleSheet("font-size: 14px; font-weight: 700; color: #0F172A;")
        log_layout.addWidget(log_title)

        self.log_table = QTableWidget()
        self.log_table.setColumnCount(4)
        self.log_table.setHorizontalHeaderLabels(["Waktu", "Batch / Desa", "Aktivitas", "Detail Catatan"])
        self.log_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.log_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.log_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.log_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.log_table.verticalHeader().setVisible(False)
        self.log_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.log_table.setSelectionBehavior(QTableWidget.SelectRows)
        log_layout.addWidget(self.log_table)

        main_layout.addWidget(log_card, 1)

    def set_active_batch(self, batch_id: int):
        self.active_batch_id = batch_id
        self.refresh_data()

    def refresh_data(self):
        stats = get_overall_stats()
        self.card_total_batch.set_value(str(stats["total_batches"]))
        self.card_total_doc.set_value(str(stats["total_documents"]))
        self.card_menunggu.set_value(str(stats["menunggu"]))
        self.card_proses.set_value(str(stats["proses"]))
        self.card_selesai.set_value(str(stats["selesai"]))
        self.card_persen.set_value(f"{stats['persen_selesai']}%")

        if self.active_batch_id:
            from database.db import get_batch
            b_info = get_batch(self.active_batch_id)
            if b_info:
                b_stats = get_batch_stats(self.active_batch_id)
                self.lbl_batch_title.setText(f"Batch Aktif: <b>Desa {b_info['nama_desa']}</b> ({b_info['kecamatan']}) — {b_stats['selesai']} dari {b_stats['total']} dokumen selesai")
                self.lbl_batch_percent.setText(f"{b_stats['persen']}% Selesai")
                self.batch_progress.setValue(int(b_stats['persen']))
            else:
                self.lbl_batch_title.setText("Batch Aktif: Tidak Ada")
                self.lbl_batch_percent.setText("0%")
                self.batch_progress.setValue(0)
        else:
            self.lbl_batch_title.setText("Pilih atau buat batch pekerjaan untuk memulai digitalisasi.")
            self.lbl_batch_percent.setText("0%")
            self.batch_progress.setValue(0)

        logs = get_recent_logs(25)
        self.log_table.setRowCount(len(logs))
        for row, l in enumerate(logs):
            t_item = QTableWidgetItem(l.get("timestamp", "-"))
            t_item.setTextAlignment(Qt.AlignCenter)
            self.log_table.setItem(row, 0, t_item)

            d_item = QTableWidgetItem(l.get("nama_desa", "-") or "-")
            d_item.setTextAlignment(Qt.AlignCenter)
            self.log_table.setItem(row, 1, d_item)

            a_item = QTableWidgetItem(l.get("aktivitas", "-"))
            a_item.setTextAlignment(Qt.AlignCenter)
            self.log_table.setItem(row, 2, a_item)

            detail_item = QTableWidgetItem(l.get("detail", "-"))
            self.log_table.setItem(row, 3, detail_item)
