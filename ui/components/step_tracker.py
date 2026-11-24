"""Indikator 4 langkah digitasi yang bisa diklik untuk kembali ke langkah awal."""

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
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        for idx, name in enumerate(self.steps):
            btn = QPushButton()
            btn.setObjectName("StepButton")
            btn.setProperty("role", "step")
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda checked=False, i=idx: self.step_clicked.emit(i))
            layout.addWidget(btn, 1)
            self.buttons.append(btn)

            if idx < len(self.steps) - 1:
                arrow = QLabel("→")
                arrow.setObjectName("StepArrow")
                arrow.setAlignment(Qt.AlignCenter)
                arrow.setFixedWidth(14)
                layout.addWidget(arrow)

        self.set_current_step(0)

    def set_current_step(self, step_idx: int):
        self.current_step = step_idx
        for idx, btn in enumerate(self.buttons):
            is_done = idx in self.completed_steps
            prefix = "✓" if is_done else str(idx + 1)
            # QPushButton memakai '&' sebagai penanda mnemonic; escaping
            # mencegah teks seperti "Periksa & Isi Data" kehilangan tanda '&'.
            btn.setText(f"{prefix}   {self.steps[idx].replace('&', '&&')}")
            if idx == step_idx:
                state = "active"
            elif is_done:
                state = "done"
            else:
                state = "idle"
            btn.setProperty("state", state)
            btn.setToolTip(
                "Langkah sedang dibuka"
                if state == "active"
                else "Klik untuk kembali ke langkah ini"
                if state == "done"
                else "Selesaikan langkah sebelumnya untuk membuka ini"
            )
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def mark_completed(self, step_idx: int):
        self.completed_steps.add(step_idx)
        self.set_current_step(self.current_step)
