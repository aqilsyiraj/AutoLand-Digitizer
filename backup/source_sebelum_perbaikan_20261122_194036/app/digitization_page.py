"""
AutoLand Digitizer - Digitization Page (Wizard Alur Kerja Terpandu)
Dirancang khusus agar operator tidak bingung: membagi proses menjadi 5 langkah berurutan,
lengkap dengan panduan di setiap langkah, indikator langkah aktif, dan tombol aksi yang jelas.
"""

import os
from datetime import datetime
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QComboBox, QDoubleSpinBox, QSpinBox,
    QMessageBox, QStackedWidget, QFileDialog, QScrollArea
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap

from config import (
    JENIS_HAK_MAP, STATUS_MENUNGGU, STATUS_PDF_DIPROSES,
    STATUS_MENUNGGU_TRACING, STATUS_MENUNGGU_SCALING,
    STATUS_MENUNGGU_VERIFIKASI, STATUS_SELESAI, STATUS_GAGAL,
    DEFAULT_TEMPLATE_PATH, HASIL_DIGITASI_DIR
)
from database.db import (
    get_document, update_document, get_batch, add_log, get_setting
)
from services.naming_service import (
    format_document_identity, sanitize_filename, validate_document_input,
    normalize_gs_number
)
from services.geometry_service import (
    calculate_scale_factor, analyze_scaling, verify_final_area
)
from services.pdf_service import (
    get_pdf_info, render_pdf_page_to_pixmap, crop_pdf_region_to_file
)
from services.image_service import rotate_image
from services.autocad_service import autocad_service
from ui.components.crop_canvas import InteractiveCropCanvas
from ui.components.status_badge import StatusBadge
from ui.components.step_tracker import StepTracker
from ui.components.guide_banner import GuideBanner

