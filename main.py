"""
AutoLand Digitizer - Main Entry Point
Aplikasi Desktop Windows untuk Otomatisasi Digitalisasi Dokumen Pertanahan.
"""

import os
import sys
import traceback
from pathlib import Path

# Setup DPI dan atribut Qt sebelum instance QApplication
os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"

from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from config import (
    APP_NAME, APP_VERSION, LOG_FILE_PATH,
    ensure_directories
)
from database.db import init_db, add_log
from app.main_window import MainWindow

def handle_exception(exc_type, exc_value, exc_traceback):
    """Menangani unhandled exception secara global agar tercatat di log."""
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    err_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    try:
        ensure_directories()
        with open(LOG_FILE_PATH, "a", encoding="utf-8") as f:
            f.write(f"\n[CRITICAL ERROR] {err_msg}\n")
    except Exception:
        pass

    print(f"[CRITICAL ERROR] {err_msg}", file=sys.stderr)

    # Tampilkan pesan jika antarmuka GUI aktif
    if QApplication.instance():
        QMessageBox.critical(
            None,
            "Kesalahan Tak Terduga",
            f"Terjadi kesalahan pada aplikasi:\n{str(exc_value)}\n\nRincian telah disimpan di log."
        )

def main():
    sys.excepthook = handle_exception

    # 1. Pastikan folder-folder lokal tersedia
    ensure_directories()

    # 2. Inisialisasi Database SQLite Lokal
    init_db()

    # 3. Jalankan Aplikasi PySide6
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    # Fusion membuat QSS tampil konsisten di semua versi Windows, dan font
    # tunggal "Segoe UI" menghindari fallback glyph yang salah.
    app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI", 9))

    window = MainWindow()
    window.show()

    add_log(aktivitas="Aplikasi Dibuka", detail=f"{APP_NAME} versi {APP_VERSION} dijalankan.")

    exit_code = app.exec()

    add_log(aktivitas="Aplikasi Ditutup", detail=f"{APP_NAME} selesai ditutup (kode: {exit_code}).")
    sys.exit(exit_code)

if __name__ == "__main__":
    main()
