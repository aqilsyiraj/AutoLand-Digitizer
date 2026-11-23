"""Antrean dokumen: import PDF, cari/filter, dan jalankan digitasi otomatis."""

import os
import shutil

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from config import (
    DOKUMEN_MASUK_DIR,
    STATUS_LABELS,
    STATUS_LIST,
    STATUS_MENUNGGU,
    STATUS_SELESAI,
)
from database.db import (
    create_document,
    delete_document,
    get_batch,
    get_batch_stats,
    get_document,
    get_documents_by_batch,
)
from ui.components.button import Button
from ui.components.data_table import DataTable, RowActions
from ui.components.form_field import InlineField
from ui.components.page_header import PageHeader
from ui.components.status_badge import StatusBadge


class QueuePage(QWidget):
    start_process_doc = Signal(int)
    navigate_to_digitize = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.active_batch_id = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(14)

        header = PageHeader(
            "PDF & Antrean",
            "Impor denah PDF, lalu proses satu per satu. Batch aktif harus dipilih dulu.",
            eyebrow="Antrean",
        )
        self.btn_import_pdf = Button(
            "Import PDF",
            size="md",
            tone="primary",
            tooltip="Pilih satu atau beberapa PDF denah tanah untuk ditambahkan ke batch aktif",
        )
        self.btn_import_pdf.clicked.connect(self._import_pdf_dialog)
        header.add_action(self.btn_import_pdf)
        layout.addWidget(header)

        # ---------- Ringkasan batch + angka ----------
        summary = QFrame()
        summary.setObjectName("Card")
        summary_layout = QHBoxLayout(summary)
        summary_layout.setContentsMargins(16, 12, 16, 12)
        summary_layout.setSpacing(18)

        info_box = QVBoxLayout()
        info_box.setSpacing(2)
        info_tag = QLabel("BATCH AKTIF")
        info_tag.setObjectName("MicroLabel")
        info_box.addWidget(info_tag)
        self.lbl_batch_info = QLabelRingkas(
            "Pilih batch aktif pada menu '2. Batch / Desa'."
        )
        info_box.addWidget(self.lbl_batch_info)
        summary_layout.addLayout(info_box, 1)

        self.lbl_stat_total = self._stat_block(summary_layout, "Total dokumen")
        self.lbl_stat_selesai = self._stat_block(summary_layout, "Selesai")
        self.lbl_stat_sisa = self._stat_block(summary_layout, "Belum selesai")
        layout.addWidget(summary)

        # ---------- Filter ----------
        filters = QFrame()
        filters.setObjectName("Card")
        filter_layout = QHBoxLayout(filters)
        filter_layout.setContentsMargins(16, 10, 16, 10)
        filter_layout.setSpacing(12)

        self.input_search = QLineEdit()
        self.input_search.setPlaceholderText(
            "Cari nama PDF, identitas, nomor hak, atau GS…"
        )
        self.input_search.textChanged.connect(self.load_data)
        filter_layout.addWidget(
            InlineField(
                "Cari",
                "Ketik sebagian nama file atau identitas, misalnya GS176.",
                self.input_search,
            ),
            1,
        )

        self.combo_status = QComboBox()
        self.combo_status.addItem("Semua status", None)
        for status in STATUS_LIST:
            self.combo_status.addItem(STATUS_LABELS.get(status, status), status)
        self.combo_status.setMinimumWidth(150)
        self.combo_status.currentIndexChanged.connect(self.load_data)
        filter_layout.addWidget(
            InlineField(
                "Status", "Saring daftar berdasarkan tahap pengerjaan.", self.combo_status
            )
        )

        self.btn_refresh = Button(
            "Segarkan", size="sm", tone="secondary",
            tooltip="Muat ulang daftar dokumen dari database lokal",
        )
        self.btn_refresh.clicked.connect(self.load_data)
        filter_layout.addWidget(self.btn_refresh, 0, Qt.AlignBottom)
        layout.addWidget(filters)

        # ---------- Tabel ----------
        self.table_queue = DataTable(6)
        self.table_queue.setHorizontalHeaderLabels(
            [
                "No",
                "Nama File PDF",
                "Identitas Dokumen",
                "Luas Dok / Awal (m²)",
                "Status",
                "Aksi",
            ]
        )
        self.table_queue.set_columns([44, 0, 150, 140, 132, 224], stretch_column=1)
        self.table_queue.verticalHeader().setDefaultSectionSize(44)
        self.table_queue.set_empty_text(
            "Belum ada dokumen pada batch ini. Klik 'Import PDF' untuk menambahkan berkas."
        )
        layout.addWidget(self.table_queue, 1)

    @staticmethod
    def _stat_block(parent_layout: QHBoxLayout, caption: str) -> QLabel:
        box = QVBoxLayout()
        box.setSpacing(0)
        value = QLabel("0")
        value.setObjectName("StatValue")
        value.setStyleSheet("font-size: 20px;")
        cap = QLabel(caption)
        cap.setObjectName("StatSubtitle")
        box.addWidget(value)
        box.addWidget(cap)
        parent_layout.addLayout(box)
        return value

    def set_active_batch(self, batch_id: int):
        self.active_batch_id = batch_id
        if batch_id:
            batch = get_batch(batch_id)
            if batch:
                self.lbl_batch_info.setText(
                    f"<b>Desa {batch['nama_desa']}</b> · "
                    f"Kec. {batch['kecamatan']} · {batch['kabupaten']}"
                )
                self.btn_import_pdf.setEnabled(True)
            else:
                self.lbl_batch_info.setText("Batch aktif tidak ditemukan.")
                self.btn_import_pdf.setEnabled(False)
        else:
            self.lbl_batch_info.setText("Pilih batch aktif pada menu '2. Batch / Desa'.")
            self.btn_import_pdf.setEnabled(False)
        self.load_data()

    def load_data(self):
        if not self.active_batch_id:
            self.table_queue.setRowCount(0)
            self._set_summary(0, 0, 0)
            return

        stats = get_batch_stats(self.active_batch_id)
        self._set_summary(stats["total"], stats["selesai"], stats["sisa"])

        docs = get_documents_by_batch(
            self.active_batch_id,
            status_filter=self.combo_status.currentData(),
            search_query=self.input_search.text().strip(),
        )
        self.table_queue.setRowCount(len(docs))

        for row, doc in enumerate(docs):
            doc_id = doc["id"]
            status = doc.get("status", STATUS_MENUNGGU)
            completed = status == STATUS_SELESAI

            number = QTableWidgetItem(str(row + 1))
            number.setTextAlignment(Qt.AlignCenter)
            self.table_queue.setItem(row, 0, number)

            file_item = QTableWidgetItem(doc["nama_pdf"])
            file_item.setToolTip(doc["nama_pdf"])
            self.table_queue.setItem(row, 1, file_item)

            identity = QTableWidgetItem(doc.get("identitas_dokumen") or "—")
            identity.setToolTip(doc.get("identitas_dokumen") or "Belum diisi")
            self.table_queue.setItem(row, 2, identity)

            doc_area = doc.get("luas_dokumen")
            drawn_area = doc.get("luas_awal")
            area = QTableWidgetItem(
                f"{doc_area:.2f} / {drawn_area:.2f}" if doc_area and drawn_area else "—"
            )
            area.setTextAlignment(Qt.AlignCenter)
            self.table_queue.setItem(row, 3, area)

            self.table_queue.setCellWidget(row, 4, self._badge_cell(status))
            self.table_queue.setCellWidget(
                row, 5, self._actions(doc_id, doc, completed)
            )

    @staticmethod
    def _badge_cell(status: str) -> QWidget:
        box = QWidget()
        lay = QHBoxLayout(box)
        lay.setContentsMargins(6, 4, 6, 4)
        lay.setSpacing(0)
        lay.addStretch()
        lay.addWidget(StatusBadge(status))
        lay.addStretch()
        return box

    def _set_summary(self, total, selesai, sisa):
        self.lbl_stat_total.setText(str(total))
        self.lbl_stat_selesai.setText(str(selesai))
        self.lbl_stat_sisa.setText(str(sisa))

    def _actions(self, doc_id, doc, completed) -> QWidget:
        buttons = []
        if completed:
            dwg_path = doc.get("path_dwg", "")
            btn_dwg = Button(
                "DWG",
                size="xs",
                tone="success",
                tooltip="Buka file DWG hasil digitasi di AutoCAD",
            )
            btn_dwg.setEnabled(bool(dwg_path and os.path.exists(dwg_path)))
            btn_dwg.clicked.connect(
                lambda checked=False, p=dwg_path: self._open_dwg(p)
            )
            buttons.append(btn_dwg)

            btn_again = Button(
                "Ulang", size="xs", tone="secondary",
                tooltip="Buka kembali wizard untuk dokumen ini",
            )
            btn_again.clicked.connect(
                lambda checked=False, id_=doc_id: self.start_process_doc.emit(id_)
            )
            buttons.append(btn_again)
        else:
            btn_process = Button(
                "Proses", size="xs", tone="primary",
                tooltip="Deteksi polyline, periksa hasil, lalu buat DWG",
            )
            btn_process.clicked.connect(
                lambda checked=False, id_=doc_id: self.start_process_doc.emit(id_)
            )
            buttons.append(btn_process)

        btn_delete = Button(
            "Hapus", size="xs", tone="danger",
            tooltip="Hapus dokumen dari antrean (tidak dapat dibatalkan)",
        )
        btn_delete.clicked.connect(
            lambda checked=False, id_=doc_id: self._delete_doc(id_)
        )
        buttons.append(btn_delete)
        return RowActions(buttons)

    def _import_pdf_dialog(self):
        if not self.active_batch_id:
            QMessageBox.warning(self, "Belum Ada Batch", "Pilih batch aktif terlebih dahulu.")
            return

        paths, _ = QFileDialog.getOpenFileNames(
            self, "Pilih PDF Denah Tanah", "", "File PDF (*.pdf)"
        )
        if not paths:
            return

        known = {
            os.path.basename(d.get("nama_pdf", "")).lower()
            for d in get_documents_by_batch(self.active_batch_id)
        }
        added = skipped = 0
        for path in paths:
            filename = os.path.basename(path)
            if filename.lower() in known:
                skipped += 1
                continue
            known.add(filename.lower())
            folder = DOKUMEN_MASUK_DIR / f"Batch_{self.active_batch_id}"
            folder.mkdir(parents=True, exist_ok=True)
            local_path = folder / filename
            try:
                shutil.copy2(path, str(local_path))
                used_path = str(local_path)
            except Exception:
                used_path = path
            create_document(
                batch_id=self.active_batch_id,
                nama_pdf=filename,
                path_pdf=used_path,
                status=STATUS_MENUNGGU,
            )
            added += 1

        skip_note = (
            f"\n{skipped} file dilewati karena nama PDF sudah ada di batch ini."
            if skipped
            else ""
        )
        QMessageBox.information(
            self,
            "Import Selesai",
            f"{added} dokumen ditambahkan ke antrean.{skip_note}\n\n"
            "Klik 'Proses' pada baris dokumen untuk melanjutkan.",
        )
        self.load_data()

    def _open_dwg(self, path: str):
        if os.path.exists(path):
            os.startfile(path)
        else:
            QMessageBox.warning(
                self, "File Tidak Ditemukan", f"File DWG tidak ditemukan di:\n{path}"
            )

    def _delete_doc(self, doc_id: int):
        doc = get_document(doc_id)
        if not doc:
            return
        reply = QMessageBox.question(
            self,
            "Hapus Dokumen",
            f"Hapus dokumen berikut?\n\n• File: {doc['nama_pdf']}\n"
            f"• Identitas: {doc.get('identitas_dokumen') or '-'}\n\n"
            "Tindakan ini tidak dapat dibatalkan.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            delete_document(doc_id)
            self.load_data()


class QLabelRingkas(QLabel):
    """Label satu baris dengan gaya teks tubuh yang konsisten."""

    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self.setObjectName("PageSubtitle")
        self.setTextFormat(Qt.RichText)
        self.setWordWrap(True)