class DigitizationPage(QWidget):
    digitization_completed = Signal(int)
    back_to_queue = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.doc_id: Optional[int] = None
        self.doc_data: dict = {}
        self.batch_data: dict = {}
        self.polyline_handle: str = ""
        self._setup_ui()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 16, 20, 20)
        main_layout.setSpacing(12)

        # 1. Header Banner & Tombol Kembali
        header_card = QFrame()
        header_card.setStyleSheet("""
            QFrame {
                background-color: #FFFFFF;
                border-radius: 8px;
                border: 1px solid #E2E8F0;
                padding: 10px 14px;
            }
        """)
        h_layout = QHBoxLayout(header_card)
        h_layout.setContentsMargins(8, 4, 8, 4)
        h_layout.setSpacing(14)

        self.btn_back_queue = QPushButton("← Kembali ke Antrean")
        self.btn_back_queue.setProperty("class", "btn-secondary")
        self.btn_back_queue.setStyleSheet("font-weight: 700; padding: 6px 12px;")
        self.btn_back_queue.clicked.connect(lambda: self.back_to_queue.emit())
        h_layout.addWidget(self.btn_back_queue)

        v_info = QVBoxLayout()
        v_info.setSpacing(2)
        self.lbl_doc_title = QLabel("Belum Ada Dokumen yang Dipilih")
        self.lbl_doc_title.setStyleSheet("font-size: 15px; font-weight: 800; color: #0F172A;")
        v_info.addWidget(self.lbl_doc_title)

        self.lbl_batch_meta = QLabel("Pilih dokumen dari menu 'Antrean Dokumen' untuk memulai digitasi.")
        self.lbl_batch_meta.setStyleSheet("font-size: 12px; color: #64748B;")
        v_info.addWidget(self.lbl_batch_meta)
        h_layout.addLayout(v_info)

        h_layout.addStretch()

        self.status_badge = StatusBadge(STATUS_MENUNGGU)
        h_layout.addWidget(self.status_badge)

        main_layout.addWidget(header_card)

        # 2. Visual Step Tracker
        step_names = [
            "Potong Denah PDF",
            "Data Hak & Luas",
            "AutoCAD & Tracing",
            "Hitung Scaling",
            "Ganti Teks & Simpan"
        ]
        self.step_tracker = StepTracker(step_names)
        self.step_tracker.step_clicked.connect(self._go_to_step)
        main_layout.addWidget(self.step_tracker)

        # 3. Stacked Wizard Steps (5 Langkah Jelas)
        self.wizard_stack = QStackedWidget()

        self.step1_widget = self._create_step1_crop()
        self.step2_widget = self._create_step2_identity()
        self.step3_widget = self._create_step3_autocad()
        self.step4_widget = self._create_step4_scaling()
        self.step5_widget = self._create_step5_save()

        self.wizard_stack.addWidget(self.step1_widget) # 0
        self.wizard_stack.addWidget(self.step2_widget) # 1
        self.wizard_stack.addWidget(self.step3_widget) # 2
        self.wizard_stack.addWidget(self.step4_widget) # 3
        self.wizard_stack.addWidget(self.step5_widget) # 4

        main_layout.addWidget(self.wizard_stack, 1)

    # ==================== LANGKAH 1: POTONG DENAH PDF ====================
    def _create_step1_crop(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        # Petunjuk Langkah 1
        guide = GuideBanner("Petunjuk Langkah 1: Memotong Denah Bidang dari PDF", [
            "Pilih <b>Halaman Denah</b> pada panel sebelah kiri yang berisi gambar denah bidang tanah.",
            "Arahkan kursor mouse ke kanvas, lalu <b>tarik kursor (drag)</b> untuk membuat kotak seleksi mengelilingi denah bidang tanah.",
            "Gunakan tombol <b>'Konfirmasi Potongan'</b> untuk menyimpan potongan resolusi tinggi (300 DPI).",
            "Jika orientasi denah miring atau terbalik, gunakan tombol <b>'Putar 90°'</b>."
        ])
        layout.addWidget(guide)

        content = QHBoxLayout()
        content.setSpacing(14)

        # Panel Kontrol Kiri
        ctrl = QFrame()
        ctrl.setFixedWidth(280)
        ctrl.setStyleSheet("background-color: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 8px; padding: 14px;")
        c_layout = QVBoxLayout(ctrl)
        c_layout.setSpacing(12)

        lbl_p = QLabel("Halaman Dokumen PDF:")
        lbl_p.setProperty("class", "field-label")
        c_layout.addWidget(lbl_p)

        self.spin_page = QSpinBox()
        self.spin_page.setMinimum(1)
        self.spin_page.setMaximum(1)
        self.spin_page.valueChanged.connect(self._on_page_changed)
        c_layout.addWidget(self.spin_page)

        self.lbl_page_total = QLabel("Total halaman: -")
        self.lbl_page_total.setStyleSheet("color: #64748B; font-size: 11px;")
        c_layout.addWidget(self.lbl_page_total)

        c_layout.addSpacing(8)

        lbl_prev = QLabel("Hasil Potongan Denah:")
        lbl_prev.setProperty("class", "field-label")
        c_layout.addWidget(lbl_prev)

        self.lbl_crop_img = QLabel("Belum ada potongan")
        self.lbl_crop_img.setAlignment(Qt.AlignCenter)
        self.lbl_crop_img.setFixedHeight(160)
        self.lbl_crop_img.setStyleSheet("background-color: #F8FAFC; border: 1px dashed #CBD5E1; border-radius: 6px; color: #94A3B8;")
        c_layout.addWidget(self.lbl_crop_img)

        # Rotasi
        rot_row = QHBoxLayout()
        self.btn_rot_left = QPushButton("↺ Putar 90° Kiri")
        self.btn_rot_left.setProperty("class", "btn-secondary")
        self.btn_rot_left.clicked.connect(lambda: self._rotate_crop(-90))
        rot_row.addWidget(self.btn_rot_left)

        self.btn_rot_right = QPushButton("↻ Putar 90° Kanan")
        self.btn_rot_right.setProperty("class", "btn-secondary")
        self.btn_rot_right.clicked.connect(lambda: self._rotate_crop(90))
        rot_row.addWidget(self.btn_rot_right)
        c_layout.addLayout(rot_row)

        c_layout.addStretch()

        self.btn_step1_next = QPushButton("Lanjut ke Langkah 2: Data Hak →")
        self.btn_step1_next.setStyleSheet("""
            QPushButton {
                background-color: #2563EB;
                color: #FFFFFF;
                font-weight: 700;
                padding: 10px;
                border-radius: 6px;
            }
            QPushButton:hover { background-color: #1D4ED8; }
        """)
        self.btn_step1_next.clicked.connect(lambda: self._go_to_step(1))
        c_layout.addWidget(self.btn_step1_next)

        content.addWidget(ctrl)

        # Kanvas Potong di Kanan
        self.crop_canvas = InteractiveCropCanvas()
        self.crop_canvas.confirmed.connect(self._on_crop_confirmed)
        content.addWidget(self.crop_canvas, 1)

        layout.addLayout(content, 1)
        return widget

    # ==================== LANGKAH 2: DATA HAK & LUAS ====================
    def _create_step2_identity(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        guide = GuideBanner("Petunjuk Langkah 2: Mengisi Informasi Hak & Luas Dokumen", [
            "Pilih <b>Jenis Hak</b> pertanahan yang sesuai (Hak Milik, HGB, Hak Pakai, Wakaf).",
            "Masukkan <b>Nomor Hak</b>, <b>Nomor GS</b> (Gambar Situasi), dan <b>Tahun Dokumen</b>.",
            "Masukkan <b>Luas Dokumen (m²)</b> yang tertera pada buku tanah / gambar situasi. Luas ini wajib untuk rumus scaling otomatis.",
            "Periksa <b>Preview Identitas Dokumen Resmi</b>, lalu klik tombol biru <b>'Simpan Data & Lanjut ke AutoCAD'</b>."
        ])
        layout.addWidget(guide)

        card = QFrame()
        card.setStyleSheet("background-color: #FFFFFF; border-radius: 8px; border: 1px solid #E2E8F0; padding: 20px;")
        c_layout = QVBoxLayout(card)
        c_layout.setSpacing(14)

        # Form Grid
        grid = QHBoxLayout()
        grid.setSpacing(14)

        v1 = QVBoxLayout()
        v1.addWidget(QLabel("1. Jenis Hak Pertanahan *"))
        self.combo_jenis_hak = QComboBox()
        for k, v in JENIS_HAK_MAP.items():
            self.combo_jenis_hak.addItem(f"{v['label']}", k)
        self.combo_jenis_hak.currentIndexChanged.connect(self._update_identity_preview)
        v1.addWidget(self.combo_jenis_hak)
        grid.addLayout(v1)

        v2 = QVBoxLayout()
        v2.addWidget(QLabel("2. Nomor Hak *"))
        self.input_nomor_hak = QLineEdit()
        self.input_nomor_hak.setPlaceholderText("Misal: 1342")
        self.input_nomor_hak.textChanged.connect(self._update_identity_preview)
        v2.addWidget(self.input_nomor_hak)
        grid.addLayout(v2)

        v3 = QVBoxLayout()
        v3.addWidget(QLabel("3. Nomor GS (Gambar Situasi) *"))
        self.input_nomor_gs = QLineEdit()
        self.input_nomor_gs.setPlaceholderText("Misal: 1152 atau GS1152")
        self.input_nomor_gs.textChanged.connect(self._update_identity_preview)
        v3.addWidget(self.input_nomor_gs)
        grid.addLayout(v3)

        v4 = QVBoxLayout()
        v4.addWidget(QLabel("4. Tahun Dokumen *"))
        self.input_tahun = QLineEdit()
        self.input_tahun.setPlaceholderText("Misal: 1998")
        self.input_tahun.textChanged.connect(self._update_identity_preview)
        v4.addWidget(self.input_tahun)
        grid.addLayout(v4)

        v5 = QVBoxLayout()
        v5.addWidget(QLabel("5. Luas Dokumen (m²) *"))
        self.input_luas_dokumen = QDoubleSpinBox()
        self.input_luas_dokumen.setRange(0.01, 10000000.0)
        self.input_luas_dokumen.setDecimals(2)
        self.input_luas_dokumen.setValue(150.0)
        self.input_luas_dokumen.setSuffix(" m²")
        self.input_luas_dokumen.valueChanged.connect(self._update_identity_preview)
        v5.addWidget(self.input_luas_dokumen)
        grid.addLayout(v5)

        c_layout.addLayout(grid)

        # Preview Card
        prev_box = QFrame()
        prev_box.setStyleSheet("background-color: #F8FAFC; border: 1.5px solid #BFDBFE; border-radius: 8px; padding: 14px;")
        p_layout = QVBoxLayout(prev_box)
        p_layout.setSpacing(6)

        lbl_pt = QLabel("HASIL FORMAT IDENTITAS RESMI:")
        lbl_pt.setStyleSheet("font-size: 11px; font-weight: 700; color: #1E40AF; letter-spacing: 0.5px;")
        p_layout.addWidget(lbl_pt)

        self.lbl_identity_preview = QLabel("M. 1342 GS1152/1998")
        self.lbl_identity_preview.setStyleSheet("font-size: 24px; font-weight: 800; color: #1E3A8A;")
        p_layout.addWidget(self.lbl_identity_preview)

        self.lbl_filename_preview = QLabel("Nama File DWG Aman: M_1342_GS1152_1998.dwg")
        self.lbl_filename_preview.setStyleSheet("font-size: 12px; color: #64748B;")
        p_layout.addWidget(self.lbl_filename_preview)

        c_layout.addWidget(prev_box)

        # Navigasi Bawah
        nav_box = QHBoxLayout()
        self.btn_step2_prev = QPushButton("← Kembali ke Potong Denah")
        self.btn_step2_prev.setProperty("class", "btn-secondary")
        self.btn_step2_prev.clicked.connect(lambda: self._go_to_step(0))
        nav_box.addWidget(self.btn_step2_prev)

        nav_box.addStretch()

        self.btn_save_info = QPushButton("💾 Simpan Data & Lanjut ke AutoCAD (Langkah 3) →")
        self.btn_save_info.setStyleSheet("""
            QPushButton {
                background-color: #059669;
                color: #FFFFFF;
                font-size: 13px;
                font-weight: 700;
                padding: 10px 18px;
                border-radius: 6px;
            }
            QPushButton:hover { background-color: #047857; }
        """)
        self.btn_save_info.clicked.connect(self._save_step2_and_next)
        nav_box.addWidget(self.btn_save_info)

        c_layout.addLayout(nav_box)

        layout.addWidget(card)
        layout.addStretch()
        return widget

    # ==================== LANGKAH 3: AUTOCAD & TRACING ====================
    def _create_step3_autocad(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        guide = GuideBanner("Petunjuk Langkah 3: Integrasi AutoCAD & Tracing Polyline", [
            "Klik tombol <b>'🚀 1. Buka Template DWG'</b> untuk meluncurkan AutoCAD Desktop dan membuka lembar kerja template.",
            "Klik tombol <b>'🖼️ 2. Sisipkan Gambar Denah (Raster)'</b> untuk memasukkan denah hasil potongan ke AutoCAD ModelSpace.",
            "Buka jendela AutoCAD Anda, gunakan perintah <b>PL (Polyline)</b> untuk menjiplak batas bidang tanah, dan <b>TUTUP</b> polyline (opsi Close / C).",
            "Setelah selesai tracing di AutoCAD, klik tombol biru <b>'📐 3. Ambil Luas Polyline dari AutoCAD'</b> untuk membaca nilai luasnya."
        ])
        layout.addWidget(guide)

        card = QFrame()
        card.setStyleSheet("background-color: #FFFFFF; border-radius: 8px; border: 1px solid #E2E8F0; padding: 18px;")
        c_layout = QVBoxLayout(card)
        c_layout.setSpacing(14)

        # Kartu Aksi 1 & 2
        act_row = QHBoxLayout()
        act_row.setSpacing(12)

        # Sub-Card 1: Buka AutoCAD & Template
        c_a1 = QFrame()
        c_a1.setStyleSheet("background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; padding: 12px;")
        ca1_l = QVBoxLayout(c_a1)
        ca1_l.setSpacing(8)

        lbl_t1 = QLabel("Tahap 3A: Buka Lembar Kerja AutoCAD")
        lbl_t1.setStyleSheet("font-weight: 700; color: #1E293B;")
        ca1_l.addWidget(lbl_t1)

        self.btn_open_template = QPushButton("🚀 1. Buka Template DWG")
        self.btn_open_template.setStyleSheet("""
            QPushButton {
                background-color: #1E40AF;
                color: #FFFFFF;
                font-weight: 700;
                padding: 10px;
                border-radius: 6px;
            }
            QPushButton:hover { background-color: #1D4ED8; }
        """)
        self.btn_open_template.clicked.connect(self._open_autocad_template)
        ca1_l.addWidget(self.btn_open_template)

        self.lbl_status_tpl = QLabel("Status: Template belum dibuka")
        self.lbl_status_tpl.setStyleSheet("font-size: 11px; color: #64748B;")
        ca1_l.addWidget(self.lbl_status_tpl)

        act_row.addWidget(c_a1)

        # Sub-Card 2: Sisipkan Raster Denah
        c_a2 = QFrame()
        c_a2.setStyleSheet("background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; padding: 12px;")
        ca2_l = QVBoxLayout(c_a2)
        ca2_l.setSpacing(8)

        lbl_t2 = QLabel("Tahap 3B: Masukkan Denah ke ModelSpace")
        lbl_t2.setStyleSheet("font-weight: 700; color: #1E293B;")
        ca2_l.addWidget(lbl_t2)

        self.btn_insert_raster = QPushButton("🖼️ 2. Sisipkan Gambar Denah")
        self.btn_insert_raster.setStyleSheet("""
            QPushButton {
                background-color: #059669;
                color: #FFFFFF;
                font-weight: 700;
                padding: 10px;
                border-radius: 6px;
            }
            QPushButton:hover { background-color: #047857; }
        """)
        self.btn_insert_raster.clicked.connect(self._insert_raster_to_autocad)
        ca2_l.addWidget(self.btn_insert_raster)

        self.lbl_status_raster = QLabel("Status: Gambar denah belum disisipkan")
        self.lbl_status_raster.setStyleSheet("font-size: 11px; color: #64748B;")
        ca2_l.addWidget(self.lbl_status_raster)

        act_row.addWidget(c_a2)
        c_layout.addLayout(act_row)

        # Sub-Card 3: Tracing & Ambil Luas
        c_a3 = QFrame()
        c_a3.setStyleSheet("background-color: #EFF6FF; border: 1.5px solid #93C5FD; border-radius: 8px; padding: 14px;")
        ca3_l = QVBoxLayout(c_a3)
        ca3_l.setSpacing(10)

        lbl_t3 = QLabel("Tahap 3C: Ambil Luas Hasil Tracing Polyline")
        lbl_t3.setStyleSheet("font-weight: 800; color: #1E3A8A; font-size: 13px;")
        ca3_l.addWidget(lbl_t3)

        lbl_petunjuk_pl = QLabel(
            "Operator melakukan tracing dengan perintah <b>PL</b> di AutoCAD, pastikan polyline ditutup (Closed). "
            "Kemudian klik tombol di bawah dan klik polyline tersebut di layar AutoCAD."
        )
        lbl_petunjuk_pl.setWordWrap(True)
        lbl_petunjuk_pl.setStyleSheet("color: #1E40AF; font-size: 12px;")
        ca3_l.addWidget(lbl_petunjuk_pl)

        btn_row_pl = QHBoxLayout()
        self.btn_get_area = QPushButton("📐 3. Ambil Luas Polyline dari AutoCAD")
        self.btn_get_area.setStyleSheet("""
            QPushButton {
                background-color: #2563EB;
                color: #FFFFFF;
                font-weight: 700;
                font-size: 13px;
                padding: 10px 18px;
                border-radius: 6px;
            }
            QPushButton:hover { background-color: #1D4ED8; }
        """)
        self.btn_get_area.clicked.connect(self._get_polyline_area)
        btn_row_pl.addWidget(self.btn_get_area)

        self.lbl_area_feedback = QLabel("Belum ada polyline yang dibaca.")
        self.lbl_area_feedback.setStyleSheet("font-weight: 700; color: #334155; font-size: 13px;")
        btn_row_pl.addWidget(self.lbl_area_feedback)
        btn_row_pl.addStretch()
        ca3_l.addLayout(btn_row_pl)

        c_layout.addWidget(c_a3)

        # Navigasi Bawah
        nav_box = QHBoxLayout()
        btn_step3_prev = QPushButton("← Kembali ke Data Hak")
        btn_step3_prev.setProperty("class", "btn-secondary")
        btn_step3_prev.clicked.connect(lambda: self._go_to_step(1))
        nav_box.addWidget(btn_step3_prev)

        nav_box.addStretch()

        self.btn_step3_next = QPushButton("Lanjut ke Hitung Scaling (Langkah 4) →")
        self.btn_step3_next.setStyleSheet("""
            QPushButton {
                background-color: #2563EB;
                color: #FFFFFF;
                font-weight: 700;
                padding: 10px 18px;
                border-radius: 6px;
            }
            QPushButton:hover { background-color: #1D4ED8; }
        """)
        self.btn_step3_next.clicked.connect(lambda: self._go_to_step(3))
        nav_box.addWidget(self.btn_step3_next)

        c_layout.addLayout(nav_box)
        layout.addWidget(card)
        layout.addStretch()
        return widget

    # ==================== LANGKAH 4: HITUNG & SCALING ====================
    def _create_step4_scaling(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        guide = GuideBanner("Petunjuk Langkah 4: Perhitungan & Penerapan Scaling Seragam", [
            "Periksa rincian perbandingan antara <b>Luas Dokumen</b> dan <b>Luas Hasil Tracing</b> pada kartu analisis di bawah.",
            "Faktor scaling dihitung secara otomatis menggunakan rumus: <code>Faktor = √(Luas Dokumen / Luas Tracing)</code>.",
            "Klik tombol kuning <b>'⚡ Terapkan Scaling di AutoCAD'</b>. Buka jendela AutoCAD, pilih objek (Raster + Polyline), lalu klik titik dasar (*base point*).",
            "Aplikasi akan secara otomatis membaca kembali luas polyline setelah diskalakan untuk memverifikasi kesesuaian toleransi."
        ])
        layout.addWidget(guide)

        card = QFrame()
        card.setStyleSheet("background-color: #FFFFFF; border-radius: 8px; border: 1px solid #E2E8F0; padding: 18px;")
        c_layout = QVBoxLayout(card)
        c_layout.setSpacing(14)

        # Kartu Analisis Scaling
        self.analysis_box = QFrame()
        self.analysis_box.setStyleSheet("background-color: #F8FAFC; border: 1.5px solid #CBD5E1; border-radius: 8px; padding: 14px;")
        a_grid = QHBoxLayout(self.analysis_box)
        a_grid.setSpacing(14)

        self.card_luas_doc = QLabel("Luas Target Dokumen:\n<b>0.00 m²</b>")
        self.card_luas_doc.setStyleSheet("font-size: 13px; color: #1E40AF;")
        a_grid.addWidget(self.card_luas_doc)

        self.card_luas_trace = QLabel("Luas Hasil Tracing:\n<b>0.00 m²</b>")
        self.card_luas_trace.setStyleSheet("font-size: 13px; color: #0D9488;")
        a_grid.addWidget(self.card_luas_trace)

        self.card_selisih_awal = QLabel("Selisih Luas Awal:\n<b>0.00 m²</b>")
        self.card_selisih_awal.setStyleSheet("font-size: 13px; color: #DC2626;")
        a_grid.addWidget(self.card_selisih_awal)

        self.card_faktor_scaling = QLabel("Faktor Scaling Otomatis:\n<b style='font-size:16px;'>1.000000</b>")
        self.card_faktor_scaling.setStyleSheet("color: #B45309;")
        a_grid.addWidget(self.card_faktor_scaling)

        c_layout.addWidget(self.analysis_box)

        # Tombol Terapkan Scaling
        scale_action_box = QFrame()
        scale_action_box.setStyleSheet("background-color: #FEF3C7; border: 1px solid #FDE68A; border-radius: 8px; padding: 14px;")
        sab_l = QVBoxLayout(scale_action_box)
        sab_l.setSpacing(10)

        lbl_act_title = QLabel("Aksi Eksekusi Scaling di AutoCAD:")
        lbl_act_title.setStyleSheet("font-weight: 800; color: #92400E;")
        sab_l.addWidget(lbl_act_title)

        row_scale = QHBoxLayout()
        self.btn_apply_scaling = QPushButton("⚡ Terapkan Scaling di AutoCAD Sekarang")
        self.btn_apply_scaling.setStyleSheet("""
            QPushButton {
                background-color: #D97706;
                color: #FFFFFF;
                font-weight: 800;
                font-size: 13px;
                padding: 10px 18px;
                border-radius: 6px;
            }
            QPushButton:hover { background-color: #B45309; }
            QPushButton:disabled { background-color: #FCD34D; color: #78350F; }
        """)
        self.btn_apply_scaling.setEnabled(False)
        self.btn_apply_scaling.clicked.connect(self._apply_scaling)
        row_scale.addWidget(self.btn_apply_scaling)

        self.lbl_scale_result = QLabel("Scaling belum diterapkan.")
        self.lbl_scale_result.setStyleSheet("color: #78350F; font-size: 12px; font-weight: 700;")
        row_scale.addWidget(self.lbl_scale_result)
        row_scale.addStretch()
        sab_l.addLayout(row_scale)

        c_layout.addWidget(scale_action_box)

        # Navigasi Bawah
        nav_box = QHBoxLayout()
        btn_step4_prev = QPushButton("← Kembali ke AutoCAD Tracing")
        btn_step4_prev.setProperty("class", "btn-secondary")
        btn_step4_prev.clicked.connect(lambda: self._go_to_step(2))
        nav_box.addWidget(btn_step4_prev)

        nav_box.addStretch()

        self.btn_step4_next = QPushButton("Lanjut ke Langkah Terakhir: Simpan DWG →")
        self.btn_step4_next.setStyleSheet("""
            QPushButton {
                background-color: #2563EB;
                color: #FFFFFF;
                font-weight: 700;
                padding: 10px 18px;
                border-radius: 6px;
            }
            QPushButton:hover { background-color: #1D4ED8; }
        """)
        self.btn_step4_next.clicked.connect(lambda: self._go_to_step(4))
        nav_box.addWidget(self.btn_step4_next)

        c_layout.addLayout(nav_box)
        layout.addWidget(card)
        layout.addStretch()
        return widget

    # ==================== LANGKAH 5: GANTI TEKS & SIMPAN DWG ====================
    def _create_step5_save(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        guide = GuideBanner("Petunjuk Langkah 5: Mengganti Teks Identitas & Menyimpan Gambar DWG", [
            "Klik tombol <b>'✏️ Ganti Teks Identitas di AutoCAD'</b>, lalu klik objek teks identitas pada etiket/kop gambar di AutoCAD.",
            "Isi teks di AutoCAD akan secara otomatis berganti sesuai nomor resmi dokumen (contoh: <code>M. 1342 GS1152/1998</code>).",
            "Klik tombol hijau besar <b>'💾 Simpan Hasil Digitasi (DWG) & Selesai'</b> untuk menyimpan file DWG resmi.",
            "File akan tersimpan ke folder batch desa, dan status dokumen akan berubah menjadi <b>SELESAI</b>."
        ])
        layout.addWidget(guide)

        card = QFrame()
        card.setStyleSheet("background-color: #FFFFFF; border-radius: 8px; border: 1px solid #E2E8F0; padding: 20px;")
        c_layout = QVBoxLayout(card)
        c_layout.setSpacing(16)

        # 1. Ganti Teks Identitas
        box_text = QFrame()
        box_text.setStyleSheet("background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; padding: 14px;")
        bt_l = QVBoxLayout(box_text)
        bt_l.setSpacing(8)

        lbl_gt = QLabel("Tahap 5A: Ganti Identitas Teks di AutoCAD (TEXT / MTEXT)")
        lbl_gt.setStyleSheet("font-weight: 800; color: #1E293B;")
        bt_l.addWidget(lbl_gt)

        self.lbl_text_target = QLabel("Identitas yang akan ditulis: <b>M. 1342 GS1152/1998</b>")
        self.lbl_text_target.setStyleSheet("font-size: 13px; color: #1E40AF;")
        bt_l.addWidget(self.lbl_text_target)

        row_t = QHBoxLayout()
        self.btn_replace_text = QPushButton("✏️ Ganti Teks Identitas di AutoCAD")
        self.btn_replace_text.setStyleSheet("""
            QPushButton {
                background-color: #1E40AF;
                color: #FFFFFF;
                font-weight: 700;
                padding: 9px 16px;
                border-radius: 6px;
            }
            QPushButton:hover { background-color: #1D4ED8; }
        """)
        self.btn_replace_text.clicked.connect(self._replace_identity_text)
        row_t.addWidget(self.btn_replace_text)

        self.lbl_text_status = QLabel("Klik tombol lalu klik objek teks di AutoCAD.")
        self.lbl_text_status.setStyleSheet("color: #64748B; font-size: 12px;")
        row_t.addWidget(self.lbl_text_status)
        row_t.addStretch()
        bt_l.addLayout(row_t)

        c_layout.addWidget(box_text)

        # 2. Simpan DWG
        box_save = QFrame()
        box_save.setStyleSheet("background-color: #ECFDF5; border: 1.5px solid #A7F3D0; border-radius: 8px; padding: 16px;")
        bs_l = QVBoxLayout(box_save)
        bs_l.setSpacing(10)

        lbl_sd = QLabel("Tahap 5B: Simpan File DWG Hasil Digitasi Resmi")
        lbl_sd.setStyleSheet("font-weight: 800; color: #065F46; font-size: 14px;")
        bs_l.addWidget(lbl_sd)

        self.lbl_save_dest = QLabel("Lokasi Target Penyimpanan: hasil_digitasi/...")
        self.lbl_save_dest.setStyleSheet("color: #047857; font-size: 12px;")
        bs_l.addWidget(self.lbl_save_dest)

        row_s = QHBoxLayout()
        self.btn_save_dwg = QPushButton("💾 Simpan Hasil Digitasi (DWG) & Tandai SELESAI")
        self.btn_save_dwg.setStyleSheet("""
            QPushButton {
                background-color: #059669;
                color: #FFFFFF;
                font-size: 14px;
                font-weight: 800;
                padding: 12px 24px;
                border-radius: 8px;
            }
            QPushButton:hover { background-color: #047857; }
        """)
        self.btn_save_dwg.clicked.connect(self._save_digitization_result)
        row_s.addWidget(self.btn_save_dwg)
        row_s.addStretch()
        bs_l.addLayout(row_s)

        c_layout.addWidget(box_save)

        # Navigasi Bawah
        nav_box = QHBoxLayout()
        btn_step5_prev = QPushButton("← Kembali ke Hitung Scaling")
        btn_step5_prev.setProperty("class", "btn-secondary")
        btn_step5_prev.clicked.connect(lambda: self._go_to_step(3))
        nav_box.addWidget(btn_step5_prev)

        nav_box.addStretch()
        c_layout.addLayout(nav_box)

        layout.addWidget(card)
        layout.addStretch()
        return widget

    # ==================== STEP NAVIGATION ====================
    def _go_to_step(self, step_idx: int):
        self.wizard_stack.setCurrentIndex(step_idx)
        self.step_tracker.set_current_step(step_idx)

    # ==================== DATA LOADING ====================
    def load_document(self, doc_id: int):
        self.doc_id = doc_id
        self.doc_data = get_document(doc_id)
        if not self.doc_data:
            return

        self.batch_data = get_batch(self.doc_data["batch_id"]) or {}

        # Update Banner
        self.lbl_doc_title.setText(f"Dokumen: {self.doc_data['nama_pdf']}")
        desa = self.batch_data.get("nama_desa", "-")
        kec = self.batch_data.get("kecamatan", "-")
        self.lbl_batch_meta.setText(f"Batch: Desa {desa}, Kec. {kec} | ID Dokumen: {doc_id}")
        self.status_badge.set_status(self.doc_data.get("status", STATUS_MENUNGGU))

        # Reset Step Tracker
        self.step_tracker.completed_steps.clear()

        # Muat Form Identitas
        if self.doc_data.get("kode_hak"):
            idx = self.combo_jenis_hak.findData(self.doc_data["kode_hak"])
            if idx >= 0:
                self.combo_jenis_hak.setCurrentIndex(idx)
        if self.doc_data.get("nomor_hak"):
            self.input_nomor_hak.setText(str(self.doc_data["nomor_hak"]))
        if self.doc_data.get("nomor_gs"):
            self.input_nomor_gs.setText(str(self.doc_data["nomor_gs"]))
        if self.doc_data.get("tahun"):
            self.input_tahun.setText(str(self.doc_data["tahun"]))
        if self.doc_data.get("luas_dokumen"):
            self.input_luas_dokumen.setValue(float(self.doc_data["luas_dokumen"]))

        # Muat PDF ke Langkah 1
        pdf_path = self.doc_data.get("path_pdf", "")
        if pdf_path and os.path.exists(pdf_path):
            info = get_pdf_info(pdf_path)
            if info["success"]:
                count = info["page_count"]
                self.spin_page.setMaximum(count)
                self.lbl_page_total.setText(f"Total halaman: {count}")
                cur_page = self.doc_data.get("halaman_pdf", 1)
                self.spin_page.setValue(cur_page)
                self._load_pdf_page(cur_page)

        # Muat Crop jika sudah ada
        crop_path = self.doc_data.get("path_crop", "")
        if crop_path and os.path.exists(crop_path):
            pix = QPixmap(crop_path)
            scaled = pix.scaled(self.lbl_crop_img.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.lbl_crop_img.setPixmap(scaled)
            self.step_tracker.mark_completed(0)

        # Muat info scaling jika sudah ada
        if self.doc_data.get("luas_awal"):
            self.card_luas_trace.setText(f"Luas Hasil Tracing:\n<b>{self.doc_data['luas_awal']:.2f} m²</b>")
            self._update_scaling_cards(self.doc_data["luas_dokumen"] or 0.0, self.doc_data["luas_awal"])
            self.btn_apply_scaling.setEnabled(True)
            self.step_tracker.mark_completed(2)

        if self.doc_data.get("luas_akhir"):
            self.step_tracker.mark_completed(3)

        if self.doc_data.get("status") == STATUS_SELESAI:
            self.step_tracker.mark_completed(4)

        self._update_identity_preview()
        self._go_to_step(0)

    def _load_pdf_page(self, page_number: int):
        pdf_path = self.doc_data.get("path_pdf", "")
        if not pdf_path or not os.path.exists(pdf_path):
            return
        img_bytes = render_pdf_page_to_pixmap(pdf_path, page_number, dpi=150)
        if img_bytes:
            self.crop_canvas.load_page_image(img_bytes)

    def _on_page_changed(self, page_num: int):
        if self.doc_id:
            update_document(self.doc_id, halaman_pdf=page_num)
        self._load_pdf_page(page_num)

    def _on_crop_confirmed(self, norm_box: tuple):
        if not self.doc_id or not self.doc_data.get("path_pdf"):
            return
        pdf_path = self.doc_data["path_pdf"]
        page_num = self.spin_page.value()
        crop_name = f"crop_doc_{self.doc_id}_{datetime.now().strftime('%H%M%S')}.png"

        ok, result_path = crop_pdf_region_to_file(pdf_path, page_num, norm_box, crop_name, dpi=300)
        if ok:
            update_document(self.doc_id, path_crop=result_path, status=STATUS_PDF_DIPROSES)
            self.doc_data["path_crop"] = result_path
            self.status_badge.set_status(STATUS_PDF_DIPROSES)
            self.step_tracker.mark_completed(0)

            pix = QPixmap(result_path)
            scaled = pix.scaled(self.lbl_crop_img.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.lbl_crop_img.setPixmap(scaled)

            QMessageBox.information(
                self, "Potongan Denah Tersimpan",
                "✓ Denah bidang tanah berhasil dipotong dengan resolusi tinggi (300 DPI)!\n\n"
                "Aplikasi akan otomatis melanjutkan ke Langkah 2 (Data Hak & Luas)."
            )
            self._go_to_step(1)
        else:
            QMessageBox.critical(self, "Gagal Crop", f"Gagal memotong denah PDF: {result_path}")

    def _rotate_crop(self, degrees: int):
        crop_path = self.doc_data.get("path_crop")
        if not crop_path or not os.path.exists(crop_path):
            QMessageBox.warning(self, "Peringatan", "Belum ada potongan denah yang tersimpan.")
            return
        ok, res = rotate_image(crop_path, degrees)
        if ok:
            pix = QPixmap(crop_path)
            scaled = pix.scaled(self.lbl_crop_img.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.lbl_crop_img.setPixmap(scaled)

    # ==================== STEP 2 LOGIC ====================
    def _update_identity_preview(self):
        kode_hak = self.combo_jenis_hak.currentData() or "1"
        no_hak = self.input_nomor_hak.text() or "1342"
        no_gs = self.input_nomor_gs.text() or "1152"
        tahun = self.input_tahun.text() or "1998"

        identity = format_document_identity(kode_hak, no_hak, no_gs, tahun)
        safe_dwg = sanitize_filename(identity, ".dwg")

        self.lbl_identity_preview.setText(identity)
        self.lbl_filename_preview.setText(f"Nama File DWG Aman: {safe_dwg}")
        self.lbl_text_target.setText(f"Identitas yang akan ditulis: <b>{identity}</b>")

        safe_desa = self.batch_data.get("nama_desa", "Desa").replace(" ", "_")
        dest = HASIL_DIGITASI_DIR / f"Batch_{self.doc_data.get('batch_id', 1)}_{safe_desa}" / safe_dwg
        self.lbl_save_dest.setText(f"Lokasi Target: <b>{dest}</b>")

    def _save_step2_and_next(self):
        if not self.doc_id:
            return

        kode_hak = self.combo_jenis_hak.currentData()
        jenis_hak_label = self.combo_jenis_hak.currentText()
        no_hak = self.input_nomor_hak.text().strip()
        no_gs = self.input_nomor_gs.text().strip()
        tahun = self.input_tahun.text().strip()
        luas = self.input_luas_dokumen.value()

        is_valid, err = validate_document_input(kode_hak, no_hak, no_gs, tahun, luas)
        if not is_valid:
            QMessageBox.warning(self, "Validasi Input", err)
            return

        identitas = format_document_identity(kode_hak, no_hak, no_gs, tahun)

        update_document(
            self.doc_id,
            kode_hak=kode_hak,
            jenis_hak=jenis_hak_label,
            nomor_hak=no_hak,
            nomor_gs=normalize_gs_number(no_gs),
            tahun=tahun,
            identitas_dokumen=identitas,
            luas_dokumen=luas,
            status=STATUS_MENUNGGU_TRACING
        )

        self.doc_data.update({
            "kode_hak": kode_hak,
            "jenis_hak": jenis_hak_label,
            "nomor_hak": no_hak,
            "nomor_gs": normalize_gs_number(no_gs),
            "tahun": tahun,
            "identitas_dokumen": identitas,
            "luas_dokumen": luas,
            "status": STATUS_MENUNGGU_TRACING
        })

        self.status_badge.set_status(STATUS_MENUNGGU_TRACING)
        self.step_tracker.mark_completed(1)
        self.card_luas_doc.setText(f"Luas Target Dokumen:\n<b>{luas:.2f} m²</b>")

        QMessageBox.information(
            self, "Data Tersimpan",
            f"✓ Informasi dokumen '{identitas}' berhasil disimpan!\n\n"
            "Melanjutkan ke Langkah 3: Integrasi AutoCAD & Tracing."
        )
        self._go_to_step(2)

    # ==================== STEP 3 LOGIC: AUTOCAD ====================
    def _open_autocad_template(self):
        custom_tpl = get_setting("template_dwg_path", str(DEFAULT_TEMPLATE_PATH))
        tpl_path = custom_tpl if os.path.exists(custom_tpl) else str(DEFAULT_TEMPLATE_PATH)

        if not os.path.exists(tpl_path):
            try:
                os.makedirs(os.path.dirname(tpl_path), exist_ok=True)
                with open(tpl_path, "wb") as f:
                    f.write(b"")
            except Exception:
                pass

        ok, msg = autocad_service.open_template(tpl_path)
        if ok:
            self.lbl_status_tpl.setText("✓ Template berhasil dibuka di AutoCAD")
            self.lbl_status_tpl.setStyleSheet("font-size: 11px; color: #059669; font-weight: 700;")
            QMessageBox.information(self, "AutoCAD Template", msg)
        else:
            self.lbl_status_tpl.setText(f"✗ Gagal buka template: {msg}")
            self.lbl_status_tpl.setStyleSheet("font-size: 11px; color: #DC2626;")
            QMessageBox.critical(self, "Gagal Buka Template", msg)

    def _insert_raster_to_autocad(self):
        crop_path = self.doc_data.get("path_crop")
        if not crop_path or not os.path.exists(crop_path):
            QMessageBox.warning(self, "Denah Belum Ada", "Potong denah bidang tanah pada Langkah 1 terlebih dahulu.")
            return

        ok, msg = autocad_service.insert_raster_image(crop_path, insert_pt=(0.0, 0.0, 0.0), scale=1.0)
        if ok:
            self.lbl_status_raster.setText("✓ Gambar denah berhasil disisipkan ke ModelSpace")
            self.lbl_status_raster.setStyleSheet("font-size: 11px; color: #059669; font-weight: 700;")
            QMessageBox.information(
                self, "Denah Masuk ke AutoCAD",
                f"{msg}\n\n"
                "Silakan buka jendela AutoCAD, gunakan perintah 'PL' (Polyline) untuk menjiplak batas bidang tanah, "
                "dan pastikan polyline ditutup (Close / C)."
            )
        else:
            self.lbl_status_raster.setText(f"✗ Gagal sisipkan denah: {msg}")
            self.lbl_status_raster.setStyleSheet("font-size: 11px; color: #DC2626;")
            QMessageBox.critical(self, "Gagal Sisipkan Gambar", msg)

    def _get_polyline_area(self):
        luas_doc = self.doc_data.get("luas_dokumen") or self.input_luas_dokumen.value()
        if luas_doc <= 0:
            QMessageBox.warning(self, "Luas Dokumen Kosong", "Isi luas dokumen pertanahan pada Langkah 2 terlebih dahulu.")
            return

        ok, area_m2, handle, msg = autocad_service.get_polyline_area()
        if not ok:
            QMessageBox.critical(self, "Gagal Membaca Polyline", msg)
            return

        self.polyline_handle = handle
        self.doc_data["luas_awal"] = area_m2
        update_document(self.doc_id, luas_awal=area_m2, status=STATUS_MENUNGGU_SCALING)
        self.status_badge.set_status(STATUS_MENUNGGU_SCALING)
        self.step_tracker.mark_completed(2)

        self.lbl_area_feedback.setText(f"✓ Luas Polyline Terbaca: {area_m2:.2f} m² (Valid & Closed)")
        self.lbl_area_feedback.setStyleSheet("font-weight: 700; color: #059669; font-size: 13px;")

        self.card_luas_trace.setText(f"Luas Hasil Tracing:\n<b>{area_m2:.2f} m²</b>")
        self._update_scaling_cards(luas_doc, area_m2)
        self.btn_apply_scaling.setEnabled(True)

        QMessageBox.information(
            self, "Luas Polyline Berhasil Diambil",
            f"{msg}\n\nFaktor scaling otomatis telah dihitung. Klik 'Lanjut ke Hitung Scaling' untuk menerapkan skala."
        )
        self._go_to_step(3)

    def _update_scaling_cards(self, luas_doc: float, luas_trace: float):
        analysis = analyze_scaling(luas_doc, luas_trace)
        if analysis["success"]:
            self.card_luas_doc.setText(f"Luas Target Dokumen:\n<b>{analysis['luas_dokumen']:.2f} m²</b>")
            self.card_selisih_awal.setText(f"Selisih Luas Awal:\n<b>{analysis['selisih_awal']:.2f} m²</b>")
            self.card_faktor_scaling.setText(f"Faktor Scaling Otomatis:\n<b style='font-size:16px;'>{analysis['faktor_scaling']:.6f}</b>")
            self.doc_data["faktor_scaling"] = analysis["faktor_scaling_raw"]
            update_document(self.doc_id, faktor_scaling=analysis["faktor_scaling_raw"])

    # ==================== STEP 4 LOGIC ====================
    def _apply_scaling(self):
        scale_fac = self.doc_data.get("faktor_scaling", 0.0)
        luas_doc = self.doc_data.get("luas_dokumen", 0.0)
        if scale_fac <= 0:
            QMessageBox.warning(self, "Faktor Scaling Tidak Valid", "Faktor scaling belum dihitung.")
            return

        reply = QMessageBox.question(
            self, "Konfirmasi Scaling Seragam",
            f"Faktor scaling yang akan diterapkan: {scale_fac:.6f}\n\n"
            "Di jendela AutoCAD:\n"
            "1. Anda akan diminta memilih objek yang ikut diskalakan (Raster, Polyline, dll).\n"
            "2. Anda akan diminta mengklik titik dasar (base point) scaling.\n\n"
            "Lanjutkan proses scaling?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes
        )
        if reply != QMessageBox.Yes:
            return

        ok, final_area, msg = autocad_service.scale_selected_objects(
            scale_fac, polyline_handle=self.polyline_handle
        )
        if not ok:
            QMessageBox.critical(self, "Scaling Gagal", msg)
            return

        eval_res = verify_final_area(luas_doc, final_area)
        self.doc_data["luas_akhir"] = final_area
        update_document(self.doc_id, luas_akhir=final_area, status=STATUS_MENUNGGU_VERIFIKASI)
        self.status_badge.set_status(STATUS_MENUNGGU_VERIFIKASI)
        self.step_tracker.mark_completed(3)

        self.lbl_scale_result.setText(
            f"✓ Luas Akhir: {final_area:.2f} m² (Selisih: {eval_res['selisih']:.2f} m² | {eval_res['status_evaluasi']})"
        )
        self.lbl_scale_result.setStyleSheet("color: #059669; font-size: 12px; font-weight: 700;")

        QMessageBox.information(
            self, "Scaling Selesai & Terverifikasi",
            f"{msg}\n\n"
            f"Hasil Verifikasi Luas Akhir:\n"
            f"• Luas Dokumen Target: {luas_doc:.2f} m²\n"
            f"• Luas Akhir Polyline: {final_area:.2f} m²\n"
            f"• Selisih: {eval_res['selisih']:.4f} m² ({eval_res['persen_error']}%)\n"
            f"• Evaluasi Akurasi: {eval_res['status_evaluasi']}\n\n"
            "Silakan lanjut ke Langkah 5 (Ganti Teks & Simpan DWG)."
        )
        self._go_to_step(4)

    # ==================== STEP 5 LOGIC ====================
    def _replace_identity_text(self):
        identitas = self.doc_data.get("identitas_dokumen") or self.lbl_identity_preview.text()
        ok, msg = autocad_service.replace_identity_text(identitas)
        if ok:
            self.lbl_text_status.setText(f"✓ {msg}")
            self.lbl_text_status.setStyleSheet("color: #059669; font-weight: 700;")
            QMessageBox.information(self, "Teks Diperbarui", msg)
        else:
            self.lbl_text_status.setText(f"✗ {msg}")
            self.lbl_text_status.setStyleSheet("color: #DC2626;")
            QMessageBox.critical(self, "Gagal Ganti Teks", msg)

    def _save_digitization_result(self):
        if not self.doc_id:
            return

        identitas = self.doc_data.get("identitas_dokumen")
        if not identitas:
            QMessageBox.warning(self, "Data Belum Lengkap", "Simpan identitas dokumen terlebih dahulu pada Langkah 2.")
            return

        safe_dwg_name = sanitize_filename(identitas, ".dwg")
        safe_desa = self.batch_data.get("nama_desa", "Desa").replace(" ", "_")
        batch_folder = HASIL_DIGITASI_DIR / f"Batch_{self.doc_data.get('batch_id', 1)}_{safe_desa}"
        batch_folder.mkdir(parents=True, exist_ok=True)
        dest_dwg_path = str(batch_folder / safe_dwg_name)

        overwrite = False
        if os.path.exists(dest_dwg_path):
            reply = QMessageBox.question(
                self, "Konfirmasi Timpa File",
                f"File '{safe_dwg_name}' sudah ada di folder hasil.\nApakah Anda ingin menimpa file ini?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return
            overwrite = True

        ok, msg = autocad_service.save_drawing_as(dest_dwg_path, overwrite=overwrite)
        if not ok:
            QMessageBox.critical(self, "Gagal Simpan DWG", msg)
            return

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        update_document(
            self.doc_id,
            path_dwg=dest_dwg_path,
            status=STATUS_SELESAI,
            completed_at=now_str
        )
        self.doc_data["status"] = STATUS_SELESAI
        self.doc_data["path_dwg"] = dest_dwg_path
        self.status_badge.set_status(STATUS_SELESAI)
        self.step_tracker.mark_completed(4)

        add_log(
            aktivitas="Digitasi Selesai",
            detail=f"Dokumen {identitas} berhasil didigitasi & disimpan ke {safe_dwg_name}",
            batch_id=self.doc_data.get("batch_id"),
            document_id=self.doc_id
        )

        reply = QMessageBox.information(
            self, "Digitasi Berhasil Disimpan",
            f"🎉 Selamat! Dokumen pertanahan berhasil didigitasi secara lengkap.\n\n"
            f"• Identitas Dokumen: {identitas}\n"
            f"• Status: SELESAI\n"
            f"• File DWG: {safe_dwg_name}\n"
            f"• Lokasi:\n{dest_dwg_path}\n\n"
            "Klik OK untuk kembali ke daftar Antrean Dokumen.",
            QMessageBox.Ok
        )

        self.digitization_completed.emit(self.doc_id)
        self.back_to_queue.emit()
