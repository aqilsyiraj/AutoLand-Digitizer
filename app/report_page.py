"""Rekapitulasi batch dan ekspor laporan, koordinat, serta paket arsip."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from config import STATUS_LABELS, STATUS_SELESAI
from database.db import get_all_batches, get_documents_by_batch
from services.export_service import (
    check_batch_readiness,
    export_batch_to_csv,
    export_batch_to_excel,
    export_batch_to_zip,
)
from ui.components.button import Button
from ui.components.data_table import DataTable
from ui.components.form_field import InlineField
from ui.components.guide_banner import GuideBanner
from ui.components.page_header import PageHeader
from ui.components.section_card import SectionCard
from ui.components.stat_card import StatCard


class ReportPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.active_batch_id = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(14)

        header = PageHeader(
            "Laporan & Ekspor",
            "Periksa kesiapan batch, lalu unduh rekap Excel, CSV, atau paket ZIP.",
            eyebrow="Arsip & Laporan",
        )
        self.btn_refresh = Button(
            "Segarkan",
            size="md",
            tone="secondary",
            tooltip="Muat ulang daftar batch dari database lokal",
        )
        self.btn_refresh.clicked.connect(self.load_batches)
        header.add_action(self.btn_refresh)
        layout.addWidget(header)

        # ---------- Ringkasan batch terpilih ----------
        stats = QHBoxLayout()
        stats.setSpacing(12)
        self.card_total = StatCard("Dokumen", "0", "Di batch terpilih", "#1D4ED8")
        self.card_selesai = StatCard("Selesai", "0", "Siap diekspor", "#15803D")
        self.card_belum = StatCard("Belum selesai", "0", "Masih dikerjakan", "#B45309")
        self.card_luas = StatCard("Total luas DWG", "0", "Meter persegi", "#0F766E")
        for card in (
            self.card_total,
            self.card_selesai,
            self.card_belum,
            self.card_luas,
        ):
            stats.addWidget(card, 1)
        layout.addLayout(stats)

        # ---------- Pemilih batch ----------
        selector = QFrame()
        selector.setObjectName("Card")
        selector_layout = QHBoxLayout(selector)
        selector_layout.setContentsMargins(16, 10, 16, 10)
        selector_layout.setSpacing(12)
        self.combo_batches = QComboBox()
        self.combo_batches.setMinimumWidth(320)
        self.combo_batches.currentIndexChanged.connect(self._on_batch_changed)
        selector_layout.addWidget(
            InlineField(
                "Batch Wilayah",
                "Pilih desa yang akan dibuatkan rekapitulasinya.",
                self.combo_batches,
            ),
            1,
        )
        layout.addWidget(selector)

        # ---------- Kesiapan + ekspor ----------
        action_row = QHBoxLayout()
        action_row.setSpacing(14)

        export_card = SectionCard(
            "Berkas yang Diekspor", "Semua format memakai data batch terpilih."
        )
        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        buttons.addWidget(
            Button(
                "Ekspor Excel",
                size="md",
                tone="primary",
                tooltip="Simpan rekap resmi ke format Excel (.xlsx)",
                on_click=self._export_excel,
            )
        )
        buttons.addWidget(
            Button(
                "Ekspor CSV",
                size="md",
                tone="secondary",
                tooltip="Simpan rekap sederhana ke format CSV",
                on_click=self._export_csv,
            )
        )
        buttons.addWidget(
            Button(
                "Paket ZIP",
                size="md",
                tone="success",
                tooltip="Arsipkan DWG, gambar denah, dan koordinat dalam satu ZIP",
                on_click=self._export_zip,
            )
        )
        buttons.addStretch()
        export_card.body_layout.addLayout(buttons)
        action_row.addWidget(export_card, 1)

        self.readiness_card = QFrame()
        self.readiness_card.setObjectName("ReadinessCard")
        readiness_layout = QVBoxLayout(self.readiness_card)
        readiness_layout.setContentsMargins(14, 11, 14, 11)
        readiness_layout.setSpacing(3)
        readiness_tag = QLabel("KESESIAPAN BATCH")
        readiness_tag.setObjectName("MicroLabel")
        readiness_layout.addWidget(readiness_tag)
        self.lbl_readiness = QLabel("Pilih batch untuk memeriksa kesiapan.")
        self.lbl_readiness.setObjectName("ReadinessText")
        self.lbl_readiness.setWordWrap(True)
        readiness_layout.addWidget(self.lbl_readiness)
        action_row.addWidget(self.readiness_card, 1)
        layout.addLayout(action_row)

        layout.addWidget(
            GuideBanner(
                "Cara ekspor rekap",
                [
                    "Pilih batch wilayah pada dropdown di atas.",
                    "Status hijau berarti seluruh dokumen sudah selesai.",
                    "<b>Ekspor Excel</b> untuk rekap resmi, <b>Ekspor CSV</b> untuk data sederhana.",
                    "<b>Paket ZIP</b> memindahkan DWG, gambar denah, dan koordinat ke komputer lain.",
                ],
            )
        )

        # ---------- Pratinjau isi rekap ----------
        preview_card = SectionCard(
            "Pratinjau Rekap", "Data inilah yang akan ditulis ke berkas ekspor."
        )
        self.table_preview = DataTable(6)
        self.table_preview.setHorizontalHeaderLabels(
            [
                "No",
                "Identitas Dokumen",
                "Hak / Nomor",
                "GS / Tahun",
                "Luas Dok → DWG (m²)",
                "Status",
            ]
        )
        self.table_preview.set_columns(
            [44, 0, 160, 124, 170, 148], stretch_column=1
        )
        self.table_preview.verticalHeader().setDefaultSectionSize(38)
        self.table_preview.set_empty_text(
            "Belum ada batch atau dokumen untuk ditampilkan."
        )
        preview_card.body_layout.addWidget(self.table_preview, 1)
        layout.addWidget(preview_card, 1)

    def load_batches(self):
        batches = get_all_batches()
        self.combo_batches.blockSignals(True)
        self.combo_batches.clear()
        if not batches:
            self.combo_batches.addItem("Belum ada batch", None)
        else:
            for batch in batches:
                label = (
                    f"Desa {batch['nama_desa']} "
                    f"({batch['kecamatan']}, {batch['kabupaten']}) — ID {batch['id']}"
                )
                self.combo_batches.addItem(label, batch["id"])
            if self.active_batch_id:
                idx = self.combo_batches.findData(self.active_batch_id)
                if idx >= 0:
                    self.combo_batches.setCurrentIndex(idx)
        self.combo_batches.blockSignals(False)
        self._on_batch_changed(self.combo_batches.currentIndex())

    def set_active_batch(self, batch_id: int):
        self.active_batch_id = batch_id
        self.load_batches()

    def _on_batch_changed(self, index: int):
        batch_id = self.combo_batches.currentData()
        if not batch_id:
            self.table_preview.setRowCount(0)
            self.lbl_readiness.setText("Pilih batch untuk memeriksa kesiapan.")
            self._set_readiness_tone(False)
            self._set_stats(0, 0, 0, 0.0)
            return
        self.active_batch_id = batch_id
        self._refresh_batch_details(batch_id)

    def _set_readiness_tone(self, ok: bool):
        tone = "ok" if ok else "warn"
        self.readiness_card.setProperty("tone", tone)
        self.lbl_readiness.setProperty("tone", tone)
        for widget in (self.readiness_card, self.lbl_readiness):
            widget.style().unpolish(widget)
            widget.style().polish(widget)

    def _set_stats(self, total: int, selesai: int, belum: int, luas: float):
        self.card_total.set_value(str(total))
        self.card_selesai.set_value(str(selesai))
        self.card_belum.set_value(str(belum))
        self.card_luas.set_value(f"{luas:,.2f}")

    def _refresh_batch_details(self, batch_id: int):
        readiness = check_batch_readiness(batch_id)
        ready = bool(readiness["is_ready"])
        if ready:
            self.lbl_readiness.setText(
                f"Siap diekspor — seluruh {readiness['selesai']} dokumen dalam batch "
                "sudah selesai."
            )
        else:
            self.lbl_readiness.setText(
                f"Belum siap — {readiness['pending_count']} dari {readiness['total']} "
                "dokumen belum selesai. Anda tetap bisa mengekspor setelah konfirmasi."
            )
        self._set_readiness_tone(ready)

        docs = get_documents_by_batch(batch_id)
        total_luas = sum(float(d.get("luas_akhir") or 0.0) for d in docs)
        selesai = sum(1 for d in docs if d.get("status") == STATUS_SELESAI)
        self._set_stats(len(docs), selesai, len(docs) - selesai, total_luas)

        self.table_preview.setRowCount(len(docs))
        for row, doc in enumerate(docs):
            values = [
                str(row + 1),
                doc.get("identitas_dokumen") or "-",
                f"{doc.get('jenis_hak') or '-'} / {doc.get('nomor_hak') or '-'}",
                f"{doc.get('nomor_gs') or '-'} / {doc.get('tahun') or '-'}",
                f"{(doc.get('luas_dokumen') or 0):.2f} → {(doc.get('luas_akhir') or 0):.2f}",
                STATUS_LABELS.get(doc.get("status", "-"), doc.get("status", "-")),
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                if col in (0, 3, 4, 5):
                    item.setTextAlignment(Qt.AlignCenter)
                self.table_preview.setItem(row, col, item)

    def _confirm_if_pending(self) -> bool:
        if not self.active_batch_id:
            return False
        readiness = check_batch_readiness(self.active_batch_id)
        if readiness["is_ready"]:
            return True
        reply = QMessageBox.warning(
            self,
            "Batch Belum Selesai",
            f"{readiness['pending_count']} dokumen belum berstatus selesai.\n\n"
            "Tetap ekspor rekap saat ini?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        return reply == QMessageBox.Yes

    def _export_excel(self):
        self._save_export(
            "Rekapitulasi Excel", "xlsx", "Excel Files (*.xlsx)", export_batch_to_excel
        )

    def _export_csv(self):
        self._save_export(
            "Rekapitulasi CSV", "csv", "CSV Files (*.csv)", export_batch_to_csv
        )

    def _export_zip(self):
        self._save_export(
            "Paket ZIP", "zip", "ZIP Archives (*.zip)", export_batch_to_zip
        )

    def _save_export(self, title: str, ext: str, pattern: str, exporter):
        if not self.active_batch_id:
            QMessageBox.warning(self, "Pilih Batch", "Pilih batch terlebih dahulu.")
            return
        if not self._confirm_if_pending():
            return
        default = f"Rekapitulasi_Batch_{self.active_batch_id}.{ext}"
        path, _ = QFileDialog.getSaveFileName(self, f"Simpan {title}", default, pattern)
        if not path:
            return
        ok, msg = exporter(self.active_batch_id, path)
        if ok:
            QMessageBox.information(
                self, "Ekspor Berhasil", f"Berkas disimpan di:\n{msg}"
            )
        else:
            QMessageBox.critical(self, "Ekspor Gagal", msg)
