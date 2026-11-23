"""Status pekerjaan dalam bentuk pill yang memakai warna sistem desain."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel

from config import (
    STATUS_LABELS,
    STATUS_MENUNGGU,
    STATUS_PDF_DIPROSES,
    STATUS_TERDETEKSI,
    STATUS_MENUNGGU_TRACING,
    STATUS_MENUNGGU_SCALING,
    STATUS_MENUNGGU_VERIFIKASI,
    STATUS_SELESAI,
    STATUS_GAGAL,
)

STATUS_TONES = {
    STATUS_MENUNGGU: "neutral",
    STATUS_PDF_DIPROSES: "info",
    STATUS_TERDETEKSI: "success",
    STATUS_MENUNGGU_TRACING: "info",
    STATUS_MENUNGGU_SCALING: "warn",
    STATUS_MENUNGGU_VERIFIKASI: "brand",
    STATUS_SELESAI: "success",
    STATUS_GAGAL: "danger",
}


class StatusBadge(QLabel):
    def __init__(self, status: str = STATUS_MENUNGGU, parent=None):
        super().__init__(parent)
        self.setObjectName("StatusPill")
        self.setAlignment(Qt.AlignCenter)
        self.set_status(status)

    def set_status(self, status: str):
        label = STATUS_LABELS.get(status, status)
        self.setText(label)
        self.setToolTip(f"{label} — kode internal: {status}")
        self.setProperty("tone", STATUS_TONES.get(status, "neutral"))
        self.style().unpolish(self)
        self.style().polish(self)
