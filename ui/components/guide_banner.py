"""Banner petunjuk ringkas yang bisa dibuka saat operator butuh detail."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
)


class GuideBanner(QFrame):
    def __init__(
        self,
        title: str,
        instructions: list[str],
        parent=None,
        collapsed: bool = True,
    ):
        super().__init__(parent)
        self.setObjectName("GuideBanner")
        self.instructions = instructions
        self.is_collapsed = collapsed

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(4)

        header = QHBoxLayout()
        header.setSpacing(8)
        self.lbl_title = QLabel(title)
        self.lbl_title.setObjectName("GuideTitle")
        self.lbl_title.setWordWrap(False)
        header.addWidget(self.lbl_title, 1)

        self.btn_toggle = QPushButton()
        self.btn_toggle.setObjectName("GuideToggle")
        self.btn_toggle.setCursor(Qt.PointingHandCursor)
        self.btn_toggle.setSizePolicy(
            self.btn_toggle.sizePolicy().horizontalPolicy(), QSizePolicy.Fixed
        )
        self.btn_toggle.clicked.connect(self._toggle_collapse)
        header.addWidget(self.btn_toggle)
        layout.addLayout(header)

        self.content_widget = QFrame()
        content = QVBoxLayout(self.content_widget)
        content.setContentsMargins(2, 0, 0, 1)
        content.setSpacing(3)
        for idx, item in enumerate(instructions, start=1):
            lbl = QLabel(f"<b style='color:#0F766E;'>{idx}.</b>&nbsp; {item}")
            lbl.setObjectName("GuideItem")
            lbl.setTextFormat(Qt.RichText)
            lbl.setWordWrap(True)
            content.addWidget(lbl)
        layout.addWidget(self.content_widget)

        self._apply_state()

    def _apply_state(self):
        total = len(self.instructions)
        self.content_widget.setVisible(not self.is_collapsed)
        self.btn_toggle.setText(
            f"Petunjuk ({total}) ▾" if self.is_collapsed else "Tutup ▴"
        )
        self.btn_toggle.setToolTip(
            "Buka petunjuk lengkap halaman ini"
            if self.is_collapsed
            else "Tutup petunjuk agar ruang kerja lebih luas"
        )

    def _toggle_collapse(self):
        self.is_collapsed = not self.is_collapsed
        self._apply_state()
