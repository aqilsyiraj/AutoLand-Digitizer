"""
AutoLand Digitizer - Halaman Digitasi Otomatis

Alur baru yang disederhanakan:
1. Pilih halaman denah -> sistem mendeteksi polyline otomatis (offline CV).
2. Periksa/koreksi titik polyline + isi data dokumen.
3. Satu tombol: buat DWG, skala, teks identitas, dan koordinat.
4. Ringkasan hasil.

Operator tidak perlu lagi menggambar PL manual di AutoCAD.
"""

from __future__ import annotations

import json
import math
import os
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QApplication, QComboBox, QDoubleSpinBox, QFrame, QGridLayout,
    QHBoxLayout, QLabel, QLineEdit, QMessageBox, QProgressBar, QPushButton,
    QStackedWidget, QTextEdit, QVBoxLayout, QWidget,
)

from config import (
    COORDINATE_DIR_NAME,
    DEFAULT_TEMPLATE_PATH,
    DETECTION_CROP_DPI,
    DETECTION_DPI,
    DETECTION_PREVIEW_DPI,
    DETECTION_SCAN_DPI,
    HASIL_DIGITASI_DIR,
    JENIS_HAK_MAP,
    STATUS_MENUNGGU_TRACING,
    STATUS_SELESAI,
    STATUS_TERDETEKSI,
    TEMPORARY_DIR,
)
from database.db import (
    add_log, get_batch, get_document, get_setting, save_detection_result,
    update_document,
)
from services.autocad_service import autocad_service
from services.detection_service import (
    detect_on_page,
    detect_polylines_from_array,
    guess_document_hints,
    polygon_area,
    render_page_array,
    suggest_denah_page,
    write_coordinate_files,
)
from services.geometry_service import analyze_scaling, verify_final_area
from services.naming_service import (
    format_document_identity, get_awalan_hak, normalize_gs_number,
    sanitize_filename, validate_document_input,
)
from services.pdf_service import crop_pdf_region_to_file, get_pdf_info
from ui.components.button import Button
from ui.components.crop_canvas import InteractiveCropCanvas
from ui.components.guide_banner import GuideBanner
from ui.components.form_field import FormField
from ui.components.status_badge import StatusBadge
from ui.components.step_tracker import StepTracker
from ui.motion.qt_motion import fade_in


