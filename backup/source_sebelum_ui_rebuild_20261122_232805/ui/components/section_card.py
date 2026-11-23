"""Kartu bagian dengan judul dan sub judul yang seragam di seluruh halaman."""

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout


class SectionCard(QFrame):
    def __init__(self, title: str, subtitle: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("SectionCard")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 12, 14, 12)
        outer.setSpacing(8)

        head = QHBoxLayout()
        head.setSpacing(8)
        self.title_label = QLabel(title)
        self.title_label.setObjectName("SectionTitle")
        self.title_label.setWordWrap(True)
        head.addWidget(self.title_label)
        if subtitle:
            self.subtitle_label = QLabel(subtitle)
            self.subtitle_label.setObjectName("SectionSubtitle")
            self.subtitle_label.setWordWrap(True)
            head.addWidget(self.subtitle_label, 1)
        else:
            head.addStretch()
        outer.addLayout(head)

        self.body = QVBoxLayout()
        self.body.setSpacing(8)
        outer.addLayout(self.body, 1)

    @property
    def body_layout(self):
        return self.body
