"""Kartu bagian dengan kepala ringkas, sub judul, dan area aksi opsional."""

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout

from ui.motion.qt_motion import fade_in


class SectionCard(QFrame):
    def __init__(self, title: str, subtitle: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("SectionCard")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 14, 16, 16)
        outer.setSpacing(12)

        head = QHBoxLayout()
        head.setSpacing(10)

        text = QVBoxLayout()
        text.setSpacing(1)
        self.title_label = QLabel(title)
        self.title_label.setObjectName("SectionTitle")
        self.title_label.setWordWrap(True)
        text.addWidget(self.title_label)

        if subtitle:
            self.subtitle_label = QLabel(subtitle)
            self.subtitle_label.setObjectName("SectionSubtitle")
            self.subtitle_label.setWordWrap(True)
            text.addWidget(self.subtitle_label)
        else:
            self.subtitle_label = None
        head.addLayout(text, 1)

        self.actions = QHBoxLayout()
        self.actions.setSpacing(7)
        head.addLayout(self.actions, 0)
        outer.addLayout(head)

        self.body = QVBoxLayout()
        self.body.setSpacing(10)
        outer.addLayout(self.body, 1)

        fade_in(self, duration=220)

    def add_action(self, widget) -> None:
        self.actions.addWidget(widget)

    @property
    def body_layout(self):
        return self.body
