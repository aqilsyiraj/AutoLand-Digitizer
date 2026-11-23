"""Indikator 4 langkah digitasi yang bisa diklik untuk kembali ke langkah sebelumnya."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton


class StepTracker(QFrame):
    step_clicked = Signal(int)

    def __init__(self, steps: list[str], parent=None):
        super().__init__(parent)
        self.setObjectName("StepTracker")
        self.setStyleSheet("QFrame#StepTracker{background:transparent;border:none;}")
        self.steps = steps
        self.current_step = 0
        self.completed_steps: set[int] = set()
        self.buttons: list[QPushButton] = []

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(4)

        for idx, name in enumerate(self.steps):
            btn = QPushButton()
            btn.setProperty("class", "step-btn")
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda checked=False, i=idx: self.step_clicked.emit(i))
            layout.addWidget(btn, 1)
            self.buttons.append(btn)

            if idx < len(self.steps) - 1:
                arrow = QLabel("›")
                arrow.setStyleSheet("color:#CBD5E1;font-size:18px;font-weight:800;")
                layout.addWidget(arrow)

        self.set_current_step(0)

    def set_current_step(self, step_idx: int):
        self.current_step = step_idx
        for idx, btn in enumerate(self.buttons):
            is_done = idx in self.completed_steps
            prefix = "✓ " if is_done else f"{idx + 1}. "
            btn.setText(f"{prefix}{self.steps[idx]}")
            if idx == step_idx:
                state = "active"
            elif is_done:
                state = "done"
            else:
                state = "idle"
            btn.setProperty("state", state)
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def mark_completed(self, step_idx: int):
        self.completed_steps.add(step_idx)
        self.set_current_step(self.current_step)
