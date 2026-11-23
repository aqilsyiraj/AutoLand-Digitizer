"""
AutoLand Digitizer - Form Field Components

Membantu operator memahami setiap kolom/input melalui label yang jelas,
keterangan singkat, dan tooltip. Dipakai pada formulir batch, data dokumen,
pencarian, dan pengaturan.
"""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel
from PySide6.QtCore import Qt


class FormField(QWidget):
    """Label + keterangan + widget input, disusun vertikal."""

    def __init__(self, label: str, hint: str, widget: QWidget, required: bool = False, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)

        self.label = QLabel(f"{label} <span style='color:#DC2626;'>*</span>" if required else label)
        self.label.setObjectName("FormFieldLabel")
        self.label.setTextFormat(Qt.RichText)
        layout.addWidget(self.label)

        if hint:
            self.hint = QLabel(hint)
            self.hint.setObjectName("FormFieldHint")
            self.hint.setWordWrap(True)
            layout.addWidget(self.hint)

        self.widget = widget
        widget.setToolTip(hint or label)
        layout.addWidget(widget)


class InlineField(QWidget):
    """Label + input dalam satu baris, cocok untuk filter dan pengaturan."""

    def __init__(self, label: str, hint: str, widget: QWidget, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.label = QLabel(label)
        self.label.setObjectName("FormFieldLabel")
        self.label.setMinimumWidth(76)
        layout.addWidget(self.label)

        self.widget = widget
        widget.setToolTip(hint or label)
        layout.addWidget(widget, 1)
