"""Tabel aplikasi dengan pesan keadaan kosong dan kontrol kolom yang terukur."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter
from PySide6.QtWidgets import QHeaderView, QTableWidget


class DataTable(QTableWidget):
    """QTableWidget yang tidak pernah terlihat kosong tanpa penjelasan."""

    def __init__(self, columns: int, parent=None):
        super().__init__(0, columns, parent)
        self.setObjectName("DataTable")
        self._empty_text = "Belum ada data yang ditampilkan."
        self.setAlternatingRowColors(True)
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(42)
        self.setSelectionBehavior(QTableWidget.SelectRows)
        self.setEditTriggers(QTableWidget.NoEditTriggers)
        self.setShowGrid(False)
        self.setMouseTracking(True)

    def set_empty_text(self, text: str) -> None:
        self._empty_text = text
        self.viewport().update()

    def set_columns(self, widths: list[int], stretch_column: int | None = None,
                    minimum_widths: list[int] | None = None) -> None:
        """Atur lebar kolom tetap dan satu kolom yang mengisi sisa ruang."""
        header = self.horizontalHeader()
        for idx, width in enumerate(widths):
            if idx == stretch_column:
                header.setSectionResizeMode(idx, QHeaderView.Stretch)
            else:
                header.setSectionResizeMode(idx, QHeaderView.Fixed)
                self.setColumnWidth(idx, width)
                if minimum_widths and idx < len(minimum_widths):
                    self.setColumnWidth(idx, max(width, minimum_widths[idx]))
        header.setStretchLastSection(False)

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.rowCount() > 0 or not self._empty_text:
            return

        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.viewport().rect()
        painter.fillRect(rect, QColor("#FFFFFF"))

        font = QFont("Segoe UI", 13)
        font.setBold(True)
        painter.setFont(font)
        metrics = QFontMetrics(font)
        text = metrics.elidedText(self._empty_text, Qt.ElideRight, rect.width() - 48)
        painter.setPen(QColor("#64748B"))
        painter.drawText(rect.adjusted(24, 0, -24, 0), Qt.AlignCenter, text)
        painter.end()
