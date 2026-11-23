"""Hasil digitasi: daftar DWG selesai dengan akses cepat ke berkas."""

import os
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLineEdit, QMessageBox, QPushButton,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from config import HASIL_DIGITASI_DIR, STATUS_SELESAI
from database.db import get_all_documents
from ui.components.data_table import DataTable
from ui.components.form_field import InlineField
from ui.components.guide_banner import GuideBanner
from ui.components.page_header import PageHeader


class ResultPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 12, 18, 12)
        layout.setSpacing(8)

        header = PageHeader(
            "Hasil Digitasi DWG",
            "Daftar gambar AutoCAD yang sudah selesai diskalakan dan disimpan.",
        )
        self.btn_open_folder = QPushButton("Folder Hasil")
        self.btn_open_folder.setProperty("class", "btn-secondary")
        self.btn_open_folder.setToolTip("Buka folder hasil_digitasi di Windows Explorer")
        self.btn_open_folder.clicked.connect(self._open_results_folder)
        header.add_action(self.btn_open_folder)

        self.btn_refresh = QPushButton("Segarkan")
        self.btn_refresh.setProperty("class", "btn-primary")
        self.btn_refresh.setToolTip("Muat ulang daftar hasil dari database")
        self.btn_refresh.clicked.connect(self.load_data)
        header.add_action(self.btn_refresh)
        layout.addWidget(header)

        layout.addWidget(GuideBanner("Tentang halaman ini", [
            "Hanya dokumen berstatus <b>Selesai</b> yang tampil di sini.",
            "Klik <b>DWG</b> untuk membuka gambar langsung di AutoCAD Desktop.",
            "Kolom <b>Luas Dok → DWG</b> membantu memeriksa hasil penskalaan.",
            "Berkas koordinat CSV/JSON tersedia melalui tombol <b>Koord.</b>.",
        ]))

        search_card = QFrame()
        search_card.setObjectName("SectionCard")
        search_layout = QHBoxLayout(search_card)
        search_layout.setContentsMargins(12, 7, 12, 7)
        self.input_search = QLineEdit()
        self.input_search.setPlaceholderText("Cari identitas, nama file DWG, atau desa…")
        self.input_search.setMinimumWidth(260)
        self.input_search.textChanged.connect(self.load_data)
        search_layout.addWidget(InlineField(
            "Cari", "Ketik identitas, nama berkas, atau nama desa.",
            self.input_search,
        ), 1)
        layout.addWidget(search_card)

        self.table_results = DataTable(6)
        self.table_results.setHorizontalHeaderLabels([
            "Desa", "Identitas", "Luas Dok → DWG",
            "Skala", "Selesai", "Aksi",
        ])
        self.table_results.set_columns([100, 0, 120, 78, 110, 310], stretch_column=1)
        self.table_results.verticalHeader().setDefaultSectionSize(44)
        self.table_results.set_empty_text(
            "Belum ada hasil digitasi. Selesaikan satu dokumen pada menu '3. PDF & Antrean'."
        )
        layout.addWidget(self.table_results, 1)

    def load_data(self):
        query = self.input_search.text().strip()
        documents = get_all_documents(search_query=query or None)
        completed = [doc for doc in documents if doc.get("status") == STATUS_SELESAI]
        self.table_results.setRowCount(len(completed))

        for row, doc in enumerate(completed):
            desa = QTableWidgetItem(f"Desa {doc.get('nama_desa', '-')}")
            self.table_results.setItem(row, 0, desa)

            identity = QTableWidgetItem(doc.get("identitas_dokumen") or "-")
            identity.setToolTip(doc.get("identitas_dokumen") or "Belum diisi")
            identity.setForeground(Qt.darkBlue)
            self.table_results.setItem(row, 1, identity)

            doc_area = doc.get("luas_dokumen") or 0.0
            final_area = doc.get("luas_akhir") or 0.0
            area = QTableWidgetItem(f"{doc_area:.2f} → {final_area:.2f}")
            area.setTextAlignment(Qt.AlignCenter)
            self.table_results.setItem(row, 2, area)

            factor = QTableWidgetItem(f"{doc.get('faktor_scaling') or 0:.6f}")
            factor.setTextAlignment(Qt.AlignCenter)
            self.table_results.setItem(row, 3, factor)

            time_item = QTableWidgetItem(doc.get("completed_at") or doc.get("updated_at") or "-")
            time_item.setTextAlignment(Qt.AlignCenter)
            self.table_results.setItem(row, 4, time_item)

            self.table_results.setCellWidget(row, 5, self._actions(doc))

    def _actions(self, doc) -> QWidget:
        widget = QWidget()
        row = QHBoxLayout(widget)
        row.setContentsMargins(2, 1, 2, 1)
        row.setSpacing(4)

        dwg_path = doc.get("path_dwg", "")
        btn_dwg = QPushButton("DWG")
        btn_dwg.setProperty("class", "btn-row")
        btn_dwg.setProperty("role", "success")
        btn_dwg.setEnabled(bool(dwg_path and os.path.exists(dwg_path)))
        btn_dwg.setToolTip("Buka gambar DWG di AutoCAD")
        btn_dwg.clicked.connect(lambda checked=False, p=dwg_path: self._open_file(p))
        row.addWidget(btn_dwg)

        btn_folder = QPushButton("Folder")
        btn_folder.setProperty("class", "btn-row")
        btn_folder.setProperty("role", "secondary")
        btn_folder.setEnabled(bool(dwg_path and os.path.exists(os.path.dirname(dwg_path))))
        btn_folder.setToolTip("Buka folder penyimpanan berkas DWG")
        btn_folder.clicked.connect(lambda checked=False, p=dwg_path: self._open_folder_file(p))
        row.addWidget(btn_folder)

        coord_path = doc.get("koordinat_csv", "")
        btn_coord = QPushButton("Koord.")
        btn_coord.setProperty("class", "btn-row")
        btn_coord.setProperty("role", "secondary")
        btn_coord.setEnabled(bool(coord_path and os.path.exists(coord_path)))
        btn_coord.setToolTip("Buka berkas koordinat CSV")
        btn_coord.clicked.connect(lambda checked=False, p=coord_path: self._open_file(p))
        row.addWidget(btn_coord)
        return widget

    def _open_file(self, path: str):
        if path and os.path.exists(path):
            os.startfile(path)
        else:
            QMessageBox.warning(self, "File Tidak Ditemukan", f"Berkas tidak ditemukan di:\n{path}")

    def _open_folder_file(self, file_path: str):
        folder = os.path.dirname(file_path)
        if folder and os.path.exists(folder):
            os.startfile(folder)

    def _open_results_folder(self):
        if HASIL_DIGITASI_DIR.exists():
            os.startfile(str(HASIL_DIGITASI_DIR))
        else:
            QMessageBox.information(self, "Folder Belum Ada", "Folder hasil belum tersedia.")
