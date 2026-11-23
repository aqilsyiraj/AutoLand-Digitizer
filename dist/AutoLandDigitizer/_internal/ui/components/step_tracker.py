"""
AutoLand Digitizer - Step Tracker Component
Indikator visual langkah alur kerja proses digitasi dengan tanda centang (checkmark),
nomor urut, dan status aktif/selesai agar operator selalu tahu di mana posisi langkahnya.
"""

from PySide6.QtWidgets import QFrame, QHBoxLayout, QPushButton, QLabel, QWidget
from PySide6.QtCore import Qt, Signal

class StepTracker(QFrame):
    step_clicked = Signal(int) # Emits index when operator clicks a step button

    def __init__(self, steps: list[str], parent=None):
        super().__init__(parent)
        self.steps = steps
        self.current_step = 0
        self.completed_steps = set()
        self.buttons: list[QPushButton] = []
        self._setup_ui()

    def _setup_ui(self):
        self.setStyleSheet("""
            StepTracker {
                background-color: #FFFFFF;
                border: 1px solid #E2E8F0;
                border-radius: 8px;
            }
        """)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)

        for idx, step_name in enumerate(self.steps):
            btn = QPushButton(f" {idx + 1}. {step_name} ")
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda checked=False, i=idx: self.step_clicked.emit(i))
            layout.addWidget(btn, 1)
            self.buttons.append(btn)

            if idx < len(self.steps) - 1:
                arrow = QLabel("➔")
                arrow.setStyleSheet("color: #CBD5E1; font-weight: bold; font-size: 13px;")
                layout.addWidget(arrow)

        self.set_current_step(0)

    def set_current_step(self, step_idx: int):
        self.current_step = step_idx
        for idx, btn in enumerate(self.buttons):
            is_active = (idx == step_idx)
            is_done = (idx in self.completed_steps)
            prefix = "✓ " if is_done else f"{idx + 1}. "
            name = self.steps[idx]
            btn.setText(f" {prefix}{name} ")

            if is_active:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #1E40AF;
                        color: #FFFFFF;
                        font-weight: 700;
                        font-size: 12px;
                        border-radius: 6px;
                        padding: 8px 12px;
                        border: 2px solid #3B82F6;
                    }
                """)
            elif is_done:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #ECFDF5;
                        color: #047857;
                        font-weight: 600;
                        font-size: 12px;
                        border-radius: 6px;
                        padding: 8px 12px;
                        border: 1.5px solid #10B981;
                    }
                    QPushButton:hover {
                        background-color: #D1FAE5;
                    }
                """)
            else:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #F8FAFC;
                        color: #64748B;
                        font-weight: 500;
                        font-size: 12px;
                        border-radius: 6px;
                        padding: 8px 12px;
                        border: 1px solid #E2E8F0;
                    }
                    QPushButton:hover {
                        background-color: #F1F5F9;
                        color: #334155;
                    }
                """)

    def mark_completed(self, step_idx: int):
        self.completed_steps.add(step_idx)
        self.set_current_step(self.current_step)
