"""
AutoLand Digitizer - Result Page (dengan Panduan & Akses Berkas Cepat)
Menampilkan daftar seluruh dokumen DWG hasil digitasi, metrik luas akhir, dan akses file langsung.
"""

import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox
)
from PySide6.QtCore import Qt

from config import STATUS_SELESAI, HASIL_DIGITASI_DIR
from database.db import get_all_documents, get_batch
from ui.components.guide_banner import GuideBanner

class ResultPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 20, 24, 24)
        main_layout.setSpacing(14)

        # Header
        header_layout = QHBoxLayout()
        header_text = QVBoxLayout()
        header_text.setSpacing(3)
        title = QLabel("Hasil Digitasi Gambar AutoCAD (DWG)")
        title.setStyleSheet("font-size: 20px; font-weight: 800; color: #0F172A;")
        header_text.addWidget(title)

        subtitle = QLabel("Daftar seluruh berkas DWG yang telah selesai diproses, diskalakan, dan disimpan.")
        subtitle.setStyleSheet("color: #64748B; font-size: 13px;")
        header_text.addWidget(subtitle)
        header_layout.addLayout(header_text)

        header_layout.addStretch()

        self.btn_open_folder = QPushButton("📂 Buka Folder Hasil (Windows Explorer)")
        self.btn_open_folder.setProperty("class", "btn-secondary")
        self.btn_open_folder.setStyleSheet("font-weight: 700; padding: 8px 14px;")
        self.btn_open_folder.clicked.connect(self._open_results_folder)
        header_layout.addWidget(self.btn_open_folder)

        self.btn_refresh = QPushButton("Segarkan")
        self.btn_refresh.setProperty("class", "btn-primary")
        self.btn_refresh.clicked.connect(self.load_data)
        header_layout.addWidget(self.btn_refresh)

        main_layout.addLayout(header_layout)

        # Panduan Hasil Digitasi
        result_guide = [
            "Tabel ini hanya menampilkan dokumen yang telah berstatus <b>SELESAI</b> dan tersimpan sebagai file DWG.",
            "Klik tombol hijau <b>'📁 Buka DWG'</b> untuk langsung membuka file gambar tersebut di software AutoCAD Desktop.",
            "Klik tombol <b>'Buka Folder'</b> untuk melihat lokasi file DWG tersebut di Windows File Explorer.",
            "Bandingkan kolom <b>Luas Dokumen</b> dengan <b>Luas Akhir DWG</b> untuk memastikan keakuratan hasil scaling."
        ]
        self.guide_banner = GuideBanner("Petunjuk Menu Hasil Digitasi", result_guide)
        main_layout.addWidget(self.guide_banner)

        # Search Bar
        search_card = QFrame()
        search_card.setStyleSheet("background-color: #FFFFFF; border-radius: 8px; border: 1px solid #E2E8F0; padding: 10px;")
        s_layout = QHBoxLayout(search_card)
        s_layout.setContentsMargins(12, 6, 12, 6)
        s_layout.setSpacing(12)

        lbl_s = QLabel("Cari Dokumen Selesai:")
        lbl_s.setStyleSheet("font-weight: 600; color: #475569;")
        s_layout.addWidget(lbl_s)

        self.input_search = QLineEdit()
        self.input_search.setPlaceholderText("Cari identitas (contoh: M. 1342), nama file DWG, atau desa...")
        self.input_search.textChanged.connect(self.load_data)
        s_layout.addWidget(self.input_search, 1)

        main_layout.addWidget(search_card)

        # Tabel Hasil Digitasi
        self.table_results = QTableWidget()
        self.table_results.setColumnCount(8)
        self.table_results.setHorizontalHeaderLabels([
            "No", "Desa / Batch", "Identitas Resmi", "Luas Dokumen (m²)",
            "Luas Akhir DWG (m²)", "Faktor Scaling", "Waktu Selesai", "Aksi / Tindakan"
        ])
        self.table_results.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table_results.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table_results.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table_results.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table_results.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table_results.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.table_results.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeToContents)
        self.table_results.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeToContents)
        self.table_results.verticalHeader().setVisible(False)
        self.table_results.setSelectionBehavior(QTableWidget.SelectRows)
        self.table_results.setEditTriggers(QTableWidget.NoEditTriggers)

        main_layout.addWidget(self.table_results, 1)

    def load_data(self):
        query = self.input_search.text().strip()
        all_docs = get_all_documents(search_query=query if query else None)
        completed_docs = [d for d in all_docs if d.get("status") == STATUS_SELESAI]

        self.table_results.setRowCount(len(completed_docs))

        for row, doc in enumerate(completed_docs):
            it_no = QTableWidgetItem(str(row + 1))
            it_no.setTextAlignment(Qt.AlignCenter)
            self.table_results.setItem(row, 0, it_no)

            desa_text = f"Desa {doc.get('nama_desa', '-')}"
            self.table_results.setItem(row, 1, QTableWidgetItem(desa_text))

            identitas = doc.get("identitas_dokumen", "-")
            it_id = QTableWidgetItem(identitas)
            it_id.setFont(it_id.font())
            it_id.setForeground(Qt.darkBlue)
            self.table_results.setItem(row, 2, it_id)

            ld = doc.get("luas_dokumen") or 0.0
            it_ld = QTableWidgetItem(f"{ld:.2f}")
            it_ld.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table_results.setItem(row, 3, it_ld)

            la = doc.get("luas_akhir") or 0.0
            it_la = QTableWidgetItem(f"{la:.2f}")
            it_la.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table_results.setItem(row, 4, it_la)

            sf = doc.get("faktor_scaling") or 0.0
            it_sf = QTableWidgetItem(f"{sf:.6f}")
            it_sf.setTextAlignment(Qt.AlignCenter)
            self.table_results.setItem(row, 5, it_sf)

            waktu = doc.get("completed_at") or doc.get("updated_at") or "-"
            it_w = QTableWidgetItem(waktu)
            it_w.setTextAlignment(Qt.AlignCenter)
            self.table_results.setItem(row, 6, it_w)

            # Tombol Aksi
            act_widget = QWidget()
            act_layout = QHBoxLayout(act_widget)
            act_layout.setContentsMargins(4, 2, 4, 2)
            act_layout.setSpacing(6)

            dwg_path = doc.get("path_dwg", "")
            btn_open = QPushButton("📁 Buka DWG")
            btn_open.setStyleSheet("""
                QPushButton {
                    background-color: #059669;
                    color: #FFFFFF;
                    font-weight: 700;
                    padding: 5px 10px;
                    border-radius: 5px;
                }
                QPushButton:hover { background-color: #047857; }
            """)
            btn_open.setEnabled(bool(dwg_path and os.path.exists(dwg_path)))
            btn_open.setToolTip("Buka gambar DWG ini langsung di AutoCAD")
            btn_open.clicked.connect(lambda checked=False, p=dwg_path: self._open_file(p))
            act_layout.addWidget(btn_open)

            btn_dir = QPushButton("Buka Folder")
            btn_dir.setProperty("class", "btn-secondary")
            btn_dir.setEnabled(bool(dwg_path and os.path.exists(os.path.dirname(dwg_path))))
            btn_dir.setToolTip("Buka folder penyimpanan Windows Explorer")
            btn_dir.clicked.connect(lambda checked=False, p=dwg_path: self._open_folder_file(p))
            act_layout.addWidget(btn_dir)

            self.table_results.setCellWidget(row, 7, act_widget)

    def _open_file(self, path: str):
        if path and os.path.exists(path):
            os.startfile(path)
        else:
            QMessageBox.warning(self, "File Hilang", f"File DWG tidak ditemukan di:\n{path}")

    def _open_folder_file(self, file_path: str):
        folder = os.path.dirname(file_path)
        if folder and os.path.exists(folder):
            os.startfile(folder)

    def _open_results_folder(self):
        if HASIL_DIGITASI_DIR.exists():
            os.startfile(str(HASIL_DIGITASI_DIR))
