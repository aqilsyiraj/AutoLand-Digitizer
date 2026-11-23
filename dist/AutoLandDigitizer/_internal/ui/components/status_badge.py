"""
AutoLand Digitizer - Status Badge Component
Menampilkan status pekerjaan dalam bentuk pill badge dengan warna representatif.
"""

from PySide6.QtWidgets import QLabel
from PySide6.QtCore import Qt
from config import (
    STATUS_MENUNGGU,
    STATUS_PDF_DIPROSES,
    STATUS_MENUNGGU_TRACING,
    STATUS_MENUNGGU_SCALING,
    STATUS_MENUNGGU_VERIFIKASI,
    STATUS_SELESAI,
    STATUS_GAGAL,
)

STATUS_STYLES = {
    STATUS_MENUNGGU: {
        "bg": "#F1F5F9",
        "color": "#475569",
        "border": "#CBD5E1",
    },
    STATUS_PDF_DIPROSES: {
        "bg": "#EFF6FF",
        "color": "#1D4ED8",
        "border": "#BFDBFE",
    },
    STATUS_MENUNGGU_TRACING: {
        "bg": "#F5F3FF",
        "color": "#6D28D9",
        "border": "#DDD6FE",
    },
    STATUS_MENUNGGU_SCALING: {
        "bg": "#FEF3C7",
        "color": "#B45309",
        "border": "#FDE68A",
    },
    STATUS_MENUNGGU_VERIFIKASI: {
        "bg": "#ECFEFF",
        "color": "#0E7490",
        "border": "#A5F3FC",
    },
    STATUS_SELESAI: {
        "bg": "#ECFDF5",
        "color": "#047857",
        "border": "#A7F3D0",
    },
    STATUS_GAGAL: {
        "bg": "#FEF2F2",
        "color": "#B91C1C",
        "border": "#FECACA",
    },
}

class StatusBadge(QLabel):
    def __init__(self, status: str = STATUS_MENUNGGU, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.set_status(status)

    def set_status(self, status: str):
        self.setText(status)
        style_info = STATUS_STYLES.get(status, STATUS_STYLES[STATUS_MENUNGGU])
        self.setStyleSheet(f"""
            QLabel {{
                background-color: {style_info['bg']};
                color: {style_info['color']};
                border: 1px solid {style_info['border']};
                border-radius: 11px;
                padding: 3px 10px;
                font-size: 11px;
                font-weight: 700;
            }}
        """)
