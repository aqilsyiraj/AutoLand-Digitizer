"""Tabel data yang rapat, dengan aksi baris yang tidak pernah terpotong."""

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QSizePolicy,
    QTableWidget,
    QWidget,
)

from ui.components.button import Button


class DataTable(QTableWidget):
    """QTableWidget dengan pesan keadaan kosong yang informatif."""

    def __init__(self, columns: int, parent=None):
        super().__init__(0, columns, parent)
        self.setObjectName("DataTable")
        self._empty_text = "Belum ada data yang ditampilkan."
        self.setAlternatingRowColors(True)
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(38)
        self.setSelectionBehavior(QTableWidget.SelectRows)
        self.setEditTriggers(QTableWidget.NoEditTriggers)
        self.setShowGrid(False)
        self.setMouseTracking(True)
        self.setWordWrap(False)
        self.setFocusPolicy(Qt.StrongFocus)

    def set_empty_text(self, text: str) -> None:
        self._empty_text = text
        self.viewport().update()

    def set_columns(
        self,
        widths: list[int],
        stretch_column: int | None = None,
        minimum_widths: list[int] | None = None,
    ) -> None:
        """Atur lebar kolom tetap dan satu kolom yang mengisi sisa ruang."""
        header = self.horizontalHeader()
        for idx, width in enumerate(widths):
            if idx == stretch_column:
                header.setSectionResizeMode(idx, QHeaderView.Stretch)
            else:
                header.setSectionResizeMode(idx, QHeaderView.Fixed)
                fixed = width
                if minimum_widths and idx < len(minimum_widths):
                    fixed = max(width, minimum_widths[idx])
                self.setColumnWidth(idx, fixed)
        header.setStretchLastSection(False)

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.rowCount() > 0 or not self._empty_text:
            return

        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.viewport().rect()
        painter.fillRect(rect, QColor("#FFFFFF"))

        center_x = rect.center().x()
        has_room = rect.height() > 150

        text_top = rect.center().y() - 10
        if has_room:
            icon = QRectF(center_x - 22, rect.center().y() - 62, 44, 44)
            painter.setPen(QPen(QColor("#DCE4EC"), 1))
            painter.setBrush(QColor("#F7F9FB"))
            painter.drawRoundedRect(icon, 11, 11)
            painter.setPen(QPen(QColor("#B7C4D3"), 2))
            for offset in (-8, 0, 8):
                painter.drawLine(
                    int(center_x - 11), int(icon.center().y() + offset),
                    int(center_x + 11), int(icon.center().y() + offset),
                )
            text_top = rect.center().y() + 4

        font = QFont("Segoe UI", 10)
        font.setBold(True)
        painter.setFont(font)
        metrics = QFontMetrics(font)
        text = metrics.elidedText(self._empty_text, Qt.ElideRight, rect.width() - 80)
        painter.setPen(QColor("#64748B"))
        painter.drawText(
            QRectF(rect.left() + 30, text_top, rect.width() - 60, 24),
            Qt.AlignHCenter | Qt.AlignTop,
            text,
        )

        hint = "Data akan muncul di sini setelah ditambahkan."
        hint_font = QFont("Segoe UI", 9)
        painter.setFont(hint_font)
        painter.setPen(QColor("#94A3B8"))
        painter.drawText(
            QRectF(rect.left() + 30, text_top + 22, rect.width() - 60, 22),
            Qt.AlignHCenter | Qt.AlignTop,
            hint,
        )
        painter.end()


class RowActions(QWidget):
    """Wadah aksi baris dengan tombol ukuran xs yang tidak saling menimpa."""

    def __init__(self, buttons: list[Button], parent=None):
        super().__init__(parent)
        self.setObjectName("RowActions")
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(2, 2, 2, 2)
        self._layout.setSpacing(3)
        self._natural_widths: list[int] = []
        for button in buttons:
            button.setParent(self)
            button.setProperty("role", "row-action")
            # Ukuran tetap berdasarkan lebar teks di font aktif. Kebijakan
            # Fixed mencegah tombol saling mendorong saat kolom aksi sempit.
            metrics = QFontMetrics(button.font())
            width = metrics.horizontalAdvance(button.text()) + 14
            self._natural_widths.append(width)
            button.setFixedWidth(width)
            button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            self._layout.addWidget(button)
        self._layout.addStretch()
        self.buttons = buttons

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._fit_buttons()

    def _fit_buttons(self) -> None:
        """Perkecil tombol secara proporsional bila kolom aksi terlalu sempit."""
        if not self.buttons or not self._natural_widths:
            return
        margins = self._layout.contentsMargins()
        spacing = self._layout.spacing() * max(0, len(self.buttons) - 1)
        available = self.width() - margins.left() - margins.right() - spacing
        if available <= 0:
            return

        total = sum(self._natural_widths)
        if total <= available:
            widths = list(self._natural_widths)
        else:
            scale = available / total
            widths = [max(24, int(width * scale)) for width in self._natural_widths]
            while sum(widths) > available:
                widest = widths.index(max(widths))
                if widths[widest] <= 24:
                    break
                widths[widest] -= 1

        for button, width in zip(self.buttons, widths):
            if button.width() != width:
                button.setFixedWidth(width)
