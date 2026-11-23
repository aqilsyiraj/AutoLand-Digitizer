"""Tombol dengan sistem ukuran dan warna yang konsisten."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPushButton, QSizePolicy

__all__ = ["Button", "apply_button_style"]


def apply_button_style(button: QPushButton, size: str = "md", tone: str = "secondary"):
    """Terapkan varian tombol tanpa mengubah teks atau perilaku tombol."""
    # "size" adalah properti bawaan QWidget (QSize); memakainya sebagai
    #_property QSS akan tertimpa sehingga selector [size="xs"] tidak pernah
    # cocok. Gunakan nama khusus agar ukuran kontekstual benar-benar aktif.
    button.setProperty("btn-size", size)
    button.setProperty("tone", tone)
    # Jangan biarkan layout induk meregangkan tombol secara vertikal; tinggi
    # tetap mengikuti ukuran kontekstual (xs/sm/md/lg).
    button.setSizePolicy(
        QSizePolicy(button.sizePolicy().horizontalPolicy(), QSizePolicy.Fixed)
    )
    button.setCursor(Qt.PointingHandCursor)
    button.style().unpolish(button)
    button.style().polish(button)
    return button


class Button(QPushButton):
    """
    QPushButton dengan varian eksplisit.

    size: xs | sm | md | lg
    tone: primary | secondary | success | danger | quiet | ghost
    """

    def __init__(
        self,
        text: str = "",
        *,
        size: str = "md",
        tone: str = "secondary",
        tooltip: str = "",
        on_click=None,
        parent=None,
    ):
        super().__init__(text, parent)
        apply_button_style(self, size=size, tone=tone)
        if tooltip:
            self.setToolTip(tooltip)
        if on_click is not None:
            self.clicked.connect(on_click)