class DigitizationPage(QWidget):
    digitization_completed = Signal(int)
    back_to_queue = Signal()

    STEP_NAMES = [
        "Pilih Halaman Denah",
        "Periksa & Isi Data",
        "Proses Otomatis",
        "Selesai",
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.doc_id: Optional[int] = None
        self.doc_data: dict = {}
        self.batch_data: dict = {}

        self.candidates: list = []
        self.selected_index = 0
        self.polyline_normalized: list = []
        self.detection_meta: dict = {}
        self.crop_box: tuple = ()
        self.crop_confirmed_by_user = False
        self.crop_path: str = ""
        self.processing = False
        self._detect_cache: dict = {}

        self._setup_ui()

    # =================================================================
    # UI
    # =================================================================
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(14)

        header = QWidget()
        h = QHBoxLayout(header)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(14)

        self.btn_back = Button(
            "← Antrean",
            size="md",
            tone="secondary",
            tooltip="Kembali ke daftar dokumen tanpa memproses lebih lanjut",
        )
        self.btn_back.clicked.connect(self.back_to_queue.emit)
        h.addWidget(self.btn_back, 0, Qt.AlignTop)

        info = QVBoxLayout()
        info.setSpacing(2)
        eyebrow = QLabel("WIZARD DIGITASI")
        eyebrow.setObjectName("PageEyebrow")
        info.addWidget(eyebrow)
        self.lbl_title = QLabel("Belum ada dokumen yang dipilih")
        self.lbl_title.setObjectName("DigitTitle")
        self.lbl_title.setWordWrap(True)
        info.addWidget(self.lbl_title)
        self.lbl_meta = QLabel("Buka dokumen dari menu '3. PDF & Antrean' untuk memulai.")
        self.lbl_meta.setObjectName("DigitMeta")
        self.lbl_meta.setWordWrap(True)
        info.addWidget(self.lbl_meta)
        h.addLayout(info, 1)

        self.status_badge = StatusBadge("MENUNGGU")
        h.addWidget(self.status_badge, 0, Qt.AlignTop)
        layout.addWidget(header)

        self.step_tracker = StepTracker(self.STEP_NAMES)
        self.step_tracker.step_clicked.connect(self._go_to_step)
        layout.addWidget(self.step_tracker)

        self.stack = QStackedWidget()
        self.stack.addWidget(self._create_step_page())
        self.stack.addWidget(self._create_review_page())
        self.stack.addWidget(self._create_process_page())
        self.stack.addWidget(self._create_done_page())
        layout.addWidget(self.stack, 1)
        fade_in(self.stack, duration=200)

        self._set_step_enabled(0)

    # ---------- Langkah 1: halaman + deteksi otomatis ----------
    def _create_step_page(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        layout.addWidget(
            GuideBanner(
                "Langkah 1 — Pilih Halaman Denah",
                [
                    "Halaman <b>Gambar Situasi</b> dipilih otomatis; Anda bisa menggantinya.",
                    "Polyline batas langsung <b>terdeteksi otomatis</b> dan digambar hijau di atas denah.",
                    "Tarik kotak pada denah lalu klik <b>Konfirmasi Potongan</b> agar hanya area itu yang dimasukkan ke AutoCAD.",
                    "Geser titik hijau untuk koreksi. Klik 2x pada garis untuk menambah titik, klik kanan titik untuk menghapus.",
                ],
            )
        )

        content = QHBoxLayout()
        content.setSpacing(12)

        panel = QFrame()
        panel.setObjectName("SectionCard")
        panel.setFixedWidth(252)
        p = QVBoxLayout(panel)
        p.setContentsMargins(14, 12, 14, 12)
        p.setSpacing(8)

        self.combo_page = QComboBox()
        self.combo_page.currentIndexChanged.connect(self._on_page_changed)
        p.addWidget(
            FormField("Halaman PDF", "Saran otomatis. Ganti bila perlu.", self.combo_page)
        )

        self.btn_detect_again = Button(
            "Deteksi Ulang",
            size="sm",
            tone="secondary",
            tooltip="Jalankan kembali deteksi polyline pada halaman yang dipilih",
        )
        self.btn_detect_again.clicked.connect(self._redetect_current_page)
        p.addWidget(self.btn_detect_again)

        self.btn_manual_draw = Button(
            "Titik Manual",
            size="sm",
            tone="primary",
            tooltip="Gambar polyline tangan bebas (aktif kapan saja, tanpa menunggu auto-detect)",
        )
        self.btn_manual_draw.clicked.connect(self._start_manual_draw)
        p.addWidget(self.btn_manual_draw)

        self.btn_set_crop = Button(
            "Area Potongan",
            size="sm",
            tone="secondary",
            tooltip="Tarik kotak pada denah untuk menentukan area yang dimasukkan ke AutoCAD, lalu klik 'Konfirmasi Potongan'",
        )
        self.btn_set_crop.clicked.connect(self._prompt_crop_selection)
        p.addWidget(self.btn_set_crop)

        self.lbl_crop_area = QLabel("Area potongan: penuh halaman")
        self.lbl_crop_area.setObjectName("DetectionInfo")
        self.lbl_crop_area.setWordWrap(True)
        p.addWidget(self.lbl_crop_area)

        self.combo_candidate = QComboBox()
        self.combo_candidate.currentIndexChanged.connect(self._on_candidate_changed)
        p.addWidget(
            FormField("Kandidat", "Pilih batas bidang yang tepat.", self.combo_candidate)
        )

        self.lbl_detection_status = QLabel("Menunggu PDF dibuka…")
        self.lbl_detection_status.setObjectName("DetectionStatus")
        self.lbl_detection_status.setWordWrap(True)
        p.addWidget(self.lbl_detection_status)

        self.lbl_detection_info = QLabel(
            "Belum ada polyline.\nGeser titik hijau setelah deteksi selesai."
        )
        self.lbl_detection_info.setObjectName("DetectionInfo")
        self.lbl_detection_info.setWordWrap(True)
        p.addWidget(self.lbl_detection_info)

        p.addStretch()
        self.btn_use_polyline = Button(
            "Gunakan Polyline",
            size="md",
            tone="primary",
            tooltip="Setujui polyline lalu lanjut ke data dokumen",
        )
        self.btn_use_polyline.setEnabled(False)
        self.btn_use_polyline.clicked.connect(self._accept_polyline)
        p.addWidget(self.btn_use_polyline)
        content.addWidget(panel)

        self.canvas = InteractiveCropCanvas()
        self.canvas.confirmed.connect(self._on_manual_crop_confirmed)
        self.canvas.polyline_changed.connect(self._on_polyline_edited)
        self.canvas.polyline_manual_finished.connect(self._on_manual_polyline_finished)
        self.canvas.manual_draw_cancelled.connect(self._on_manual_draw_cancelled)
        content.addWidget(self.canvas, 1)

        layout.addLayout(content, 1)
        return widget

    # ---------- Langkah 2: koreksi final + data dokumen ----------
    def _create_review_page(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        layout.addWidget(
            GuideBanner(
                "Langkah 2 — Periksa Polyline & Isi Data",
                [
                    "Polyline disetujui di Langkah 1. Klik <b>Deteksi</b> bila ingin mengoreksi titiknya.",
                    "Isi <b>Jenis Hak, Nomor Hak, Nomor GS, Tahun</b>, dan <b>Luas Dokumen</b>. Nilai otomatis dari PDF tetap harus diperiksa.",
                ],
            )
        )

        card = QFrame()
        card.setObjectName("SectionCard")
        c = QVBoxLayout(card)
        c.setContentsMargins(14, 12, 14, 12)
        c.setSpacing(10)

        self.lbl_review_summary = QLabel("Ringkasan deteksi akan tampil di sini.")
        self.lbl_review_summary.setObjectName("ReviewSummary")
        self.lbl_review_summary.setWordWrap(True)
        c.addWidget(self.lbl_review_summary)

        fields_row = QHBoxLayout()
        fields_row.setSpacing(12)

        form_box = QWidget()
        grid = QGridLayout(form_box)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(8)
        for col in range(5):
            grid.setColumnStretch(col, 1)

        self.combo_hak = QComboBox()
        for code, item in JENIS_HAK_MAP.items():
            self.combo_hak.addItem(item["label"], code)
        self.combo_hak.currentIndexChanged.connect(self._update_identity_preview)
        grid.addWidget(
            FormField("Jenis Hak", "Sesuai sertifikat.", self.combo_hak, required=True),
            0, 0,
        )

        self.input_no_hak = QLineEdit()
        self.input_no_hak.setPlaceholderText("1342")
        self.input_no_hak.textChanged.connect(self._update_identity_preview)
        grid.addWidget(
            FormField("Nomor Hak", "Angka sertifikat.", self.input_no_hak, required=True),
            0, 1,
        )

        self.input_no_gs = QLineEdit()
        self.input_no_gs.setPlaceholderText("176")
        self.input_no_gs.textChanged.connect(self._update_identity_preview)
        grid.addWidget(
            FormField("Nomor GS", "Nomor GS buku tanah.", self.input_no_gs, required=True),
            0, 2,
        )

        self.input_tahun = QLineEdit()
        self.input_tahun.setPlaceholderText("1969")
        self.input_tahun.textChanged.connect(self._update_identity_preview)
        grid.addWidget(
            FormField("Tahun", "Tahun terbit hak.", self.input_tahun, required=True),
            0, 3,
        )

        self.input_luas = QDoubleSpinBox()
        self.input_luas.setRange(0.01, 10_000_000.0)
        self.input_luas.setDecimals(2)
        self.input_luas.setSuffix(" m²")
        self.input_luas.valueChanged.connect(self._update_identity_preview)
        grid.addWidget(
            FormField("Luas Dokumen", "Target skala DWG.", self.input_luas, required=True),
            0, 4,
        )

        preview = QFrame()
        preview.setObjectName("IdentityPreview")
        preview.setFixedWidth(188)
        pv = QVBoxLayout(preview)
        pv.setContentsMargins(9, 7, 9, 7)
        pv.setSpacing(2)
        eyebrow = QLabel("IDENTITAS DI DWG")
        eyebrow.setObjectName("IdentityEyebrow")
        pv.addWidget(eyebrow)
        self.lbl_identity = QLabel("Lengkapi data terlebih dahulu")
        self.lbl_identity.setObjectName("IdentityValue")
        self.lbl_identity.setWordWrap(True)
        pv.addWidget(self.lbl_identity)
        self.lbl_file_preview = QLabel("—")
        self.lbl_file_preview.setObjectName("IdentityFile")
        self.lbl_file_preview.setWordWrap(True)
        pv.addWidget(self.lbl_file_preview)

        fields_row.addWidget(form_box, 1)
        fields_row.addWidget(preview, 0)
        c.addLayout(fields_row)

        nav = QHBoxLayout()
        nav.setSpacing(7)
        nav.addWidget(
            Button(
                "Deteksi",
                size="sm",
                tone="secondary",
                tooltip="Kembali ke langkah 1 untuk mengoreksi polyline",
                on_click=lambda: self._go_to_step(0),
            )
        )
        nav.addStretch()
        self.btn_save_data = Button(
            "Simpan && Lanjut",
            size="md",
            tone="primary",
            tooltip="Simpan identitas dokumen lalu lanjut ke proses otomatis",
        )
        self.btn_save_data.setEnabled(False)
        self.btn_save_data.clicked.connect(self._save_identity)
        nav.addWidget(self.btn_save_data)
        c.addLayout(nav)

        layout.addWidget(card)
        layout.addStretch()
        return widget

    # ---------- Langkah 3: satu tombol proses otomatis ----------
    def _create_process_page(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        layout.addWidget(
            GuideBanner(
                "Langkah 3 — Proses Otomatis",
                [
                    "Satu tombol: memotong denah, memasukkan <b>gambar ke DWG</b>, membuat polyline, menghitung skala, lalu menulis data dokumen.",
                    "Anda <b>tidak perlu</b> membuka AutoCAD atau menggambar polyline manual.",
                    "DWG berisi denah raster, polyline terskala, dan blok data dokumen.",
                ],
            )
        )

        card = QFrame()
        card.setObjectName("SectionCard")
        c = QVBoxLayout(card)
        c.setContentsMargins(14, 12, 14, 12)
        c.setSpacing(10)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        c.addWidget(self.progress)

        self.log_view = QTextEdit()
        self.log_view.setObjectName("ProcessLog")
        self.log_view.setReadOnly(True)
        self.log_view.setMinimumHeight(150)
        c.addWidget(self.log_view, 1)

        nav = QHBoxLayout()
        nav.setSpacing(7)
        nav.addWidget(
            Button(
                "Data",
                size="sm",
                tone="secondary",
                tooltip="Kembali ke langkah 2 untuk mengubah data dokumen",
                on_click=lambda: self._go_to_step(1),
            )
        )
        nav.addStretch()
        self.btn_run = Button(
            "Jalankan Proses",
            size="md",
            tone="primary",
            tooltip="Buat DWG berisi denah, polyline terskala, dan data dokumen",
        )
        self.btn_run.clicked.connect(self._run_auto_process)
        nav.addWidget(self.btn_run)
        c.addLayout(nav)

        layout.addWidget(card, 1)
        return widget

    # ---------- Langkah 4: hasil ----------
    def _create_done_page(self) -> QWidget:
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        card = QFrame()
        card.setObjectName("DoneCard")
        c = QVBoxLayout(card)
        c.setContentsMargins(22, 18, 22, 18)
        c.setSpacing(10)

        title = QLabel("Digitasi Selesai")
        title.setObjectName("DoneTitle")
        c.addWidget(title)

        self.lbl_done = QLabel("")
        self.lbl_done.setObjectName("DoneBody")
        self.lbl_done.setWordWrap(True)
        self.lbl_done.setTextInteractionFlags(Qt.TextSelectableByMouse)
        c.addWidget(self.lbl_done, 1)

        nav = QHBoxLayout()
        nav.setSpacing(8)
        self.btn_open_folder = Button(
            "Buka Folder",
            size="md",
            tone="secondary",
            tooltip="Buka folder penyimpanan hasil DWG",
        )
        self.btn_open_folder.clicked.connect(self._open_result_folder)
        nav.addWidget(self.btn_open_folder)
        nav.addStretch()
        self.btn_done_back = Button(
            "Kembali ke Antrean",
            size="md",
            tone="primary",
            tooltip="Kembali ke daftar dokumen",
        )
        self.btn_done_back.clicked.connect(self.back_to_queue.emit)
        nav.addWidget(self.btn_done_back)
        c.addLayout(nav)

        layout.addWidget(card, 2)

        side = QFrame()
        side.setObjectName("SectionCard")
        s = QVBoxLayout(side)
        s.setContentsMargins(16, 14, 16, 16)
        s.setSpacing(10)

        side_title = QLabel("Periksa Sebelum Diserahkan")
        side_title.setObjectName("SectionTitle")
        s.addWidget(side_title)
        for number, (head, desc) in enumerate(
            [
                ("Buka DWG di AutoCAD", "Pastikan denah dan polyline tampil tepat."),
                ("Periksa skala luas", "Bandingkan luas DWG dengan luas dokumen."),
                ("Ekspor rekap", "Unduh Excel atau paket ZIP di menu Laporan."),
            ],
            start=1,
        ):
            row = QHBoxLayout()
            row.setSpacing(10)
            badge = QLabel(str(number))
            badge.setObjectName("StepBadge")
            badge.setAlignment(Qt.AlignCenter)
            badge.setFixedSize(24, 24)
            row.addWidget(badge, 0, Qt.AlignTop)
            text = QVBoxLayout()
            text.setSpacing(0)
            t = QLabel(head)
            t.setObjectName("StepTitle")
            t.setWordWrap(True)
            d = QLabel(desc)
            d.setObjectName("StepDesc")
            d.setWordWrap(True)
            text.addWidget(t)
            text.addWidget(d)
            row.addLayout(text, 1)
            s.addLayout(row)
        s.addStretch(1)

        layout.addWidget(side, 1)
        return widget

    @staticmethod
    def _field_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet("font-size:12px;font-weight:700;color:#334155;")
        return label

    @staticmethod
    def _small_caps(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("IdentityEyebrow")
        label.setText(text)
        return label

    @staticmethod
    def _tone(widget, value: str):
        widget.setProperty("tone", value)
        widget.style().unpolish(widget)
        widget.style().polish(widget)

    def _set_detection_status(self, text: str, tone: str = "neutral"):
        self.lbl_detection_status.setText(text)
        self._tone(self.lbl_detection_status, tone)

    # =================================================================
    # AREA POTONGAN (raster yang dimasukkan ke AutoCAD)
    # =================================================================
    def _crop_area_text(self) -> str:
        box = self.crop_box
        if len(box) != 4:
            return "penuh halaman"
        width = max(0.0, float(box[2]) - float(box[0]))
        height = max(0.0, float(box[3]) - float(box[1]))
        if width >= 0.999 and height >= 0.999:
            return "penuh halaman"
        return f"{width * 100:.0f}% × {height * 100:.0f}% halaman"

    def _update_crop_area_label(self):
        self.lbl_crop_area.setText(f"Area potongan: {self._crop_area_text()}")

    def _prompt_crop_selection(self):
        """Arahkan operator menarik kotak area yang akan dimasukkan ke AutoCAD."""
        if not self.canvas.has_image():
            QMessageBox.information(
                self, "Halaman Belum Dimuat",
                "Tunggu hingga gambar denah tampil, lalu tentukan area potongan.",
            )
            return
        if self.canvas.draw_mode:
            self._finish_manual_draw()
        self.canvas.reset_crop()
        self._set_detection_status(
            "Tarik kotak pada denah, lalu klik 'Konfirmasi Potongan'.", "info"
        )
        self.lbl_detection_info.setText(
            "Area Potongan: tarik kotak pada denah untuk membatasi area.\n"
            "Hanya area di dalam kotak yang dimasukkan ke AutoCAD."
        )
        self.canvas.info_label.setText(
            "Tarik kotak pada denah, lalu klik 'Konfirmasi Potongan'."
        )

    @staticmethod
    def _crop_box_from_points(points: list, padding_ratio: float = 0.06) -> tuple:
        """Kotak ternormalisasi di sekitar polyline (bukan seluruh halaman)."""
        xs = [float(p[0]) for p in points]
        ys = [float(p[1]) for p in points]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        pad_x = max(0.02, (max_x - min_x) * padding_ratio)
        pad_y = max(0.02, (max_y - min_y) * padding_ratio)
        clamp = lambda v: max(0.0, min(1.0, v))
        return (
            round(clamp(min_x - pad_x), 6),
            round(clamp(min_y - pad_y), 6),
            round(clamp(max_x + pad_x), 6),
            round(clamp(max_y + pad_y), 6),
        )

    def _resolve_manual_crop_box(self, points: list) -> tuple:
        """Area potongan untuk polyline manual: pakai area terkonfirmasi bila ada."""
        if self.crop_confirmed_by_user and len(self.crop_box) == 4:
            return tuple(float(v) for v in self.crop_box)
        return self._crop_box_from_points(points)

    # =================================================================
    # NAVIGASI & STATE
    # =================================================================
    def _set_step_enabled(self, step: int):
        self.stack.setCurrentIndex(step)
        self.step_tracker.set_current_step(step)
        for idx in range(1, len(self.STEP_NAMES)):
            self.step_tracker.buttons[idx].setEnabled(idx <= step)

    def _go_to_step(self, step: int):
        if step == 1 and len(self.polyline_normalized) < 3:
            QMessageBox.warning(self, "Polyline Belum Ada", "Setujui polyline hasil deteksi terlebih dahulu.")
            return
        if step >= 2 and not (self.doc_data.get("identitas_dokumen") and self.doc_data.get("luas_dokumen")):
            QMessageBox.warning(self, "Data Belum Lengkap", "Simpan data dokumen pada Langkah 2 terlebih dahulu.")
            return
        self._set_step_enabled(step)

    def _reset_state(self):
        self.doc_id = None
        self.doc_data = {}
        self.batch_data = {}
        self.candidates = []
        self.selected_index = 0
        self.polyline_normalized = []
        self.detection_meta = {}
        self.crop_box = ()
        self.crop_confirmed_by_user = False
        self.crop_path = ""
        self.processing = False
        self._detect_cache.clear()
        self.canvas.clear_polyline()
        self.log_view.clear()
        self.progress.setValue(0)
        self._set_detection_status("Menunggu PDF dibuka…")
        self.lbl_detection_info.setText("Belum ada polyline.")
        self._update_crop_area_label()
        self.combo_candidate.clear()
        self.btn_use_polyline.setEnabled(False)
        self.btn_manual_draw.setEnabled(True)
        self.btn_detect_again.setEnabled(True)

    def load_document(self, doc_id: int):
        self._reset_state()
        self.doc_id = doc_id
        self.doc_data = get_document(doc_id) or {}
        if not self.doc_data:
            return
        # Proses dokumen baru selalu dimulai dari Langkah 1 agar operator
        # menempuh urutan 1 → 2 → 3 → 4 (tanpa acuh) — reset langkah ke 0.
        self._set_step_enabled(0)

        self.batch_data = get_batch(self.doc_data.get("batch_id")) or {}
        desa = self.batch_data.get("nama_desa", "-")
        kec = self.batch_data.get("kecamatan", "-")
        self.lbl_title.setText(f"Dokumen: {self.doc_data.get('nama_pdf', '-')}")
        self.lbl_meta.setText(f"Desa {desa} • Kecamatan {kec}")
        self.status_badge.set_status(self.doc_data.get("status", "MENUNGGU"))

        # Form identitas (data lama bila ada)
        if self.doc_data.get("kode_hak"):
            idx = self.combo_hak.findData(str(self.doc_data["kode_hak"]))
            if idx >= 0:
                self.combo_hak.setCurrentIndex(idx)
        self.input_no_hak.setText(str(self.doc_data.get("nomor_hak") or ""))
        self.input_no_gs.setText(str(self.doc_data.get("nomor_gs") or ""))
        self.input_tahun.setText(str(self.doc_data.get("tahun") or ""))
        if self.doc_data.get("luas_dokumen"):
            self.input_luas.setValue(float(self.doc_data["luas_dokumen"]))

        pdf_path = self.doc_data.get("path_pdf", "")
        if not pdf_path or not os.path.exists(pdf_path):
            self._set_detection_status("File PDF tidak ditemukan. Periksa menu Antrean Dokumen.", "error")
            return

        info = get_pdf_info(pdf_path)
        if not info.get("success"):
            self._set_detection_status(f"Gagal membaca PDF: {info.get('error')}", "error")
            return

        self.combo_page.blockSignals(True)
        self.combo_page.clear()
        for page in range(1, info["page_count"] + 1):
            self.combo_page.addItem(f"Halaman {page}", page)
        self.combo_page.blockSignals(False)

        suggestion = suggest_denah_page(pdf_path)
        saved_page = int(self.doc_data.get("halaman_pdf") or 0)
        target_page = suggestion.get("page", 1) if suggestion.get("success") else 1
        # Halaman tersimpan hanya dipakai jika dokumen sudah punya hasil deteksi,
        # sehingga saran otomatis tetap berlaku untuk PDF yang baru diimpor.
        if 1 <= saved_page <= info["page_count"] and self.doc_data.get("detected_vertices_json"):
            target_page = saved_page
        idx = self.combo_page.findData(target_page)
        self.combo_page.setCurrentIndex(max(0, idx))

        page_info = info["pages"][target_page - 1]
        self.detection_meta = {
            "page": target_page,
            "image_width": round(float(page_info["width"]) * DETECTION_DPI / 72.0),
            "image_height": round(float(page_info["height"]) * DETECTION_DPI / 72.0),
            "dpi": DETECTION_DPI,
        }
        self._load_page_preview(pdf_path, target_page)

        self._prefill_hints(pdf_path)
        if self.doc_data.get("detected_vertices_json"):
            self._show_saved_detection()
        else:
            self._detect_page(target_page)

    def _prefill_hints(self, pdf_path: str):
        hints = guess_document_hints(pdf_path)
        if not self.input_no_gs.text() and hints.get("nomor_gs"):
            self.input_no_gs.setText(hints["nomor_gs"])
        if not self.input_tahun.text() and hints.get("tahun"):
            self.input_tahun.setText(hints["tahun"])
        if not self.doc_data.get("luas_dokumen") and hints.get("luas_dokumen"):
            try:
                self.input_luas.setValue(float(hints["luas_dokumen"].replace(",", ".")))
            except ValueError:
                pass
        self._update_identity_preview()

    # =================================================================
    # DETEKSI & KOREKSI
    # =================================================================
    def _on_page_changed(self, _index: int):
        if not self.doc_id:
            return
        # Area potongan terikat pada halaman; mulai bersih saat halaman diganti.
        self.crop_box = ()
        self.crop_confirmed_by_user = False
        self._update_crop_area_label()
        page = self.combo_page.currentData()
        if page:
            self._detect_page(int(page))

    def _redetect_current_page(self):
        if not self.doc_id:
            return
        page = self.combo_page.currentData()
        if page:
            self._detect_page(int(page))

    def _load_page_preview(self, pdf_path: str, page_number: int):
        """Muat pratinjau halaman dari array render yang sama dengan deteksi
        otomatis (karena render_page_array direuse, hanya satu pixmap)."""
        import io
        from PIL import Image

        arr, _err = render_page_array(pdf_path, page_number, dpi=DETECTION_PREVIEW_DPI)
        if arr is None:
            return
        try:
            buf = io.BytesIO()
            Image.fromarray(arr).save(buf, format="PNG")
            self.canvas.load_page_image(buf.getvalue())
        except Exception:
            pass

    def _show_saved_detection(self):
        """Menampilkan polyline hasil koreksi sebelumnya agar tidak hilang saat membuka ulang."""
        try:
            points = [tuple(p) for p in json.loads(self.doc_data.get("detected_vertices_json") or "[]")]
        except (ValueError, TypeError):
            points = []
        if len(points) < 3:
            self._detect_page(int(self.detection_meta.get("page") or 1))
            return

        try:
            crop_box = tuple(json.loads(self.doc_data.get("crop_box_json") or "[]"))
        except (ValueError, TypeError):
            crop_box = ()
        if len(crop_box) != 4:
            crop_box = (0.0, 0.0, 1.0, 1.0)

        candidate = {
            "vertices_normalized": [list(p) for p in points],
            "crop_box_normalized": list(crop_box),
            "confidence": float(self.doc_data.get("detection_confidence") or 0.0),
            "area_px": float(self.doc_data.get("detected_area_px") or 0.0),
            "vertex_count": len(points),
            "method": self.doc_data.get("detection_method") or "tersimpan",
        }
        self.candidates = [candidate]
        self.selected_index = 0
        self.polyline_normalized = points
        self.crop_box = crop_box

        self.combo_candidate.blockSignals(True)
        self.combo_candidate.clear()
        self.combo_candidate.addItem("Polyline tersimpan (hasil koreksi)", 0)
        self.combo_candidate.blockSignals(False)
        self.canvas.show_polyline(points)
        self.btn_use_polyline.setEnabled(True)
        self._set_detection_status(
            "Polyline tersimpan ditampilkan. Geser titik bila ingin mengoreksi.", "ok"
        )
        self._update_detection_info()

    def _detect_page(self, page_number: int):
        pdf_path = self.doc_data.get("path_pdf", "")
        if not pdf_path or not os.path.exists(pdf_path):
            return

        # Deteksi otomatis direuse jika halaman sama sudah diperiksa
        # (mis. operator beralih halaman turun dan kembali).
        cache_key = (os.path.abspath(pdf_path), int(page_number))
        cached = self._detect_cache.get(cache_key)
        if cached is not None:
            result = cached
        else:
            self._set_detection_status(f"Mendeteksi polyline pada halaman {page_number}…")
            QApplication.processEvents()

            if self.doc_id:
                update_document(self.doc_id, halaman_pdf=page_number)

            self._load_page_preview(pdf_path, page_number)

            image, _preview_err = render_page_array(
                pdf_path, page_number, dpi=DETECTION_SCAN_DPI
            )
            result = detect_on_page(pdf_path, page_number, dpi=DETECTION_SCAN_DPI, image=image)
            # Copy list/dict supaya operasi selanjutnya (mis. penambahan
            # kandidat manual) tidak mengaburkan cache deteksi otomatis.
            result["candidates"] = [dict(c) for c in result.get("candidates", [])]
            self._detect_cache[cache_key] = result

        self.detection_meta = {
            "page": page_number,
            "image_width": result.get("image_width", 0),
            "image_height": result.get("image_height", 0),
            "dpi": result.get("dpi", DETECTION_SCAN_DPI),
        }
        self.candidates = list(result.get("candidates", []))

        self.combo_candidate.blockSignals(True)
        self.combo_candidate.clear()
        for idx, cand in enumerate(self.candidates):
            self.combo_candidate.addItem(
                f"Kandidat {idx + 1} • {cand.get('confidence', 0) * 100:.0f}% • {cand.get('vertex_count', 0)} titik",
                idx,
            )
        self.combo_candidate.blockSignals(False)

        if self.candidates:
            self.combo_candidate.setCurrentIndex(0)
            self._show_candidate(0)
            self._set_detection_status(result.get("message", "Deteksi berhasil."), "ok")
            self.btn_use_polyline.setEnabled(True)
        else:
            self._set_detection_status(
                result.get("message", "Deteksi gagal.")
                + " Anda juga bisa menarik kotak pada gambar untuk memilih area denah.",
                "error",
            )
            self.btn_use_polyline.setEnabled(False)
            self.canvas.clear_polyline()
            if not self.crop_confirmed_by_user:
                self.crop_box = ()
                self._update_crop_area_label()
            self._update_detection_info()

    def _show_candidate(self, index: int):
        if not (0 <= index < len(self.candidates)):
            return
        self.selected_index = index
        cand = self.candidates[index]
        self.polyline_normalized = [tuple(p) for p in cand.get("vertices_normalized", [])]
        self.crop_box = tuple(cand.get("crop_box_normalized") or ())
        self.canvas.show_polyline(self.polyline_normalized)
        self._update_crop_area_label()
        self._update_detection_info()

    def _on_candidate_changed(self, _index: int):
        idx = self.combo_candidate.currentData()
        if idx is not None:
            self._show_candidate(int(idx))

    def _on_polyline_edited(self, points: list):
        self.polyline_normalized = [tuple(p) for p in points]
        self._update_detection_info()

    def _update_detection_info(self):
        n = len(self.polyline_normalized)
        if not n:
            self.lbl_detection_info.setText(
                "Belum ada polyline.\nGeser titik hijau setelah deteksi, atau tutup area denah dengan mouse untuk deteksi ulang."
            )
            return
        cand = self.candidates[self.selected_index] if self.candidates else {}
        conf = float(cand.get("confidence", 0.0)) * 100
        width = float(self.detection_meta.get("image_width") or 0)
        height = float(self.detection_meta.get("image_height") or 0)
        pts_px = [(nx * width, ny * height) for nx, ny in self.polyline_normalized]
        area = polygon_area(pts_px)
        self.lbl_detection_info.setText(
            f"Polyline siap: <b>{n} titik</b>\n"
            f"Keyakinan deteksi: <b>{conf:.0f}%</b>\n"
            f"Luas citra: <b>{area:,.0f} px²</b>\n"
            f"Area masuk DWG: <b>{self._crop_area_text()}</b>\n\n"
            "Geser titik hijau bila perlu, lalu klik 'Gunakan Polyline Ini'."
        )

    def _on_manual_crop_confirmed(self, norm_box: tuple):
        """
        Operator menentukan area potongan dengan mouse.
        Area ini yang dipakai sebagai raster di AutoCAD; deteksi otomatis hanya
        dijalankan bila belum ada polyline manual.
        """
        if len(norm_box) != 4:
            return
        norm_box = tuple(float(v) for v in norm_box)
        self.crop_box = norm_box
        self.crop_confirmed_by_user = True
        self._update_crop_area_label()

        # Polyline manual yang sudah ada tidak boleh hilang; cukup perbarui areanya.
        manual_cands = [c for c in self.candidates if c.get("method") == "manual-draw"]
        if manual_cands:
            for cand in manual_cands:
                cand["crop_box_normalized"] = list(norm_box)
            self._set_detection_status(
                "Area potongan diperbarui. Polyline manual tetap dipakai.", "ok"
            )
            self._update_detection_info()
            return

        pdf_path = self.doc_data.get("path_pdf", "")
        page = self.combo_page.currentData() or 1
        if not pdf_path or not os.path.exists(pdf_path):
            self._set_detection_status("Area potongan disimpan.", "ok")
            return

        name = f"manual_{uuid.uuid4().hex[:8]}.png"
        ok, path = crop_pdf_region_to_file(pdf_path, int(page), norm_box, name, dpi=DETECTION_DPI)
        if not ok:
            self._set_detection_status("Area potongan disimpan.", "ok")
            QMessageBox.warning(self, "Gagal Memotong", path)
            return
        import numpy as np
        from PIL import Image

        try:
            image = Image.open(path).convert("RGB")
            array = np.asarray(image)
        except Exception as exc:
            self._set_detection_status("Area potongan disimpan.", "ok")
            QMessageBox.warning(self, "Gagal Membaca Gambar", str(exc))
            return

        result = detect_polylines_from_array(array)
        x0, y0, x1, y1 = norm_box
        cands = []
        for cand in result.get("candidates", []):
            mapped = []
            for nx, ny in cand.get("vertices_normalized", []):
                mapped.append((x0 + nx * (x1 - x0), y0 + ny * (y1 - y0)))
            new_cand = dict(cand)
            new_cand["vertices_normalized"] = [list(p) for p in mapped]
            new_cand["crop_box_normalized"] = list(norm_box)
            cands.append(new_cand)

        if not cands:
            self._set_detection_status(
                "Area potongan disimpan. Deteksi otomatis gagal; gunakan Titik Manual.", "warn"
            )
            QMessageBox.information(
                self, "Deteksi Otomatis Gagal",
                "Polyline tidak ditemukan pada area ini, tetapi area potongan sudah disimpan.\n"
                "Klik 'Titik Manual' untuk menggambar batas tanah secara manual."
            )
            return

        self.candidates = cands
        # detection_meta tetap memakai ukuran halaman penuh karena titik disimpan
        # dalam koordinat ternormalisasi terhadap halaman PDF.
        self.combo_candidate.clear()
        for idx, cand in enumerate(cands):
            self.combo_candidate.addItem(
                f"Area manual {idx + 1} • {cand.get('confidence', 0) * 100:.0f}%", idx
            )
        self.combo_candidate.setCurrentIndex(0)
        self._show_candidate(0)
        self.btn_use_polyline.setEnabled(True)
        self._set_detection_status(
            "Polyline berhasil dideteksi dari area yang Anda pilih.", "ok"
        )

    def _accept_polyline(self):
        if len(self.polyline_normalized) < 3 or not self.doc_id:
            QMessageBox.warning(self, "Polyline Belum Valid", "Minimal tiga titik polyline diperlukan.")
            return
        save_detection_result(
            self.doc_id,
            self.candidates,
            selected_index=self.selected_index,
            crop_box=self.crop_box,
            crop_dpi=DETECTION_CROP_DPI,
            luas_dokumen=self.doc_data.get("luas_dokumen"),
        )
        self.doc_data["status"] = STATUS_TERDETEKSI
        self.doc_data["detected_vertices_json"] = json.dumps(self.polyline_normalized)
        self.status_badge.set_status(STATUS_TERDETEKSI)
        self.step_tracker.mark_completed(0)

        cand = self.candidates[self.selected_index] if self.candidates else {}
        self.lbl_review_summary.setText(
            f"Polyline disetujui: <b>{len(self.polyline_normalized)} titik</b> • "
            f"keyakinan <b>{float(cand.get('confidence', 0)) * 100:.0f}%</b> • "
            f"halaman <b>{self.detection_meta.get('page', '-')}</b>.<br>"
            f"Area yang masuk ke DWG: <b>{self._crop_area_text()}</b>. "
            "Geser titik di Langkah 1 bila perlu koreksi."
        )
        self._go_to_step(1)

    # =================================================================
    # TITIK MANUAL (draw polyline bebas)
    # =================================================================
    def _start_manual_draw(self):
        """Aktifkan mode titik manual di canvas. Bisa dipakai kapan saja."""
        if not self.doc_id:
            QMessageBox.information(
                self, "Belum Ada Dokumen",
                "Buka dokumen dari menu Antrean terlebih dahulu.",
            )
            return
        if not self.canvas.has_image():
            QMessageBox.information(
                self, "Halaman Belum Dimuat",
                "Pratinjau halaman denah belum siap. Tunggu hingga gambar denah tampil, lalu coba lagi.",
            )
            return

        self.btn_detect_again.setEnabled(False)
        self.btn_manual_draw.setEnabled(False)
        self.canvas.start_manual_draw()
        self._set_detection_status(
            "Mode Titik Manual aktif. Klik pada denah, klik 2x untuk menyegel.", "info"
        )
        self.lbl_detection_info.setText(
            "Titik Manual: klik pada denah untuk menambah titik.\n"
            "Klik 2x untuk menyegel polyline • Esc untuk membatalkan.\n\n"
            + (
                "Area masuk AutoCAD: area yang Anda konfirmasi."
                if self.crop_confirmed_by_user
                else "Area masuk AutoCAD: otomatis mengikuti batas polyline."
            )
        )
        self.status_badge.set_status("Gambar Manual")

    def _finish_manual_draw(self):
        """Kembalikan kontrol UI setelah mode manual selesai/dibatalkan."""
        self.canvas.cancel_manual_draw()
        self.btn_detect_again.setEnabled(True)
        self.btn_manual_draw.setEnabled(True)

    def _on_manual_polyline_finished(self, normalized_points: list):
        """Dipanggil canvas saat polyline manual disegel (double-click)."""
        self._finish_manual_draw()
        self._process_manual_candidate(normalized_points)

    def _on_manual_draw_cancelled(self):
        """Pulihkan kontrol UI saat mode manual dibatalkan (Esc)."""
        self.btn_detect_again.setEnabled(True)
        self.btn_manual_draw.setEnabled(True)
        self.status_badge.set_status(self.doc_data.get("status") or "MENUNGGU")
        self._set_detection_status("Mode Titik Manual dibatalkan.", "neutral")
        self._update_detection_info()

    def _process_manual_candidate(self, normalized_points: list):
        """Tambahkan polyline manual sebagai kandidat dan lanjut ke Langkah 2."""
        points = [tuple(p) for p in normalized_points]
        if len(points) < 3:
            QMessageBox.warning(self, "Polyline Tidak Valid", "Minimal tiga titik diperlukan.")
            self.status_badge.set_status(self.doc_data.get("status") or "MENUNGGU")
            return

        self.polyline_normalized = points
        self.crop_box = self._resolve_manual_crop_box(points)
        self._update_crop_area_label()

        # Tambahkan sebagai kandidat baru tanpa menghapus hasil auto-detect.
        manual_index = len(self.candidates)
        self.candidates.append({
            "vertices_normalized": [list(p) for p in points],
            "crop_box_normalized": list(self.crop_box),
            "confidence": 0.30,
            "vertex_count": len(points),
            "method": "manual-draw",
        })
        self.selected_index = manual_index

        # Simpan ke DB (mirror `_accept_polyline`) agar polyline manual ketemu
        # saat dokumen dibuka ulang nanti — juga menyu badge status TERDETEKSI konsisten.
        save_detection_result(
            self.doc_id,
            self.candidates,
            selected_index=self.selected_index,
            crop_box=self.crop_box,
            crop_dpi=DETECTION_CROP_DPI,
            luas_dokumen=self.doc_data.get("luas_dokumen"),
        )
        self.doc_data["status"] = STATUS_TERDETEKSI

        self.combo_candidate.blockSignals(True)
        self.combo_candidate.addItem(
            f"Polyline Manual • {len(points)} titik (digambar operator)", manual_index
        )
        self.combo_candidate.setCurrentIndex(self.combo_candidate.count() - 1)
        self.combo_candidate.blockSignals(False)

        self.canvas.show_polyline(self.polyline_normalized)
        self.btn_use_polyline.setEnabled(True)
        self.status_badge.set_status(STATUS_TERDETEKSI)
        self._set_detection_status("Polyline manual siap digunakan.", "ok")
        self._update_detection_info()

        self.lbl_review_summary.setText(
            f"Polyline manual disetujui: <b>{len(points)} titik</b> • "
            "keyakinan <b>~30%</b> • digambar manual oleh operator.<br>"
            f"Area yang masuk ke DWG: <b>{self._crop_area_text()}</b>."
        )
        self.status_badge.set_status(self.doc_data.get("status") or "MENUNGGU")
        self._go_to_step(1)


    def _update_identity_preview(self):
        kode = self.combo_hak.currentData()
        no_hak = self.input_no_hak.text().strip()
        no_gs = self.input_no_gs.text().strip()
        tahun = self.input_tahun.text().strip()

        if not (kode and no_hak and no_gs and tahun):
            self.lbl_identity.setText("Lengkapi data terlebih dahulu")
            self._tone(self.lbl_identity, "empty")
            self.lbl_file_preview.setText("Nama file DWG akan tampil setelah data lengkap.")
            self.btn_save_data.setEnabled(False)
            return

        identity = format_document_identity(kode, no_hak, no_gs, tahun)
        safe = sanitize_filename(identity, ".dwg")
        self.lbl_identity.setText(identity)
        self._tone(self.lbl_identity, "ready")
        self.lbl_file_preview.setText(f"Nama file: {safe}")
        self.btn_save_data.setEnabled(True)

    def _save_identity(self):
        kode = self.combo_hak.currentData()
        no_hak = self.input_no_hak.text().strip()
        no_gs = self.input_no_gs.text().strip()
        tahun = self.input_tahun.text().strip()
        luas = self.input_luas.value()

        valid, err = validate_document_input(kode, no_hak, no_gs, tahun, luas)
        if not valid:
            QMessageBox.warning(self, "Data Belum Valid", err)
            return

        identity = format_document_identity(kode, no_hak, no_gs, tahun)
        update_document(
            self.doc_id,
            kode_hak=kode,
            jenis_hak=self.combo_hak.currentText(),
            nomor_hak=no_hak,
            nomor_gs=normalize_gs_number(no_gs),
            tahun=tahun,
            identitas_dokumen=identity,
            luas_dokumen=luas,
            status=STATUS_MENUNGGU_TRACING,
        )
        self.doc_data.update({
            "kode_hak": kode,
            "nomor_hak": no_hak,
            "nomor_gs": normalize_gs_number(no_gs),
            "tahun": tahun,
            "identitas_dokumen": identity,
            "luas_dokumen": luas,
            "status": STATUS_MENUNGGU_TRACING,
        })
        self.status_badge.set_status(STATUS_MENUNGGU_TRACING)
        self.step_tracker.mark_completed(1)
        self._go_to_step(2)

    # =================================================================
    # PROSES OTOMATIS
    # =================================================================
    def _log(self, message: str, percent: int = 0):
        stamp = datetime.now().strftime("%H:%M:%S")
        self.log_view.append(f"[{stamp}] {message}")
        if percent:
            self.progress.setValue(percent)
        QApplication.processEvents()

    def _get_template_path(self) -> str:
        """Mengembalikan template resmi bila valid; kosong berarti buat DWG baru."""
        configured = get_setting("template_dwg_path", str(DEFAULT_TEMPLATE_PATH))
        candidate = Path(configured) if configured else Path(DEFAULT_TEMPLATE_PATH)
        if candidate.exists() and candidate.stat().st_size > 1024:
            return str(candidate)
        return ""

    def _parcel_label_lines(self) -> tuple[str, str]:
        """Label 2 baris di tengah denah: 'M. 00831' dan 'GS00013/1995'."""
        kode = str(self.doc_data.get("kode_hak") or "")
        awalan = get_awalan_hak(kode)
        nomor_hak = str(self.doc_data.get("nomor_hak") or "").strip()
        if nomor_hak.isdigit():
            nomor_hak = nomor_hak.zfill(5)
        nomor_gs = str(self.doc_data.get("nomor_gs") or "").strip()
        tahun = str(self.doc_data.get("tahun") or "").strip()
        gs = normalize_gs_number(nomor_gs) if nomor_gs else ""
        line1 = f"{awalan} {nomor_hak}".strip()
        if gs and tahun:
            line2 = f"{gs}/{tahun}"
        else:
            line2 = gs or tahun
        return line1, line2

    def _ensure_autocad(self) -> bool:
        ok, msg = autocad_service.connect(launch_if_closed=True)
        if ok:
            self._log(f"AutoCAD terhubung: {msg}")
            return True

        QMessageBox.critical(
            self, "AutoCAD Tidak Terdeteksi",
            f"{msg}\n\nPastikan AutoCAD 2021 terpasang dan lisensi aktif, lalu coba lagi."
        )
        return False

    def _run_auto_process(self):
        if self.processing:
            return

        identity = self.doc_data.get("identitas_dokumen")
        luas_doc = float(self.doc_data.get("luas_dokumen") or 0.0)
        pdf_path = self.doc_data.get("path_pdf", "")
        if not (identity and luas_doc > 0 and len(self.polyline_normalized) >= 3 and os.path.exists(pdf_path)):
            QMessageBox.warning(self, "Data Belum Lengkap", "Lengkapi Langkah 1 dan 2 terlebih dahulu.")
            return

        self.processing = True
        self.btn_run.setEnabled(False)
        self.progress.setValue(0)
        self.log_view.clear()
        try:
            self._execute_auto_process(identity, luas_doc, pdf_path)
        except Exception as exc:
            self._log(f"ERROR: {exc}", 0)
            update_document(self.doc_id, status="GAGAL")
            self.doc_data["status"] = "GAGAL"
            self.status_badge.set_status("GAGAL")
            QMessageBox.critical(self, "Proses Gagal", str(exc))
        finally:
            self.processing = False
            self.btn_run.setEnabled(True)

    def _execute_auto_process(self, identity: str, luas_doc: float, pdf_path: str):
        from PIL import Image

        page = int(self.detection_meta.get("page") or self.doc_data.get("halaman_pdf") or 1)
        box = self.crop_box or (0.0, 0.0, 1.0, 1.0)
        if len(box) != 4:
            box = (0.0, 0.0, 1.0, 1.0)

        desa = (self.batch_data.get("nama_desa") or "Desa").replace(" ", "_")
        batch_folder = HASIL_DIGITASI_DIR / f"Batch_{self.doc_data.get('batch_id', 0)}_{desa}"
        batch_folder.mkdir(parents=True, exist_ok=True)
        denah_dir = batch_folder / "Gambar_Denah"
        denah_dir.mkdir(parents=True, exist_ok=True)

        # 1. Potong denah resolusi tinggi dan simpan di folder hasil yang permanen.
        method = (
            self.candidates[self.selected_index].get("method", "opencv")
            if self.candidates
            else "manual"
        )
        self._log(f"Sumber polyline: {method}", 8)
        self._log(f"Memotong denah halaman {page} (300 DPI)…", 10)
        crop_name = f"crop_doc_{self.doc_id}_{uuid.uuid4().hex[:8]}.png"
        ok, temp_crop_path = crop_pdf_region_to_file(pdf_path, page, box, crop_name, dpi=DETECTION_CROP_DPI)
        if not ok:
            raise RuntimeError(temp_crop_path)
        crop_path = str(denah_dir / crop_name)
        shutil.copy2(temp_crop_path, crop_path)
        self.crop_path = crop_path
        update_document(self.doc_id, path_crop=crop_path, crop_box_json=json.dumps(box), crop_dpi=DETECTION_CROP_DPI)
        self._log(f"Gambar denah disimpan: {Path(crop_path).name}", 15)

        with Image.open(crop_path) as img:
            crop_w, crop_h = img.size

        # 2. Konversi titik ternormalisasi (halaman) -> piksel gambar hasil crop
        x0, y0, x1, y1 = box
        span_x, span_y = max(1e-9, x1 - x0), max(1e-9, y1 - y0)
        vertices_px = [
            ((nx - x0) / span_x * crop_w, (ny - y0) / span_y * crop_h)
            for nx, ny in self.polyline_normalized
        ]
        area_px = polygon_area(vertices_px)
        if area_px <= 0:
            raise RuntimeError("Luas polyline hasil deteksi tidak valid.")
        skala_m_per_px = math.sqrt(luas_doc / area_px)
        self._log(
            f"Polyline {len(vertices_px)} titik • luas citra {area_px:,.0f} px² "
            f"• skala {skala_m_per_px:.6f} m/px",
            20,
        )

        # 3. Simpan berkas koordinat CSV + JSON
        coord_dir = batch_folder / COORDINATE_DIR_NAME
        coord = write_coordinate_files(
            coord_dir, identity, vertices_px, crop_w, crop_h, luas_doc, area_px,
            crop_path=crop_path,
            method=self.candidates[self.selected_index].get("method", "opencv") if self.candidates else "manual",
            confidence=float(self.candidates[self.selected_index].get("confidence", 0.0)) if self.candidates else 0.0,
        )
        update_document(
            self.doc_id,
            koordinat_csv=coord["csv"],
            koordinat_json=coord["json"],
            scale_m_per_px=coord["scale_m_per_px"],
        )
        self._log(f"Koordinat tersimpan: {Path(coord['csv']).name}", 30)

        # 4. Siapkan DWG desa (satu file per desa, denah berjajar)
        if not self._ensure_autocad():
            self._log("Proses dibatalkan oleh operator.")
            return

        desa_raw = self.batch_data.get("nama_desa") or "Desa"
        desa_file = sanitize_filename(f"Desa {desa_raw}", ".dwg")
        desa_folder = HASIL_DIGITASI_DIR / Path(desa_file).stem
        desa_folder.mkdir(parents=True, exist_ok=True)
        dest = desa_folder / desa_file

        tpl = self._get_template_path()
        ok, msg, created = autocad_service.open_or_create_desa_drawing(
            str(dest), template_path=tpl
        )
        if not ok:
            raise RuntimeError(msg)
        self._log(msg, 40)

        # Dokumen yang pernah diproses ke DWG desa yang sama: hapus denah lama
        # di posisinya, lalu ganti dengan hasil terbaru.
        handles_old = {}
        try:
            handles_old = json.loads(self.doc_data.get("dwg_handles_json") or "{}")
        except Exception:
            handles_old = {}
        replace_bbox = None
        if handles_old and handles_old.get("dwg") == str(dest):
            poly_handle = str(handles_old.get("polyline") or "")
            if poly_handle:
                replace_bbox = autocad_service.get_entity_bbox(poly_handle)
            deleted, errors = autocad_service.delete_entities(handles_old)
            if deleted:
                self._log(f"Denah lama dihapus ({deleted} objek).", 42)
            if errors:
                self._log("Sebagian objek lama tidak bisa dihapus: " + "; ".join(errors), 42)
            # Bila polyline lama masih ada, jangan menimpa posisinya.
            if replace_bbox and poly_handle:
                if autocad_service.get_entity_bbox(poly_handle) is not None:
                    replace_bbox = None

        layout = autocad_service.get_desa_layout()
        slot = layout.get("next_slot") or {"x": 0.0, "y": 0.0, "row": 0, "column": 0}
        if replace_bbox:
            slot = {
                "x": replace_bbox[0],
                "y": replace_bbox[1],
                "row": int(handles_old.get("row", slot.get("row", 0))),
                "column": int(handles_old.get("column", slot.get("column", 0))),
            }
        self._log(
            f"Posisi denah: baris {int(slot.get('row', 0)) + 1}, "
            f"kolom {int(slot.get('column', 0)) + 1}.",
            44,
        )

        ok, msg = autocad_service.insert_raster_image(crop_path, insert_pt=(0.0, 0.0, 0.0), scale=1.0)
        if not ok:
            raise RuntimeError(msg)
        self._log(f"Denah disisipkan ke ModelSpace: {Path(crop_path).name}", 50)

        ok, handle, msg = autocad_service.create_polyline_from_vertices(
            vertices_px, image_width=crop_w, image_height=crop_h, closed=True
        )
        if not ok:
            raise RuntimeError(msg)
        self._log(f"{msg} Handle: {handle or '-'}", 58)

        # Pastikan raster denah tidak ikut hilang saat polyline dibuat.
        ok_raster, raster_msg = autocad_service.ensure_raster_attached()
        if not ok_raster:
            raise RuntimeError(raster_msg)
        self._log(f"{raster_msg} Denah tetap berada di bawah polyline.", 59)

        ok, initial_area, _, msg = autocad_service.get_polyline_area(handle=handle or None)
        if not ok:
            raise RuntimeError(msg)
        update_document(self.doc_id, luas_awal=initial_area)
        self._log(f"Luas awal polyline: {initial_area:,.2f} unit²", 65)

        analysis = analyze_scaling(luas_doc, initial_area)
        if not analysis.get("success"):
            raise RuntimeError(analysis.get("error", "Gagal menghitung faktor skala."))
        faktor = float(analysis["faktor_scaling_raw"])
        update_document(self.doc_id, faktor_scaling=faktor)
        self._log(f"Faktor skala otomatis: {faktor:.8f}", 70)

        ok, final_area, msg = autocad_service.scale_active_objects(
            faktor, base_point=(0.0, 0.0, 0.0), polyline_handle=handle or None
        )
        if not ok:
            raise RuntimeError(msg)
        self._log(f"{msg} Gambar denah dan polyline diskalakan bersama (raster + polyline).", 80)

        ok_raster, raster_msg = autocad_service.ensure_raster_attached()
        if not ok_raster:
            raise RuntimeError(raster_msg)

        # Koreksi otomatis bila toleransi belum tercapai
        for attempt in range(3):
            check = verify_final_area(luas_doc, final_area)
            if check.get("is_acceptable"):
                break
            koreksi = math.sqrt(luas_doc / final_area) if final_area > 0 else 1.0
            self._log(f"Koreksi otomatis ke-{attempt + 1}: faktor ×{koreksi:.8f}", 84)
            ok, final_area, msg = autocad_service.scale_active_objects(
                koreksi, base_point=(0.0, 0.0, 0.0), polyline_handle=handle or None
            )
            if not ok:
                raise RuntimeError(msg)

        evaluation = verify_final_area(luas_doc, final_area)
        update_document(self.doc_id, luas_akhir=final_area, status="MENUNGGU_VERIFIKASI")
        if not evaluation.get("is_acceptable"):
            raise RuntimeError(
                f"Luas akhir {final_area:.2f} m² masih di luar toleransi "
                f"({evaluation.get('persen_error', 0)}%). Periksa kualitas deteksi."
            )
        self._log(
            f"Verifikasi luas OK: {final_area:.2f} m² (selisih {evaluation['selisih']:.4f} m²)",
            88,
        )

        # 5. Geser denah (raster + polyline) ke slotnya di DWG desa.
        bbox = autocad_service.get_polyline_bbox(handle or "")
        if not bbox:
            raise RuntimeError("Batas polyline tidak terbaca untuk penempatan denah.")
        if slot.get("starts_new_row") and slot.get("row_top") is not None:
            # Baris baru: tempelkan sisi atas denah tepat di bawah baris lama.
            slot = {
                **slot,
                "y": float(slot["row_top"]) - (float(bbox[3]) - float(bbox[1])),
            }
        dx = float(slot["x"]) - bbox[0]
        dy = float(slot["y"]) - bbox[1]
        active_handles = autocad_service.get_active_handles()
        ok, msg = autocad_service.move_entities(active_handles, dx, dy)
        if not ok:
            raise RuntimeError(msg)
        bbox = (bbox[0] + dx, bbox[1] + dy, bbox[2] + dx, bbox[3] + dy)
        self._log(f"Denah ditempatkan di DWG desa: {msg}.", 90)

        # 6. Label 2 baris di tengah denah (pengganti blok data dokumen).
        label_line1, label_line2 = self._parcel_label_lines()
        center = ((bbox[0] + bbox[2]) / 2.0, (bbox[1] + bbox[3]) / 2.0)
        ok, label_handle, msg = autocad_service.add_parcel_label(
            [label_line1, label_line2],
            center=center,
            plot_w=bbox[2] - bbox[0],
            plot_h=bbox[3] - bbox[1],
        )
        if not ok:
            raise RuntimeError(msg)
        self._log(f"Label denah: {label_line1} / {label_line2}", 93)

        # 7. Simpan ke file DWG desa yang sama.
        ok, msg = autocad_service.save_drawing_as(str(dest), overwrite=True)
        if not ok:
            raise RuntimeError(msg)
        self._log(f"DWG desa tersimpan: {dest.name}", 96)

        handles_new = {
            **active_handles,
            "label": label_handle,
            "bbox": [round(float(v), 6) for v in bbox],
            "dwg": str(dest),
            "row": int(slot.get("row", 0)),
            "column": int(slot.get("column", 0)),
        }

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        update_document(
            self.doc_id,
            path_dwg=str(dest),
            status=STATUS_SELESAI,
            completed_at=now,
            is_auto_detected=1,
            dwg_handles_json=json.dumps(handles_new),
        )
        self.doc_data.update({
            "path_dwg": str(dest), "status": STATUS_SELESAI,
            "luas_awal": initial_area, "luas_akhir": final_area,
            "faktor_scaling": faktor,
            "dwg_handles_json": json.dumps(handles_new),
        })
        add_log(
            aktivitas="Digitasi Otomatis Selesai",
            detail=(
                f"{identity} | {len(vertices_px)} titik | luas {final_area:.2f} m² | "
                f"DWG desa {dest.name}"
            ),
            batch_id=self.doc_data.get("batch_id"),
            document_id=self.doc_id,
        )
        for idx in range(4):
            self.step_tracker.mark_completed(idx)
        self.status_badge.set_status(STATUS_SELESAI)
        self.progress.setValue(100)

        versi = autocad_service.version_string or "AutoCAD Desktop"
        self.lbl_done.setText(
            f"<b>{identity}</b><br><br>"
            f"• Status: SELESAI<br>"
            f"• Mode: AutoCAD Desktop ({versi})<br>"
            f"• Isi DWG: gambar denah + polyline terskala + label 2 baris<br>"
            f"• Posisi denah: baris {int(slot.get('row', 0)) + 1}, "
            f"kolom {int(slot.get('column', 0)) + 1}<br>"
            f"• Luas akhir: {final_area:.2f} m² (target {luas_doc:.2f} m²)<br>"
            f"• Faktor skala: {faktor:.6f}<br>"
            f"• DWG desa: {dest}<br>"
            f"• Koordinat CSV: {coord['csv']}<br>"
            f"• Koordinat JSON: {coord['json']}"
        )
        self.digitization_completed.emit(self.doc_id)
        self._go_to_step(3)
        QMessageBox.information(
            self, "Digitasi Selesai",
            f"{identity} berhasil diproses otomatis.\n\n"
            f"Denah ditambahkan ke DWG desa:\n{dest.name}\n\n"
            "Berkas koordinat juga telah disimpan.",
        )

    def _open_result_folder(self):
        path = Path(self.doc_data.get("path_dwg") or "")
        folder = path.parent if path else HASIL_DIGITASI_DIR
        if folder.exists():
            os.startfile(str(folder))
        else:
            QMessageBox.information(self, "Folder Belum Ada", f"Folder belum tersedia:\n{folder}")
