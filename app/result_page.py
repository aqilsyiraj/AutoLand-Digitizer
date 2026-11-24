"""Hasil digitasi: daftar DWG selesai dengan akses cepat ke berkas."""

import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from config import HASIL_DIGITASI_DIR, STATUS_SELESAI
from database.db import get_all_documents
from ui.components.button import Button
from ui.components.data_table import DataTable, RowActions
from ui.components.form_field import InlineField
from ui.components.page_header import PageHeader


class ResultPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(14)

        header = PageHeader(
            "Hasil Digitasi DWG",
            "Gambar AutoCAD yang sudah diskalakan dan disimpan.",
            eyebrow="Arsip",
        )
        self.btn_open_folder = Button(
            "Folder Hasil", size="md", tone="secondary",
            tooltip="Buka folder hasil_digitasi di Windows Explorer",
        )
        self.btn_open_folder.clicked.connect(self._open_results_folder)
        header.add_action(self.btn_open_folder)

        self.btn_refresh = Button(
            "Segarkan", size="md", tone="primary",
            tooltip="Muat ulang daftar hasil dari database",
        )
        self.btn_refresh.clicked.connect(self.load_data)
        header.add_action(self.btn_refresh)
        layout.addWidget(header)

        # ---------- Ringkasan arsip ----------
        summary = QFrame()
        summary.setObjectName("Card")
        summary_layout = QHBoxLayout(summary)
        summary_layout.setContentsMargins(16, 12, 16, 12)
        summary_layout.setSpacing(26)

        intro = QVBoxLayout()
        intro.setSpacing(1)
        intro_tag = QLabel("ARSIP DWG")
        intro_tag.setObjectName("MicroLabel")
        intro_title = QLabel("Satu DWG desa berisi seluruh denah")
        intro_title.setObjectName("SectionTitle")
        intro.addWidget(intro_tag)
        intro.addWidget(intro_title)
        summary_layout.addLayout(intro, 1)

        self.lbl_stat_total = self._stat_block(summary_layout, "Total denah")
        self.lbl_stat_area = self._stat_block(summary_layout, "Total luas (m²)")
        self.lbl_stat_batch = self._stat_block(summary_layout, "DWG desa")
        layout.addWidget(summary)

        # ---------- Pencarian ----------
        search_card = QFrame()
        search_card.setObjectName("Card")
        search_layout = QHBoxLayout(search_card)
        search_layout.setContentsMargins(16, 10, 16, 10)
        self.input_search = QLineEdit()
        self.input_search.setPlaceholderText(
            "Cari identitas, nama file DWG, atau desa…"
        )
        self.input_search.textChanged.connect(self.load_data)
        search_layout.addWidget(
            InlineField(
                "Cari", "Ketik identitas, nama berkas, atau nama desa.", self.input_search
            ),
            1,
        )
        layout.addWidget(search_card)

        self.table_results = DataTable(6)
        self.table_results.setHorizontalHeaderLabels(
            [
                "Desa",
                "Identitas",
                "Luas Dok → DWG",
                "Skala",
                "Selesai",
                "Aksi",
            ]
        )
        self.table_results.set_columns([118, 0, 136, 96, 124, 312], stretch_column=1)
        self.table_results.verticalHeader().setDefaultSectionSize(44)
        self.table_results.set_empty_text(
            "Belum ada hasil digitasi. Selesaikan satu dokumen pada menu '3. PDF & Antrean'."
        )
        layout.addWidget(self.table_results, 1)

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

    def load_data(self):
        query = self.input_search.text().strip()
        documents = get_all_documents(search_query=query or None)
        completed = [d for d in documents if d.get("status") == STATUS_SELESAI]
        self.table_results.setRowCount(len(completed))

        total_area = 0.0
        desa_set = set()
        for row, doc in enumerate(completed):
            desa_set.add(doc.get("nama_desa") or "-")
            total_area += float(doc.get("luas_akhir") or 0.0)

            desa = QTableWidgetItem(f"Desa {doc.get('nama_desa', '-')}")
            self.table_results.setItem(row, 0, desa)

            identity = QTableWidgetItem(doc.get("identitas_dokumen") or "—")
            identity.setToolTip(doc.get("identitas_dokumen") or "Belum diisi")
            self.table_results.setItem(row, 1, identity)

            doc_area = doc.get("luas_dokumen") or 0.0
            final_area = doc.get("luas_akhir") or 0.0
            area = QTableWidgetItem(f"{doc_area:.2f} → {final_area:.2f}")
            area.setTextAlignment(Qt.AlignCenter)
            self.table_results.setItem(row, 2, area)

            factor = QTableWidgetItem(f"{doc.get('faktor_scaling') or 0:.6f}")
            factor.setTextAlignment(Qt.AlignCenter)
            self.table_results.setItem(row, 3, factor)

            time_item = QTableWidgetItem(
                doc.get("completed_at") or doc.get("updated_at") or "-"
            )
            time_item.setTextAlignment(Qt.AlignCenter)
            self.table_results.setItem(row, 4, time_item)

            self.table_results.setCellWidget(row, 5, self._actions(doc))

        self.lbl_stat_total.setText(str(len(completed)))
        self.lbl_stat_area.setText(f"{total_area:,.2f}")
        self.lbl_stat_batch.setText(str(len(desa_set)))

    def _actions(self, doc) -> QWidget:
        dwg_path = doc.get("path_dwg", "")

        btn_dwg = Button(
            "DWG Desa", size="xs", tone="success",
            tooltip="Buka DWG desa (satu file berisi seluruh denah desa ini)",
        )
        btn_dwg.setEnabled(bool(dwg_path and os.path.exists(dwg_path)))
        btn_dwg.clicked.connect(lambda checked=False, p=dwg_path: self._open_file(p))

        btn_folder = Button(
            "Folder", size="xs", tone="secondary",
            tooltip="Buka folder penyimpanan berkas DWG",
        )
        btn_folder.setEnabled(
            bool(dwg_path and os.path.exists(os.path.dirname(dwg_path)))
        )
        btn_folder.clicked.connect(
            lambda checked=False, p=dwg_path: self._open_folder_file(p)
        )

        coord_path = doc.get("koordinat_csv", "")
        btn_coord = Button(
            "Koord.", size="xs", tone="secondary",
            tooltip="Buka berkas koordinat CSV",
        )
        btn_coord.setEnabled(bool(coord_path and os.path.exists(coord_path)))
        btn_coord.clicked.connect(
            lambda checked=False, p=coord_path: self._open_file(p)
        )

        return RowActions([btn_dwg, btn_folder, btn_coord])

    def _open_file(self, path: str):
        if path and os.path.exists(path):
            os.startfile(path)
        else:
            QMessageBox.warning(
                self, "File Tidak Ditemukan", f"Berkas tidak ditemukan di:\n{path}"
            )

    def _open_folder_file(self, file_path: str):
        folder = os.path.dirname(file_path)
        if folder and os.path.exists(folder):
            os.startfile(folder)

    def _open_results_folder(self):
        if HASIL_DIGITASI_DIR.exists():
            os.startfile(str(HASIL_DIGITASI_DIR))
        else:
            QMessageBox.information(self, "Folder Belum Ada", "Folder hasil belum tersedia.")
