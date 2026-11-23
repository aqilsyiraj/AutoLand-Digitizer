"""Dashboard: ringkasan pekerjaan, alur kerja, dan aktivitas terbaru."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from database.db import get_batch, get_batch_stats, get_overall_stats, get_recent_logs
from ui.components.button import Button
from ui.components.data_table import DataTable
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
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(14)

        header = PageHeader(
            "Ringkasan Pekerjaan",
            "Pantau progres batch, antrean, dan kesiapan AutoCAD dari satu layar.",
            eyebrow="Dasbor",
        )
        header.add_action(
            Button(
                "Buat Batch",
                size="md",
                tone="primary",
                tooltip="Buat kelompok kerja baru untuk satu desa atau kelurahan",
                on_click=lambda: self.navigate_to_page.emit(1),
            )
        )
        self.btn_open_queue = Button(
            "Buka Antrean",
            size="md",
            tone="secondary",
            tooltip="Lihat dan proses PDF yang sudah diimpor",
        )
        self.btn_open_queue.clicked.connect(lambda: self.navigate_to_page.emit(2))
        header.add_action(self.btn_open_queue)
        layout.addWidget(header)

        # ---------- Metrik utama ----------
        stats = QHBoxLayout()
        stats.setSpacing(12)
        self.card_total_batch = StatCard(
            "Total Batch", "0", "Wilayah terdaftar", "#1D4ED8"
        )
        self.card_total_doc = StatCard(
            "Dokumen", "0", "PDF di semua batch", "#0F766E"
        )
        self.card_selesai = StatCard(
            "Selesai DWG", "0", "Berkas tersimpan", "#15803D"
        )
        self.card_persen = StatCard(
            "Progres", "0%", "Penyelesaian keseluruhan", "#B45309"
        )
        for card in (
            self.card_total_batch,
            self.card_total_doc,
            self.card_selesai,
            self.card_persen,
        ):
            stats.addWidget(card, 1)
        layout.addLayout(stats)

        # ---------- Progres batch + alur kerja ----------
        middle = QHBoxLayout()
        middle.setSpacing(12)

        progress_card = SectionCard(
            "Progres Batch Aktif", "Ringkasan batch yang sedang dipilih."
        )
        head = QHBoxLayout()
        head.setSpacing(10)
        self.lbl_batch_title = QLabel(
            "Pilih atau buat batch pekerjaan untuk memulai."
        )
        self.lbl_batch_title.setObjectName("SectionSubtitle")
        self.lbl_batch_title.setWordWrap(True)
        head.addWidget(self.lbl_batch_title, 1)
        self.lbl_batch_percent = QLabel("0%")
        self.lbl_batch_percent.setObjectName("ProgressPercent")
        head.addWidget(self.lbl_batch_percent, 0, Qt.AlignRight)
        progress_card.body_layout.addLayout(head)

        self.batch_progress = QProgressBar()
        self.batch_progress.setRange(0, 100)
        self.batch_progress.setValue(0)
        self.batch_progress.setTextVisible(False)
        self.batch_progress.setFixedHeight(8)
        progress_card.body_layout.addWidget(self.batch_progress)

        mini = QHBoxLayout()
        mini.setSpacing(10)
        self.card_menunggu = StatCard(
            "Menunggu", "0", "Belum diproses", "#64748B", compact=True
        )
        self.card_proses = StatCard(
            "Dikerjakan", "0", "Sedang diproses", "#B45309", compact=True
        )
        mini.addWidget(self.card_menunggu, 1)
        mini.addWidget(self.card_proses, 1)
        progress_card.body_layout.addLayout(mini)
        middle.addWidget(progress_card, 2)

        workflow_card = SectionCard(
            "Alur Kerja", "Empat langkah dari PDF denah ke DWG."
        )
        steps = [
            ("Buat batch wilayah", "Kumpulkan berkas per desa di menu 2."),
            ("Impor PDF denah", "Tambahkan scan di menu 3, lalu klik Proses."),
            ("Periksa & isi data", "Koreksi polyline dan identitas dokumen."),
            ("Ekspor rekap", "Unduh Excel, CSV, atau paket ZIP di menu 6."),
        ]
        for number, (title, desc) in enumerate(steps, start=1):
            workflow_card.body_layout.addLayout(
                self._workflow_row(number, title, desc)
            )
        workflow_card.body_layout.addStretch(1)
        middle.addWidget(workflow_card, 1)
        layout.addLayout(middle)

        # ---------- Aktivitas ----------
        log_card = SectionCard(
            "Aktivitas Terakhir", "Riwayat 25 kegiatan terakhir di aplikasi ini."
        )
        log_card.add_action(
            Button(
                "Segarkan",
                size="sm",
                tone="secondary",
                tooltip="Muat ulang ringkasan dan aktivitas",
                on_click=self.refresh_data,
            )
        )
        self.log_table = DataTable(4)
        self.log_table.setHorizontalHeaderLabels(
            ["Waktu", "Batch / Desa", "Aktivitas", "Detail Catatan"]
        )
        self.log_table.set_columns([132, 150, 178, 0], stretch_column=3)
        self.log_table.verticalHeader().setDefaultSectionSize(36)
        self.log_table.set_empty_text(
            "Belum ada aktivitas. Mulai dengan membuat batch wilayah."
        )
        log_card.body_layout.addWidget(self.log_table, 1)
        layout.addWidget(log_card, 1)

    @staticmethod
    def _workflow_row(number: int, title: str, desc: str) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(10)
        badge = QLabel(str(number))
        badge.setObjectName("StepBadge")
        badge.setAlignment(Qt.AlignCenter)
        badge.setFixedSize(24, 24)
        row.addWidget(badge, 0, Qt.AlignTop)

        text = QVBoxLayout()
        text.setSpacing(0)
        t = QLabel(title)
        t.setObjectName("StepTitle")
        t.setWordWrap(True)
        d = QLabel(desc)
        d.setObjectName("StepDesc")
        d.setWordWrap(True)
        text.addWidget(t)
        text.addWidget(d)
        row.addLayout(text, 1)
        return row

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
            info = get_batch(self.active_batch_id)
            if info:
                b_stats = get_batch_stats(self.active_batch_id)
                self.lbl_batch_title.setText(
                    f"Desa {info['nama_desa']} — {b_stats['selesai']} dari "
                    f"{b_stats['total']} dokumen selesai (Kec. {info['kecamatan']})."
                )
                self.lbl_batch_percent.setText(f"{b_stats['persen']}%")
                self.batch_progress.setValue(int(b_stats["persen"]))
            else:
                self.lbl_batch_title.setText("Batch aktif tidak ditemukan.")
                self.lbl_batch_percent.setText("0%")
                self.batch_progress.setValue(0)
        else:
            self.lbl_batch_title.setText(
                "Pilih atau buat batch pekerjaan untuk memulai digitalisasi."
            )
            self.lbl_batch_percent.setText("0%")
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
                item.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)
                self.log_table.setItem(row, col, item)
