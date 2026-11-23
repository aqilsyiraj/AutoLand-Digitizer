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

import numpy as np
from PIL import Image
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
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
    suggest_denah_page,
    write_coordinate_files,
)
from services.geometry_service import analyze_scaling, verify_final_area
from services.naming_service import (
    format_document_identity, normalize_gs_number, sanitize_filename,
    validate_document_input,
)
from services.pdf_service import (
    crop_pdf_region_to_file, get_pdf_info, render_pdf_page_to_pixmap,
)
from ui.components.crop_canvas import InteractiveCropCanvas
from ui.components.guide_banner import GuideBanner
from ui.components.form_field import FormField
from ui.components.status_badge import StatusBadge
from ui.components.step_tracker import StepTracker


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
        self.crop_path: str = ""
        self.processing = False

        self._setup_ui()

    # =================================================================
    # UI
    # =================================================================
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 8, 14, 12)
        layout.setSpacing(6)

        header = QFrame()
        header.setObjectName("SectionCard")
        h = QHBoxLayout(header)
        h.setContentsMargins(12, 8, 12, 8)
        h.setSpacing(8)

        self.btn_back = QPushButton("Antrean")
        self.btn_back.setProperty("class", "btn-secondary")
        self.btn_back.setToolTip("Kembali ke daftar dokumen tanpa memproses lebih lanjut")
        self.btn_back.clicked.connect(self.back_to_queue.emit)
        h.addWidget(self.btn_back)

        info = QVBoxLayout()
        info.setSpacing(2)
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
        h.addWidget(self.status_badge)
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

        self._set_step_enabled(0)

    # ---------- Langkah 1: halaman + deteksi otomatis ----------
    def _create_step_page(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        layout.addWidget(GuideBanner("Langkah 1 — Pilih Halaman Denah", [
            "Aplikasi otomatis memilih halaman yang paling mungkin berisi <b>Gambar Situasi</b>. Anda bisa menggantinya.",
            "Polyline batas bidang langsung <b>terdeteksi otomatis</b> dan digambar dengan garis hijau di atas denah.",
            "Jika hasil kurang tepat, <b>geser titik hijau</b>, klik 2x pada garis untuk menambah titik, atau klik kanan titik untuk menghapus.",
        ]))

        content = QHBoxLayout()
        content.setSpacing(8)

        panel = QFrame()
        panel.setObjectName("SectionCard")
        panel.setFixedWidth(252)
        p = QVBoxLayout(panel)
        p.setContentsMargins(12, 10, 12, 10)
        p.setSpacing(8)

        self.combo_page = QComboBox()
        self.combo_page.currentIndexChanged.connect(self._on_page_changed)
        p.addWidget(FormField(
            "Halaman PDF",
            "Saran otomatis. Ganti bila perlu.",
            self.combo_page,
        ))

        self.btn_detect_again = QPushButton("Deteksi Ulang")
        self.btn_detect_again.setProperty("class", "btn-secondary")
        self.btn_detect_again.setToolTip("Jalankan kembali deteksi polyline pada halaman yang sedang dipilih")
        self.btn_detect_again.clicked.connect(self._redetect_current_page)
        p.addWidget(self.btn_detect_again)

        self.combo_candidate = QComboBox()
        self.combo_candidate.currentIndexChanged.connect(self._on_candidate_changed)
        p.addWidget(FormField(
            "Kandidat Polyline",
            "Pilih batas bidang yang tepat.",
            self.combo_candidate,
        ))

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
        self.btn_use_polyline = QPushButton("Gunakan Polyline →")
        self.btn_use_polyline.setProperty("class", "btn-primary")
        self.btn_use_polyline.setEnabled(False)
        self.btn_use_polyline.clicked.connect(self._accept_polyline)
        p.addWidget(self.btn_use_polyline)
        content.addWidget(panel)

        self.canvas = InteractiveCropCanvas()
        self.canvas.confirmed.connect(self._on_manual_crop_confirmed)
        self.canvas.polyline_changed.connect(self._on_polyline_edited)
        content.addWidget(self.canvas, 1)

        layout.addLayout(content, 1)
        return widget

    # ---------- Langkah 2: koreksi final + data dokumen ----------
    def _create_review_page(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        layout.addWidget(GuideBanner("Langkah 2 — Periksa Polyline & Isi Data Dokumen", [
            "Polyline sudah disetujui pada Langkah 1. Jika perlu mengoreksi, klik <b>← Kembali</b> dan geser titiknya.",
            "Isi <b>Jenis Hak, Nomor Hak, Nomor GS, Tahun</b>, dan <b>Luas Dokumen (m²)</b>. Nilai GS/Tahun/Luas sudah diisi otomatis dari PDF bila terbaca — tetap periksa kembali.",
            "Teks merah menunjukkan data yang belum lengkap dan harus diperbaiki sebelum diproses.",
        ]))

        card = QFrame()
        card.setObjectName("SectionCard")
        c = QVBoxLayout(card)
        c.setContentsMargins(12, 10, 12, 10)
        c.setSpacing(8)

        self.lbl_review_summary = QLabel("Ringkasan deteksi akan tampil di sini.")
        self.lbl_review_summary.setObjectName("ReviewSummary")
        self.lbl_review_summary.setWordWrap(True)
        c.addWidget(self.lbl_review_summary)

        fields_row = QHBoxLayout()
        fields_row.setSpacing(10)

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
        grid.addWidget(FormField(
            "Jenis Hak", "Sesuai sertifikat.",
            self.combo_hak, required=True,
        ), 0, 0)

        self.input_no_hak = QLineEdit()
        self.input_no_hak.setPlaceholderText("1342")
        self.input_no_hak.textChanged.connect(self._update_identity_preview)
        grid.addWidget(FormField(
            "Nomor Hak", "Angka nomor sertifikat.",
            self.input_no_hak, required=True,
        ), 0, 1)

        self.input_no_gs = QLineEdit()
        self.input_no_gs.setPlaceholderText("176")
        self.input_no_gs.textChanged.connect(self._update_identity_preview)
        grid.addWidget(FormField(
            "Nomor GS", "Nomor GS buku tanah.",
            self.input_no_gs, required=True,
        ), 0, 2)

        self.input_tahun = QLineEdit()
        self.input_tahun.setPlaceholderText("1969")
        self.input_tahun.textChanged.connect(self._update_identity_preview)
        grid.addWidget(FormField(
            "Tahun Sertifikat", "Tahun terbit hak.",
            self.input_tahun, required=True,
        ), 0, 3)

        self.input_luas = QDoubleSpinBox()
        self.input_luas.setRange(0.01, 10_000_000.0)
        self.input_luas.setDecimals(2)
        self.input_luas.setSuffix(" m²")
        self.input_luas.valueChanged.connect(self._update_identity_preview)
        grid.addWidget(FormField(
            "Luas Dokumen", "Target skala DWG (m²).",
            self.input_luas, required=True,
        ), 0, 4)

        preview = QFrame()
        preview.setObjectName("IdentityPreview")
        preview.setFixedWidth(220)
        pv = QVBoxLayout(preview)
        pv.setContentsMargins(10, 8, 10, 8)
        pv.setSpacing(3)
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
        nav.setSpacing(8)
        btn_prev = QPushButton("← Deteksi")
        btn_prev.setProperty("class", "btn-secondary")
        btn_prev.setToolTip("Kembali ke langkah 1 untuk mengoreksi polyline")
        btn_prev.clicked.connect(lambda: self._go_to_step(0))
        nav.addWidget(btn_prev)
        nav.addStretch()
        self.btn_save_data = QPushButton("Simpan & Lanjut →")
        self.btn_save_data.setProperty("class", "btn-primary")
        self.btn_save_data.setEnabled(False)
        self.btn_save_data.setToolTip("Simpan identitas dokumen lalu lanjut ke proses otomatis")
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

        layout.addWidget(GuideBanner("Langkah 3 — Proses Otomatis", [
            "Tekan satu tombol di bawah. Aplikasi akan memotong denah, memasukkan <b>gambar denah ke DWG</b>, membuat polyline di atasnya, menghitung & menerapkan skala, lalu menulis <b>data dokumen</b> di atas gambar.",
            "Anda <b>tidak perlu</b> membuka AutoCAD atau menggambar polyline secara manual.",
            "Hasil akhir di AutoCAD berisi: denah raster, polyline batas yang sudah diskalakan, dan blok data dokumen (identitas, hak, GS, tahun, luas, desa).",
        ]))

        card = QFrame()
        card.setObjectName("SectionCard")
        c = QVBoxLayout(card)
        c.setContentsMargins(12, 10, 12, 10)
        c.setSpacing(8)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        c.addWidget(self.progress)

        self.log_view = QTextEdit()
        self.log_view.setObjectName("ProcessLog")
        self.log_view.setReadOnly(True)
        self.log_view.setMinimumHeight(180)
        c.addWidget(self.log_view)

        nav = QHBoxLayout()
        nav.setSpacing(8)
        btn_prev = QPushButton("← Data")
        btn_prev.setProperty("class", "btn-secondary")
        btn_prev.setToolTip("Kembali ke langkah 2 untuk mengubah data dokumen")
        btn_prev.clicked.connect(lambda: self._go_to_step(1))
        nav.addWidget(btn_prev)
        nav.addStretch()
        self.btn_run = QPushButton("Jalankan Proses")
        self.btn_run.setProperty("class", "btn-primary")
        self.btn_run.setMinimumHeight(40)
        self.btn_run.setToolTip("Buat DWG berisi denah, polyline terskala, dan data dokumen")
        self.btn_run.clicked.connect(self._run_auto_process)
        nav.addWidget(self.btn_run)
        c.addLayout(nav)

        layout.addWidget(card)
        return widget

    # ---------- Langkah 4: hasil ----------
    def _create_done_page(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        card = QFrame()
        card.setObjectName("DoneCard")
        c = QVBoxLayout(card)
        c.setContentsMargins(18, 14, 18, 14)
        c.setSpacing(8)

        title = QLabel("Digitasi Selesai")
        title.setObjectName("DoneTitle")
        c.addWidget(title)

        self.lbl_done = QLabel("")
        self.lbl_done.setObjectName("DoneBody")
        self.lbl_done.setWordWrap(True)
        c.addWidget(self.lbl_done)

        nav = QHBoxLayout()
        self.btn_open_folder = QPushButton("📂 Buka Folder Hasil")
        self.btn_open_folder.setProperty("class", "btn-secondary")
        self.btn_open_folder.clicked.connect(self._open_result_folder)
        nav.addWidget(self.btn_open_folder)
        self.btn_done_back = QPushButton("Kembali ke Antrean")
        self.btn_done_back.setProperty("class", "btn-primary")
        self.btn_done_back.clicked.connect(self.back_to_queue.emit)
        nav.addWidget(self.btn_done_back)
        c.addLayout(nav)

        layout.addWidget(card)
        layout.addStretch()
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
        self.crop_path = ""
        self.processing = False
        self.canvas.clear_polyline()
        self.log_view.clear()
        self.progress.setValue(0)
        self._set_detection_status("Menunggu PDF dibuka…")
        self.lbl_detection_info.setText("Belum ada polyline.")
        self.combo_candidate.clear()
        self.btn_use_polyline.setEnabled(False)

    def load_document(self, doc_id: int):
        self._reset_state()
        self.doc_id = doc_id
        self.doc_data = get_document(doc_id) or {}
        if not self.doc_data:
            return

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
        page = self.combo_page.currentData()
        if page:
            self._detect_page(int(page))

    def _redetect_current_page(self):
        page = self.combo_page.currentData()
        if page:
            self._detect_page(int(page))

    def _load_page_preview(self, pdf_path: str, page_number: int):
        preview = render_pdf_page_to_pixmap(pdf_path, page_number, dpi=DETECTION_PREVIEW_DPI)
        if preview:
            self.canvas.load_page_image(preview)

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

        self._set_detection_status(f"Mendeteksi polyline pada halaman {page_number}…")
        QApplication.processEvents()

        if self.doc_id:
            update_document(self.doc_id, halaman_pdf=page_number)

        self._load_page_preview(pdf_path, page_number)

        result = detect_on_page(pdf_path, page_number, dpi=DETECTION_DPI)
        self.detection_meta = {
            "page": page_number,
            "image_width": result.get("image_width", 0),
            "image_height": result.get("image_height", 0),
            "dpi": result.get("dpi", DETECTION_DPI),
        }
        self.candidates = result.get("candidates", [])

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
            self._update_detection_info()

    def _show_candidate(self, index: int):
        if not (0 <= index < len(self.candidates)):
            return
        self.selected_index = index
        cand = self.candidates[index]
        self.polyline_normalized = [tuple(p) for p in cand.get("vertices_normalized", [])]
        self.crop_box = tuple(cand.get("crop_box_normalized") or ())
        self.canvas.show_polyline(self.polyline_normalized)
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
            f"Luas citra: <b>{area:,.0f} px²</b>\n\n"
            "Geser titik hijau bila perlu, lalu klik 'Gunakan Polyline Ini'."
        )

    def _on_manual_crop_confirmed(self, norm_box: tuple):
        """Fallback: operator menentukan area denah dengan mouse, lalu sistem mendeteksi di dalamnya."""
        pdf_path = self.doc_data.get("path_pdf", "")
        page = self.combo_page.currentData() or 1
        name = f"manual_{uuid.uuid4().hex[:8]}.png"
        ok, path = crop_pdf_region_to_file(pdf_path, int(page), norm_box, name, dpi=DETECTION_DPI)
        if not ok:
            QMessageBox.critical(self, "Gagal Memotong", path)
            return
        try:
            image = Image.open(path).convert("RGB")
            array = np.asarray(image)
        except Exception as exc:
            QMessageBox.critical(self, "Gagal Membaca Gambar", str(exc))
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
            QMessageBox.warning(
                self, "Deteksi Gagal",
                "Polyline tidak ditemukan pada area yang dipilih. Coba area lain atau halaman lain."
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
            f"halaman <b>{self.detection_meta.get('page', '-')}</b>. "
            "Geser titik di Langkah 1 bila perlu koreksi."
        )
        self._go_to_step(1)

    # =================================================================
    # DATA DOKUMEN
    # =================================================================
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
        self._log(f"Polyline {len(vertices_px)} titik • luas citra {area_px:,.0f} px²", 20)

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

        # 4. AutoCAD otomatis
        if not self._ensure_autocad():
            self._log("Proses dibatalkan oleh operator.")
            return

        tpl = self._get_template_path()
        if tpl:
            ok, msg = autocad_service.open_template(tpl)
            if not ok:
                raise RuntimeError(msg)
            self._log(f"Template dibuka: {Path(tpl).name}", 40)
        else:
            ok, msg = autocad_service.create_new_drawing()
            if not ok:
                raise RuntimeError(msg)
            self._log("Template belum tersedia; DWG baru dibuat otomatis di AutoCAD.", 40)

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
        self._log(msg, 80)

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

        kode_hak = str(self.doc_data.get("kode_hak") or "")
        jenis_hak = (
            self.doc_data.get("jenis_hak")
            or JENIS_HAK_MAP.get(kode_hak, {}).get("label", "-")
        )
        desa = self.batch_data.get("nama_desa") or "-"
        kecamatan = self.batch_data.get("kecamatan") or "-"
        kabupaten = self.batch_data.get("kabupaten") or "-"
        tanggal = self.batch_data.get("tanggal") or "-"
        operator = self.batch_data.get("operator") or "-"

        info_lines = [
            f"Identitas: {identity}",
            f"Jenis Hak: {jenis_hak}",
            f"Nomor Hak: {self.doc_data.get('nomor_hak') or '-'}",
            f"Nomor GS: {self.doc_data.get('nomor_gs') or '-'}",
            f"Tahun: {self.doc_data.get('tahun') or '-'}",
            f"Luas Dokumen: {luas_doc:.2f} m²",
            f"Luas DWG Terskala: {final_area:.2f} m²",
            f"Lokasi: Desa {desa}, Kec. {kecamatan}, Kab. {kabupaten}",
            f"Batch: #{self.doc_data.get('batch_id', '-')} | Tanggal: {tanggal}",
            f"Operator: {operator}",
        ]

        ok, msg = autocad_service.set_identity_text(identity)
        if not ok:
            raise RuntimeError(msg)
        self._log("Teks identitas diperbarui otomatis.", 92)

        ok, msg = autocad_service.add_document_info_block(info_lines)
        if not ok:
            raise RuntimeError(msg)
        self._log(f"{msg} Denah + polyline terskala + data dokumen aktif di DWG.", 94)

        safe_name = sanitize_filename(identity, ".dwg")
        dest = batch_folder / safe_name
        overwrite = False
        if dest.exists():
            reply = QMessageBox.question(
                self, "Timpa File DWG",
                f"File {safe_name} sudah ada. Timpa dengan hasil terbaru?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                self._log("Penyimpanan dibatalkan oleh operator.")
                return
            overwrite = True

        ok, msg = autocad_service.save_drawing_as(str(dest), overwrite=overwrite)
        if not ok:
            raise RuntimeError(msg)
        self._log(f"DWG tersimpan: {dest.name}", 96)

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        update_document(
            self.doc_id,
            path_dwg=str(dest),
            status=STATUS_SELESAI,
            completed_at=now,
            is_auto_detected=1,
        )
        self.doc_data.update({
            "path_dwg": str(dest), "status": STATUS_SELESAI,
            "luas_awal": initial_area, "luas_akhir": final_area,
            "faktor_scaling": faktor,
        })
        add_log(
            aktivitas="Digitasi Otomatis Selesai",
            detail=f"{identity} | {len(vertices_px)} titik | luas {final_area:.2f} m² | {dest.name}",
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
            f"• Isi DWG: gambar denah + polyline terskala + data dokumen<br>"
            f"• Luas akhir: {final_area:.2f} m² (target {luas_doc:.2f} m²)<br>"
            f"• Faktor skala: {faktor:.6f}<br>"
            f"• DWG: {dest}<br>"
            f"• Koordinat CSV: {coord['csv']}<br>"
            f"• Koordinat JSON: {coord['json']}"
        )
        self.digitization_completed.emit(self.doc_id)
        self._go_to_step(3)
        QMessageBox.information(
            self, "Digitasi Selesai",
            f"{identity} berhasil diproses otomatis.\n\nFile DWG dan koordinat telah disimpan.",
        )

    def _open_result_folder(self):
        path = Path(self.doc_data.get("path_dwg") or "")
        folder = path.parent if path else HASIL_DIGITASI_DIR
        if folder.exists():
            os.startfile(str(folder))
        else:
            QMessageBox.information(self, "Folder Belum Ada", f"Folder belum tersedia:\n{folder}")
