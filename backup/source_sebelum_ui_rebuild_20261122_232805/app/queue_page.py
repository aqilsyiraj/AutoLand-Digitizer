"""Antrean dokumen: import PDF, cari/filter, dan jalankan digitasi otomatis."""

import os
import shutil
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
    QPushButton, QTableWidgetItem, QVBoxLayout, QWidget,
)

from config import (
    DOKUMEN_MASUK_DIR, STATUS_LABELS, STATUS_LIST, STATUS_MENUNGGU, STATUS_SELESAI,
)
from database.db import (
    create_document, delete_document, get_batch, get_batch_stats,
    get_document, get_documents_by_batch,
)
from ui.components.data_table import DataTable
from ui.components.form_field import InlineField
from ui.components.guide_banner import GuideBanner
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
        layout.setContentsMargins(18, 12, 18, 12)
        layout.setSpacing(8)

        header = PageHeader(
            "PDF & Antrean Dokumen",
            "Impor denah PDF, lalu proses satu per satu. Batch aktif harus dipilih terlebih dahulu.",
        )
        self.btn_import_pdf = QPushButton("+ Import PDF")
        self.btn_import_pdf.setProperty("class", "btn-primary")
        self.btn_import_pdf.setToolTip("Pilih satu atau beberapa PDF denah tanah untuk ditambahkan ke batch aktif")
        self.btn_import_pdf.clicked.connect(self._import_pdf_dialog)
        header.add_action(self.btn_import_pdf)
        layout.addWidget(header)

        self.lbl_batch_info = QLabelRingkas("Pilih batch aktif pada menu '2. Batch / Desa'.")
        layout.addWidget(self.lbl_batch_info)

        layout.addWidget(GuideBanner("Cara memproses dokumen", [
            "Klik <b>Import PDF</b> untuk menambahkan satu atau beberapa scan denah.",
            "Klik <b>Proses</b> pada baris dokumen. Sistem memilih halaman denah dan mendeteksi polyline.",
            "Periksa titik polyline, isi identitas dokumen, lalu jalankan proses pembuatan DWG.",
            "Setelah selesai, tersedia tombol <b>DWG</b> dan berkas koordinat. Tidak perlu menggambar manual di AutoCAD.",
        ]))

        summary = QFrame()
        summary.setObjectName("SectionCard")
        summary_layout = QHBoxLayout(summary)
        summary_layout.setContentsMargins(12, 7, 12, 7)
        summary_layout.setSpacing(20)
        self.lbl_stat_total = QLabelRingkas("Total Dokumen: <b>0</b>")
        self.lbl_stat_selesai = QLabelRingkas("Selesai: <b style='color:#047857;'>0</b>")
        self.lbl_stat_sisa = QLabelRingkas("Belum Selesai: <b style='color:#B45309;'>0</b>")
        for label in (self.lbl_stat_total, self.lbl_stat_selesai, self.lbl_stat_sisa):
            label.setToolTip("Ringkasan dokumen pada batch aktif")
            summary_layout.addWidget(label)
        summary_layout.addStretch()
        layout.addWidget(summary)

        filters = QFrame()
        filters.setObjectName("SectionCard")
        filter_layout = QHBoxLayout(filters)
        filter_layout.setContentsMargins(12, 7, 12, 7)
        filter_layout.setSpacing(12)

        self.input_search = QLineEdit()
        self.input_search.setPlaceholderText("Cari nama PDF, identitas, nomor hak, atau GS…")
        self.input_search.setMinimumWidth(240)
        self.input_search.textChanged.connect(self.load_data)
        filter_layout.addWidget(InlineField(
            "Cari", "Ketik sebagian nama file atau identitas, misalnya GS176.",
            self.input_search,
        ), 1)

        self.combo_status = QComboBox()
        self.combo_status.addItem("Semua status", None)
        for status in STATUS_LIST:
            self.combo_status.addItem(STATUS_LABELS.get(status, status), status)
        self.combo_status.setMinimumWidth(150)
        self.combo_status.currentIndexChanged.connect(self.load_data)
        filter_layout.addWidget(InlineField(
            "Status", "Saring daftar berdasarkan tahap pengerjaan.",
            self.combo_status,
        ))

        self.btn_refresh = QPushButton("Segarkan")
        self.btn_refresh.setProperty("class", "btn-secondary")
        self.btn_refresh.setToolTip("Muat ulang daftar dokumen dari database lokal")
        self.btn_refresh.clicked.connect(self.load_data)
        filter_layout.addWidget(self.btn_refresh)
        layout.addWidget(filters)

        self.table_queue = DataTable(6)
        self.table_queue.setHorizontalHeaderLabels([
            "No", "Nama File PDF", "Identitas Dokumen", "Luas Dok / Awal (m²)",
            "Status", "Aksi",
        ])
        self.table_queue.set_columns([38, 0, 140, 120, 130, 300], stretch_column=1)
        self.table_queue.verticalHeader().setDefaultSectionSize(44)
        self.table_queue.set_empty_text(
            "Belum ada dokumen pada batch ini. Klik 'Import PDF' untuk menambahkan berkas."
        )
        layout.addWidget(self.table_queue, 1)

    def set_active_batch(self, batch_id: int):
        self.active_batch_id = batch_id
        if batch_id:
            batch = get_batch(batch_id)
            if batch:
                self.lbl_batch_info.setText(
                    f"Batch aktif: <b>Desa {batch['nama_desa']}</b>, "
                    f"Kec. {batch['kecamatan']} ({batch['kabupaten']})"
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

        status_filter = self.combo_status.currentData()
        search = self.input_search.text().strip()
        docs = get_documents_by_batch(
            self.active_batch_id, status_filter=status_filter, search_query=search
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

            identity = QTableWidgetItem(doc.get("identitas_dokumen") or "-")
            identity.setToolTip(doc.get("identitas_dokumen") or "Belum diisi")
            if doc.get("identitas_dokumen"):
                identity.setForeground(Qt.darkBlue)
            self.table_queue.setItem(row, 2, identity)

            doc_area = doc.get("luas_dokumen")
            drawn_area = doc.get("luas_awal")
            area_text = (
                f"{doc_area:.2f} / {drawn_area:.2f}"
                if doc_area and drawn_area else "-"
            )
            area = QTableWidgetItem(area_text)
            area.setTextAlignment(Qt.AlignCenter)
            self.table_queue.setItem(row, 3, area)

            self.table_queue.setCellWidget(row, 4, StatusBadge(status))
            self.table_queue.setCellWidget(row, 5, self._actions(doc_id, doc, completed))

    def _set_summary(self, total, selesai, sisa):
        self.lbl_stat_total.setText(f"Total Dokumen: <b>{total}</b>")
        self.lbl_stat_selesai.setText(f"Selesai: <b style='color:#047857;'>{selesai}</b>")
        self.lbl_stat_sisa.setText(f"Belum Selesai: <b style='color:#B45309;'>{sisa}</b>")

    def _actions(self, doc_id, doc, completed) -> QWidget:
        widget = QWidget()
        row = QHBoxLayout(widget)
        row.setContentsMargins(2, 1, 2, 1)
        row.setSpacing(4)

        if completed:
            dwg_path = doc.get("path_dwg", "")
            btn_dwg = QPushButton("DWG")
            btn_dwg.setProperty("class", "btn-row")
            btn_dwg.setProperty("role", "success")
            btn_dwg.setEnabled(bool(dwg_path and os.path.exists(dwg_path)))
            btn_dwg.setToolTip("Buka file DWG hasil digitasi di AutoCAD")
            btn_dwg.clicked.connect(lambda checked=False, p=dwg_path: self._open_dwg(p))
            row.addWidget(btn_dwg)

            btn_again = QPushButton("Ulang")
            btn_again.setProperty("class", "btn-row")
            btn_again.setProperty("role", "secondary")
            btn_again.setToolTip("Buka kembali wizard untuk dokumen ini")
            btn_again.clicked.connect(
                lambda checked=False, id_=doc_id: self.start_process_doc.emit(id_)
            )
            row.addWidget(btn_again)
        else:
            btn_process = QPushButton("Proses")
            btn_process.setProperty("class", "btn-row")
            btn_process.setProperty("role", "primary")
            btn_process.setToolTip("Deteksi polyline, periksa hasil, lalu buat DWG")
            btn_process.clicked.connect(
                lambda checked=False, id_=doc_id: self.start_process_doc.emit(id_)
            )
            row.addWidget(btn_process)

        btn_delete = QPushButton("Hapus")
        btn_delete.setProperty("class", "btn-row")
        btn_delete.setProperty("role", "danger")
        btn_delete.setToolTip("Hapus dokumen dari antrean (tidak dapat dibatalkan)")
        btn_delete.clicked.connect(lambda checked=False, id_=doc_id: self._delete_doc(id_))
        row.addWidget(btn_delete)
        return widget

    def _import_pdf_dialog(self):
        if not self.active_batch_id:
            QMessageBox.warning(self, "Belum Ada Batch", "Pilih batch aktif terlebih dahulu.")
            return

        paths, _ = QFileDialog.getOpenFileNames(
            self, "Pilih PDF Denah Tanah", "", "File PDF (*.pdf)"
        )
        if not paths:
            return

        known = {os.path.basename(d.get("nama_pdf", "")).lower()
                 for d in get_documents_by_batch(self.active_batch_id)}
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
            if skipped else ""
        )
        QMessageBox.information(
            self, "Import Selesai",
            f"{added} dokumen ditambahkan ke antrean.{skip_note}\n\n"
            "Klik 'Proses' pada baris dokumen untuk melanjutkan.",
        )
        self.load_data()

    def _open_dwg(self, path: str):
        if os.path.exists(path):
            os.startfile(path)
        else:
            QMessageBox.warning(self, "File Tidak Ditemukan", f"File DWG tidak ditemukan di:\n{path}")

    def _delete_doc(self, doc_id: int):
        doc = get_document(doc_id)
        if not doc:
            return
        reply = QMessageBox.question(
            self, "Hapus Dokumen",
            f"Hapus dokumen berikut?\n\n• File: {doc['nama_pdf']}\n"
            f"• Identitas: {doc.get('identitas_dokumen') or '-'}\n\n"
            "Tindakan ini tidak dapat dibatalkan.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
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
