"""Header halaman: label bagian, judul, sub judul, dan aksi di kanan."""

from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ui.motion.qt_motion import fade_in


class PageHeader(QWidget):
    def __init__(self, title: str, subtitle: str = "", eyebrow: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("PageHeader")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        text = QVBoxLayout()
        text.setSpacing(2)

        self.eyebrow_label = QLabel(eyebrow.upper())
        self.eyebrow_label.setObjectName("PageEyebrow")
        self.eyebrow_label.setVisible(bool(eyebrow))
        text.addWidget(self.eyebrow_label)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("PageTitle")
        self.title_label.setWordWrap(True)
        text.addWidget(self.title_label)

        self.subtitle_label = QLabel(subtitle)
        self.subtitle_label.setObjectName("PageSubtitle")
        self.subtitle_label.setWordWrap(True)
        self.subtitle_label.setVisible(bool(subtitle))
        text.addWidget(self.subtitle_label)

        layout.addLayout(text, 1)

        self.actions = QHBoxLayout()
        self.actions.setSpacing(8)
        layout.addLayout(self.actions, 0)

        fade_in(self, duration=200)

    def add_action(self, widget) -> None:
        self.actions.addWidget(widget)

    def add_stretch(self) -> None:
        self.actions.addStretch()

    def set_eyebrow(self, text: str) -> None:
        self.eyebrow_label.setText(text.upper())
        self.eyebrow_label.setVisible(bool(text))
