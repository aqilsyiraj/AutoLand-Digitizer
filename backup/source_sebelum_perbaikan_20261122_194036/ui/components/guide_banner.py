"""
AutoLand Digitizer - Guide Banner Component
Komponen banner panduan interaktif yang dapat diperluas/diciutkan (collapsible)
untuk memberikan petunjuk jelas bagi operator di setiap halaman.
"""

from PySide6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PySide6.QtCore import Qt

class GuideBanner(QFrame):
    def __init__(self, title: str, instructions: list[str], parent=None):
        super().__init__(parent)
        self.is_collapsed = False
        self.setObjectName("GuideBanner")
        self.setStyleSheet("""
            #GuideBanner {
                background-color: #F0F9FF;
                border: 1px solid #BAE6FD;
                border-left: 5px solid #0284C7;
                border-radius: 8px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(6)

        # Header Row: Title & Toggle Button
        header_row = QHBoxLayout()
        header_row.setSpacing(8)

        lbl_icon = QLabel("💡")
        lbl_icon.setStyleSheet("font-size: 16px;")
        header_row.addWidget(lbl_icon)

        self.lbl_title = QLabel(title)
        self.lbl_title.setStyleSheet("font-size: 13px; font-weight: 700; color: #0369A1;")
        header_row.addWidget(self.lbl_title)

        header_row.addStretch()

        self.btn_toggle = QPushButton("Sembunyikan Petunjuk ▲")
        self.btn_toggle.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                color: #0284C7;
                font-size: 11px;
                font-weight: 600;
                padding: 2px 6px;
            }
            QPushButton:hover {
                text-decoration: underline;
                color: #0369A1;
            }
        """)
        self.btn_toggle.clicked.connect(self._toggle_collapse)
        header_row.addWidget(self.btn_toggle)

        layout.addLayout(header_row)

        # Content Box
        self.content_widget = QFrame()
        c_layout = QVBoxLayout(self.content_widget)
        c_layout.setContentsMargins(24, 2, 4, 4)
        c_layout.setSpacing(4)

        for idx, item in enumerate(instructions, start=1):
            lbl_item = QLabel(f"<b>{idx}.</b> {item}")
            lbl_item.setWordWrap(True)
            lbl_item.setStyleSheet("font-size: 12px; color: #0F172A; line-height: 1.4;")
            c_layout.addWidget(lbl_item)

        layout.addWidget(self.content_widget)

    def _toggle_collapse(self):
        self.is_collapsed = not self.is_collapsed
        if self.is_collapsed:
            self.content_widget.hide()
            self.btn_toggle.setText("Tampilkan Petunjuk ▼")
        else:
            self.content_widget.show()
            self.btn_toggle.setText("Sembunyikan Petunjuk ▲")
