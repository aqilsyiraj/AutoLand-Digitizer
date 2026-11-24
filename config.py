"""
AutoLand Digitizer - Configuration Module
Mengatur path direktori, konstanta sistem, pemetaan jenis hak, dan konfigurasi database.
Mendukung eksekusi mandiri (source code) dan paket terkompilasi (PyInstaller).
"""

import os
import sys
from pathlib import Path

# Mendeteksi apakah aplikasi berjalan dalam bundle PyInstaller
if getattr(sys, 'frozen', False):
    # Mode eksekusi (.exe)
    BASE_DIR = Path(sys.executable).resolve().parent
    BUNDLE_DIR = Path(getattr(sys, '_MEIPASS', BASE_DIR))
else:
    # Mode pengembangan Python script
    BASE_DIR = Path(__file__).resolve().parent
    BUNDLE_DIR = BASE_DIR

# Nama dan Versi Aplikasi
APP_NAME = "AutoLand Digitizer"
APP_VERSION = "1.0.0"
APP_SUBTITLE = "Aplikasi Pengelolaan & Otomatisasi Digitalisasi Dokumen Pertanahan"

# Folder Penyimpanan Lokal
DATA_DIR = BASE_DIR / "data"
DOKUMEN_MASUK_DIR = BASE_DIR / "dokumen_masuk"
TEMPORARY_DIR = BASE_DIR / "temporary"
HASIL_DIGITASI_DIR = BASE_DIR / "hasil_digitasi"
BACKUP_DIR = BASE_DIR / "backup"
LOGS_DIR = BASE_DIR / "logs"
TEMPLATE_DIR = BASE_DIR / "template"

# File Path Standar
DB_PATH = DATA_DIR / "autoland.db"
DEFAULT_TEMPLATE_PATH = TEMPLATE_DIR / "template.dwg"
LOG_FILE_PATH = LOGS_DIR / "autoland_activity.log"

# Status Pekerjaan
STATUS_MENUNGGU = "MENUNGGU"
STATUS_PDF_DIPROSES = "PDF DIPROSES"
STATUS_TERDETEKSI = "TERDETEKSI"
STATUS_MENUNGGU_TRACING = "MENUNGGU TRACING"
STATUS_MENUNGGU_SCALING = "MENUNGGU SCALING"
STATUS_MENUNGGU_VERIFIKASI = "MENUNGGU VERIFIKASI"
STATUS_SELESAI = "SELESAI"
STATUS_GAGAL = "GAGAL"

STATUS_LIST = [
    STATUS_MENUNGGU,
    STATUS_PDF_DIPROSES,
    STATUS_TERDETEKSI,
    STATUS_MENUNGGU_TRACING,
    STATUS_MENUNGGU_SCALING,
    STATUS_MENUNGGU_VERIFIKASI,
    STATUS_SELESAI,
    STATUS_GAGAL,
]

# Label status yang ditampilkan ke operator (kode internal tetap dipakai di database)
STATUS_LABELS = {
    STATUS_MENUNGGU: "Menunggu",
    STATUS_PDF_DIPROSES: "Dipotong",
    STATUS_TERDETEKSI: "Terdeteksi",
    STATUS_MENUNGGU_TRACING: "Siap Proses",
    STATUS_MENUNGGU_SCALING: "Skala",
    STATUS_MENUNGGU_VERIFIKASI: "Verifikasi",
    STATUS_SELESAI: "Selesai",
    STATUS_GAGAL: "Gagal",
}

# Pengaturan deteksi polyline otomatis (offline computer vision)
DETECTION_DPI = 200              # DPI standar untuk analisis gambar denah
DETECTION_SCAN_DPI = 100         # DPI lebih rendah untuk pemindaian deteksi otomatis
DETECTION_PREVIEW_DPI = DETECTION_SCAN_DPI  # preview berkongsi render dengan deteksi
DETECTION_CROP_DPI = 300         # DPI untuk denah hasil potongan
DETECTION_MIN_CONFIDENCE = 0.25  # Ambang batas kandidat diterima (dilebarkan untuk skan variatif)
DETECTION_MAX_CANDIDATES = 5     # Maksimal kandidat yang ditampilkan
DETECTION_MIN_AREA_RATIO = 0.005  # Luas minima kandidat terhadap luas halaman (dilebarkan)
DETECTION_MAX_AREA_RATIO = 0.90  # Luas maksima kandidat terhadap luas halaman (dilebarkan)
DETECTION_EPS_FACTOR = 0.012     # Faktor penyederhanaan garis (approxPolyDP)
COORDINATE_DIR_NAME = "koordinat"

# Tata letak DWG desa: satu file per desa, denah berjajar maksimal 10 kolom
# lalu turun ke baris berikutnya mulai dari bawah denah pertama.
DWG_MAX_COLUMNS = 10
DWG_PLOT_GAP_RATIO = 0.10       # jarak antar denah = 10% lebar denah
DWG_PLOT_MIN_GAP = 5.0          # jarak minimum antar denah (satuan gambar)
DWG_LABEL_HEIGHT_RATIO = 0.06   # tinggi huruf label = 6% tinggi denah
DWG_LABEL_MAX_WIDTH_RATIO = 0.80  # label maksimal 80% lebar denah

# Pemetaan Jenis Hak Pertanahan Indonesia
# Kode jenis hak -> (Awalan, Label Lengkap)
JENIS_HAK_MAP = {
    "1": {"awalan": "M.", "label": "Hak Milik (M.)", "kode": "1"},
    "3": {"awalan": "B.", "label": "Hak Guna Bangunan (B.)", "kode": "3"},
    "4": {"awalan": "P.", "label": "Hak Pakai (P.)", "kode": "4"},
    "8": {"awalan": "W.", "label": "Wakaf (W.)", "kode": "8"},
}

# Awalan ke Kode Hak
AWALAN_KE_KODE = {
    "M.": "1",
    "B.": "3",
    "P.": "4",
    "W.": "8",
}

# Warna Tema UI
THEME_COLORS = {
    "primary": "#1E40AF",       # Deep Blue
    "primary_hover": "#1D4ED8",
    "primary_light": "#DBEAFE",
    "secondary": "#0D9488",     # Teal
    "accent": "#F59E0B",        # Amber
    "success": "#10B981",       # Emerald
    "danger": "#EF4444",        # Rose/Red
    "warning": "#F59E0B",
    "info": "#3B82F6",
    "bg_main": "#F8FAFC",       # Slate 50
    "bg_card": "#FFFFFF",
    "bg_sidebar": "#0F172A",    # Slate 900
    "text_dark": "#0F172A",
    "text_muted": "#64748B",
    "text_light": "#F8FAFC",
    "border": "#E2E8F0",
}

def ensure_directories():
    """Memastikan seluruh direktori lokal yang diperlukan telah tersedia."""
    dirs = [
        DATA_DIR,
        DOKUMEN_MASUK_DIR,
        TEMPORARY_DIR,
        HASIL_DIGITASI_DIR,
        BACKUP_DIR,
        LOGS_DIR,
        TEMPLATE_DIR,
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
