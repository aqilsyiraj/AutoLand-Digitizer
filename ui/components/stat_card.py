"""Kartu metrik: label kecil, angka besar, dan aksen warna tipis."""

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout


def stat_block(parent_layout: QHBoxLayout, caption: str) -> QLabel:
    """Blok statistik ringkas: angka besar dengan keterangan di bawahnya."""
    box = QVBoxLayout()
    box.setSpacing(0)
    value = QLabel("0")
    value.setObjectName("StatValue")
    value.setStyleSheet("font-size: 20px;")
    cap = QLabel(caption)
    cap.setObjectName("StatSubtitle")
    box.addWidget(value)
    box.addWidget(cap)
    parent_layout.addLayout(box)
    return value


class StatCard(QFrame):
    def __init__(
        self,
        title: str,
        value: str = "0",
        subtitle: str = "",
        accent_color: str = "#0F766E",
        parent=None,
        compact: bool = False,
    ):
        super().__init__(parent)
        self.setObjectName("StatCard")
        self.setProperty("compact", "true" if compact else "false")
        self.setProperty("accent", accent_color)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            11 if compact else 14, 8 if compact else 11,
            11 if compact else 14, 8 if compact else 11,
        )
        layout.setSpacing(2)

        head = QHBoxLayout()
        head.setSpacing(6)
        dot = QLabel("●")
        dot.setStyleSheet(f"color: {accent_color}; font-size: 9px;")
        dot.setFixedWidth(10)
        head.addWidget(dot)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("StatTitle")
        self.title_label.setWordWrap(True)
        head.addWidget(self.title_label, 1)
        layout.addLayout(head)

        self.value_label = QLabel(value)
        self.value_label.setObjectName("StatValue")
        layout.addWidget(self.value_label)

        self.subtitle_label = QLabel(subtitle)
        self.subtitle_label.setObjectName("StatSubtitle")
        self.subtitle_label.setWordWrap(True)
        if not subtitle:
            self.subtitle_label.hide()
        layout.addWidget(self.subtitle_label)

    def set_value(self, value: str, subtitle: str = ""):
        self.value_label.setText(str(value))
        if subtitle:
            self.subtitle_label.setText(subtitle)
            self.subtitle_label.show()
