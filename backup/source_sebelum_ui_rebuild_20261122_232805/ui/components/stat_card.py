"""Kartu metrik dashboard dengan satu aksen warna dan angka besar."""

from PySide6.QtWidgets import QFrame, QVBoxLayout, QLabel


class StatCard(QFrame):
    def __init__(self, title: str, value: str = "0", subtitle: str = "",
                 accent_color: str = "#2563EB", parent=None):
        super().__init__(parent)
        self.setObjectName("StatCard")
        self.setStyleSheet(
            f"#StatCard {{ border-left: 4px solid {accent_color}; }}"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(2)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("StatTitle")
        self.title_label.setWordWrap(True)
        layout.addWidget(self.title_label)

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
