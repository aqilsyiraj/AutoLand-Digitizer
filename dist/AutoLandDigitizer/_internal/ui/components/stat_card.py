"""
AutoLand Digitizer - Stat Card Component
Menampilkan metrik ringkasan dashboard dengan desain kartu modern.
"""

from PySide6.QtWidgets import QFrame, QVBoxLayout, QLabel, QHBoxLayout
from PySide6.QtCore import Qt

class StatCard(QFrame):
    def __init__(self, title: str, value: str = "0", subtitle: str = "", accent_color: str = "#1E40AF", parent=None):
        super().__init__(parent)
        self.accent_color = accent_color
        self.setObjectName("StatCard")
        self.setStyleSheet(f"""
            #StatCard {{
                background-color: #FFFFFF;
                border-radius: 10px;
                border: 1px solid #E2E8F0;
                border-left: 4px solid {accent_color};
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(4)
        
        # Header (Title)
        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("color: #64748B; font-size: 12px; font-weight: 600; text-transform: uppercase;")
        layout.addWidget(self.title_label)
        
        # Metric Value
        self.value_label = QLabel(value)
        self.value_label.setStyleSheet("color: #0F172A; font-size: 26px; font-weight: 800;")
        layout.addWidget(self.value_label)
        
        # Subtitle / Hint
        self.subtitle_label = QLabel(subtitle)
        self.subtitle_label.setStyleSheet("color: #94A3B8; font-size: 11px;")
        if not subtitle:
            self.subtitle_label.hide()
        layout.addWidget(self.subtitle_label)

    def set_value(self, value: str, subtitle: str = ""):
        self.value_label.setText(str(value))
        if subtitle:
            self.subtitle_label.setText(subtitle)
            self.subtitle_label.show()
