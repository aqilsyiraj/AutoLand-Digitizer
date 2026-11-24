"""Field formulir ringkas: label, keterangan, dan input tanpa ruang berlebih."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget


class FormField(QWidget):
    """Label + hint + input. Hint tampil di bawah label, bukan blok besar."""

    def __init__(
        self,
        label: str,
        hint: str,
        widget: QWidget,
        required: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        text = f"{label} <span style='color:#B91C1C;'>*</span>" if required else label
        self.label = QLabel(text)
        self.label.setObjectName("FormFieldLabel")
        self.label.setTextFormat(Qt.RichText)
        layout.addWidget(self.label)

        if hint:
            self.hint = QLabel(hint)
            self.hint.setObjectName("FormFieldHint")
            self.hint.setWordWrap(True)
            layout.addWidget(self.hint)
        else:
            self.hint = None

        self.widget = widget
        widget.setToolTip(hint or label)
        layout.addWidget(widget)


class InlineField(QWidget):
    """Label + input dalam satu baris untuk filter dan pengaturan."""

    def __init__(self, label: str, hint: str, widget: QWidget, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.label = QLabel(label)
        self.label.setObjectName("FormFieldLabel")
        self.label.setMinimumWidth(74)
        layout.addWidget(self.label)

        self.hint = hint
        self.widget = widget
        widget.setToolTip(hint or label)
        layout.addWidget(widget, 1)
