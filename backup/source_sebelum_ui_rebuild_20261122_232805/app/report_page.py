"""Rekapitulasi batch dan ekspor laporan, koordinat, serta paket arsip."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QFrame, QHBoxLayout, QLabel, QMessageBox,
    QPushButton, QTableWidgetItem, QVBoxLayout, QWidget,
)

from config import STATUS_LABELS
from database.db import get_all_batches, get_documents_by_batch
from services.export_service import (
    check_batch_readiness, export_batch_to_csv, export_batch_to_excel,
    export_batch_to_zip,
)
from ui.components.data_table import DataTable
from ui.components.form_field import InlineField
from ui.components.guide_banner import GuideBanner
from ui.components.page_header import PageHeader
from ui.components.section_card import SectionCard


class ReportPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.active_batch_id = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)
        layout.addWidget(PageHeader(
            "Laporan & Ekspor",
            "Periksa kesiapan batch, lalu unduh rekap Excel, CSV, atau paket ZIP.",
        ))

        layout.addWidget(GuideBanner("Cara ekspor rekap", [
            "Pilih batch wilayah pada dropdown di bawah.",
            "Perhatikan status kesiapan: hijau berarti seluruh dokumen sudah selesai.",
            "Gunakan <b>Ekspor Excel</b> untuk rekap resmi dan <b>Ekspor CSV</b> untuk data sederhana.",
            "Gunakan <b>Paket ZIP</b> jika akan memindahkan seluruh DWG dan koordinat ke komputer lain.",
        ]))

        selector = QFrame()
        selector.setObjectName("SectionCard")
        selector_layout = QHBoxLayout(selector)
        selector_layout.setContentsMargins(16, 10, 16, 10)
        self.combo_batches = QComboBox()
        self.combo_batches.setMinimumWidth(340)
        self.combo_batches.currentIndexChanged.connect(self._on_batch_changed)
        selector_layout.addWidget(InlineField(
            "Batch Wilayah", "Pilih desa yang akan dibuatkan rekapitulasinya.",
            self.combo_batches,
        ), 1)

        self.btn_refresh = QPushButton("Segarkan")
        self.btn_refresh.setProperty("class", "btn-secondary")
        self.btn_refresh.clicked.connect(self.load_batches)
        selector_layout.addWidget(self.btn_refresh)
        layout.addWidget(selector)

        self.readiness_card = QFrame()
        self.readiness_card.setObjectName("ReadinessCard")
        readiness_layout = QHBoxLayout(self.readiness_card)
        readiness_layout.setContentsMargins(16, 12, 16, 12)
        self.lbl_readiness = QLabel("Pilih batch untuk memeriksa kesiapan.")
        self.lbl_readiness.setObjectName("ReadinessText")
        self.lbl_readiness.setWordWrap(True)
        readiness_layout.addWidget(self.lbl_readiness)
        layout.addWidget(self.readiness_card)

        export_card = SectionCard("Berkas yang diekspor")
        buttons = QHBoxLayout()
        for text, css, tip, slot in [
            ("Ekspor Excel (.xlsx)", "btn-primary", "Simpan rekap resmi ke format Excel.", self._export_excel),
            ("Ekspor CSV (.csv)", "btn-secondary", "Simpan rekap sederhana ke format CSV.", self._export_csv),
            ("Paket ZIP (DWG + Koordinat + Excel)", "btn-success", "Arsipkan seluruh berkas batch ke satu ZIP.", self._export_zip),
        ]:
            btn = QPushButton(text)
            btn.setProperty("class", css)
            btn.setToolTip(tip)
            btn.clicked.connect(slot)
            buttons.addWidget(btn)
        buttons.addStretch()
        export_card.body_layout.addLayout(buttons)
        layout.addWidget(export_card)

        self.table_preview = DataTable(6)
        self.table_preview.setHorizontalHeaderLabels([
            "No", "Identitas Dokumen", "Hak / Nomor", "GS / Tahun",
            "Luas Dok → DWG (m²)", "Status",
        ])
        self.table_preview.set_columns([48, 0, 170, 130, 190, 160], stretch_column=1)
        self.table_preview.set_empty_text("Belum ada batch atau dokumen untuk ditampilkan.")
        layout.addWidget(self.table_preview, 1)

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

    def _refresh_batch_details(self, batch_id: int):
        readiness = check_batch_readiness(batch_id)
        ready = bool(readiness["is_ready"])
        if ready:
            self.lbl_readiness.setText(
                f"Siap diekspor — seluruh {readiness['selesai']} dokumen dalam batch sudah selesai."
            )
        else:
            self.lbl_readiness.setText(
                f"Belum siap — {readiness['pending_count']} dari {readiness['total']} dokumen "
                "belum selesai. Anda tetap bisa mengekspor setelah konfirmasi."
            )
        self._set_readiness_tone(ready)

        docs = get_documents_by_batch(batch_id)
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
            self, "Batch Belum Selesai",
            f"{readiness['pending_count']} dokumen belum berstatus selesai.\n\n"
            "Tetap ekspor rekap saat ini?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        return reply == QMessageBox.Yes

    def _export_excel(self):
        self._save_export("Rekapitulasi Excel", "xlsx", "Excel Files (*.xlsx)", export_batch_to_excel)

    def _export_csv(self):
        self._save_export("Rekapitulasi CSV", "csv", "CSV Files (*.csv)", export_batch_to_csv)

    def _export_zip(self):
        self._save_export("Paket ZIP", "zip", "ZIP Archives (*.zip)", export_batch_to_zip)

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
            QMessageBox.information(self, "Ekspor Berhasil", f"Berkas disimpan di:\n{msg}")
        else:
            QMessageBox.critical(self, "Ekspor Gagal", msg)
