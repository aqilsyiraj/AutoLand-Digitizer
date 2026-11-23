"""Dashboard: ringkasan pekerjaan, alur kerja, dan aktivitas terbaru."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QGridLayout, QHBoxLayout, QLabel, QProgressBar, QPushButton,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from database.db import get_batch, get_batch_stats, get_overall_stats, get_recent_logs
from ui.components.data_table import DataTable
from ui.components.guide_banner import GuideBanner
from ui.components.page_header import PageHeader
from ui.components.section_card import SectionCard
from ui.components.stat_card import StatCard


class DashboardPage(QWidget):
    navigate_to_page = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.active_batch_id = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 12, 18, 12)
        layout.setSpacing(8)

        header = PageHeader(
            "Ringkasan Digitalisasi",
            "Pantau progres batch, antrean dokumen, dan koneksi AutoCAD dari satu layar.",
        )
        btn_new_batch = QPushButton("+ Buat Batch")
        btn_new_batch.setProperty("class", "btn-primary")
        btn_new_batch.setToolTip("Buat kelompok kerja baru untuk satu desa atau kelurahan")
        btn_new_batch.clicked.connect(lambda: self.navigate_to_page.emit(1))
        header.add_action(btn_new_batch)

        self.btn_open_queue = QPushButton("Buka Antrean")
        self.btn_open_queue.setProperty("class", "btn-success")
        self.btn_open_queue.setToolTip("Lihat dan proses PDF yang sudah diimpor")
        self.btn_open_queue.clicked.connect(lambda: self.navigate_to_page.emit(2))
        header.add_action(self.btn_open_queue)
        layout.addWidget(header)

        workflow = [
            "<b>Buat atau pilih batch wilayah</b> pada menu 2 agar berkas terkumpul per desa.",
            "<b>Impor PDF denah</b> pada menu 3, lalu klik <b>Proses</b> pada baris dokumen.",
            "<b>Periksa polyline hasil deteksi</b> dan isi identitas dokumen sebelum memproses ke DWG.",
            "<b>Ekspor rekap</b> pada menu 6 setelah seluruh dokumen dalam batch selesai.",
        ]
        layout.addWidget(GuideBanner("Alur kerja 4 langkah — buka bila perlu petunjuk", workflow))

        # Satu baris metrik: hemat tinggi, ruang aktivitas terakhir jadi lebih besar.
        stats_grid = QGridLayout()
        stats_grid.setSpacing(8)
        self.card_total_batch = StatCard("Total Batch", "0", "Wilayah", "#2563EB")
        self.card_total_doc = StatCard("Dokumen", "0", "Berkas PDF", "#0D9488")
        self.card_menunggu = StatCard("Menunggu", "0", "Belum diproses", "#64748B")
        self.card_proses = StatCard("Dikerjakan", "0", "Deteksi + DWG", "#D97706")
        self.card_selesai = StatCard("Selesai DWG", "0", "Tersimpan", "#059669")
        self.card_persen = StatCard("Progres", "0%", "Semua dokumen", "#0369A1")
        cards = [
            self.card_total_batch, self.card_total_doc, self.card_menunggu,
            self.card_proses, self.card_selesai, self.card_persen,
        ]
        for idx, card in enumerate(cards):
            stats_grid.addWidget(card, 0, idx)
            stats_grid.setColumnStretch(idx, 1)
        layout.addLayout(stats_grid)

        batch_card = SectionCard("Progres Batch Aktif")
        bsc_header = QHBoxLayout()
        bsc_header.setSpacing(8)
        self.lbl_batch_title = QLabel("Pilih atau buat batch pekerjaan untuk memulai.")
        self.lbl_batch_title.setWordWrap(True)
        bsc_header.addWidget(self.lbl_batch_title, 1)
        self.lbl_batch_percent = QLabel("0% selesai")
        self.lbl_batch_percent.setStyleSheet("color:#047857;font-weight:800;font-size:12px;")
        bsc_header.addWidget(self.lbl_batch_percent)
        batch_card.body_layout.addLayout(bsc_header)

        self.batch_progress = QProgressBar()
        self.batch_progress.setRange(0, 100)
        self.batch_progress.setValue(0)
        self.batch_progress.setTextVisible(False)
        self.batch_progress.setFixedHeight(8)
        self.batch_progress.setStyleSheet(
            "QProgressBar{background:#F1F5F9;border-radius:5px;}"
            "QProgressBar::chunk{background:#059669;border-radius:5px;}"
        )
        batch_card.body_layout.addWidget(self.batch_progress)
        layout.addWidget(batch_card)

        log_card = SectionCard("Aktivitas Terakhir", "Riwayat 25 kegiatan terakhir di aplikasi ini.")
        self.log_table = DataTable(4)
        self.log_table.setHorizontalHeaderLabels(["Waktu", "Batch / Desa", "Aktivitas", "Detail Catatan"])
        self.log_table.set_columns([132, 150, 170, 0], stretch_column=3)
        self.log_table.verticalHeader().setDefaultSectionSize(38)
        self.log_table.set_empty_text("Belum ada aktivitas. Mulai dengan membuat batch wilayah.")
        log_card.body_layout.addWidget(self.log_table, 1)
        layout.addWidget(log_card, 1)

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
            b_info = get_batch(self.active_batch_id)
            if b_info:
                b_stats = get_batch_stats(self.active_batch_id)
                self.lbl_batch_title.setText(
                    f"Desa <b>{b_info['nama_desa']}</b> — {b_stats['selesai']} dari "
                    f"{b_stats['total']} dokumen selesai (Kec. {b_info['kecamatan']})."
                )
                self.lbl_batch_title.setTextFormat(Qt.RichText)
                self.lbl_batch_percent.setText(f"{b_stats['persen']}% selesai")
                self.batch_progress.setValue(int(b_stats["persen"]))
            else:
                self.lbl_batch_title.setText("Batch aktif tidak ditemukan.")
                self.lbl_batch_percent.setText("0% selesai")
                self.batch_progress.setValue(0)
        else:
            self.lbl_batch_title.setText("Pilih atau buat batch pekerjaan untuk memulai digitalisasi.")
            self.lbl_batch_percent.setText("0% selesai")
            self.batch_progress.setValue(0)

        logs = get_recent_logs(25)
        self.log_table.setRowCount(len(logs))
        for row, log in enumerate(logs):
            values = [
                log.get("timestamp", "-"),
                log.get("nama_desa", "-") or "-",
                log.get("aktivitas", "-"),
                log.get("detail", "-"),
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if col < 3:
                    item.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)
                self.log_table.setItem(row, col, item)
