"""
Motion layer untuk UI PySide6 desktop.

GSAP, ScrollTrigger, dan Lenis adalah library browser dan tidak bisa dipakai
langsung oleh widget Qt. Modul ini memberi padanan yang sesuai untuk aplikasi
desktop: transisi halaman fade-in, ekspansi panduan yang halus, pulse status,
dan smooth-scroll pada QScrollArea. Semua memakai QPropertyAnimation bawaan Qt.
"""

from PySide6.QtCore import (
    QEasingCurve,
    QObject,
    QParallelAnimationGroup,
    QPropertyAnimation,
    QSequentialAnimationGroup,
)
from PySide6.QtWidgets import QGraphicsOpacityEffect, QScrollArea

__all__ = [
    "fade_in",
    "fade_swap",
    "pulse",
    "animate_height",
    "smooth_scroll",
    "SmoothScrollArea",
    "MotionGroup",
]


class MotionGroup(QParallelAnimationGroup):
    """Kumpulan animasi yang dibersihkan otomatis setelah selesai."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.finished.connect(self.deleteLater)


def fade_in(widget, duration: int = 180, start: float = 0.88, parent=None):
    """Fade widget masuk sekali saat widget tampil."""
    effect = widget.graphicsEffect()
    if not isinstance(effect, QGraphicsOpacityEffect):
        effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)

    anim = QPropertyAnimation(effect, b"opacity", parent or widget)
    anim.setStartValue(start)
    anim.setEndValue(1.0)
    anim.setDuration(duration)
    anim.setEasingCurve(QEasingCurve.OutCubic)
    anim.start()
    return anim


def fade_swap(hidden_widget, visible_widget, duration: int = 180):
    """Fade-out widget lama lalu fade-in widget baru."""
    group = QSequentialAnimationGroup()
    group.finished.connect(group.deleteLater)

    for widget in (hidden_widget, visible_widget):
        if widget is None:
            continue
        effect = widget.graphicsEffect()
        if not isinstance(effect, QGraphicsOpacityEffect):
            effect = QGraphicsOpacityEffect(widget)
            widget.setGraphicsEffect(effect)

    if hidden_widget is not None:
        out = QPropertyAnimation(
            hidden_widget.graphicsEffect(), b"opacity", hidden_widget
        )
        out.setStartValue(1.0)
        out.setEndValue(0.0)
        out.setDuration(max(80, duration // 2))
        out.setEasingCurve(QEasingCurve.InCubic)
        group.addAnimation(out)

    if visible_widget is not None:
        inn = QPropertyAnimation(
            visible_widget.graphicsEffect(), b"opacity", visible_widget
        )
        inn.setStartValue(0.88)
        inn.setEndValue(1.0)
        inn.setDuration(duration)
        inn.setEasingCurve(QEasingCurve.OutCubic)
        group.addAnimation(inn)

    group.start()
    return group


def pulse(widget, cycles: int = 2, duration: int = 260):
    """Pulse ringan untuk status sukses / peringatan."""
    effect = widget.graphicsEffect()
    if not isinstance(effect, QGraphicsOpacityEffect):
        effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)

    group = QSequentialAnimationGroup(widget)
    group.finished.connect(group.deleteLater)
    for _ in range(cycles):
        down = QPropertyAnimation(effect, b"opacity", widget)
        down.setStartValue(1.0)
        down.setEndValue(0.55)
        down.setDuration(duration // 2)
        up = QPropertyAnimation(effect, b"opacity", widget)
        up.setStartValue(0.55)
        up.setEndValue(1.0)
        up.setDuration(duration // 2)
        group.addAnimation(down)
        group.addAnimation(up)
    group.start()
    return group


def animate_height(widget, target_height: int, duration: int = 180, parent=None):
    """Animasi tinggi widget, dipakai untuk membuka/menutup panduan."""
    anim = QPropertyAnimation(widget, b"maximumHeight", parent or widget)
    anim.setStartValue(max(widget.height(), 1))
    anim.setEndValue(max(target_height, 1))
    anim.setDuration(duration)
    anim.setEasingCurve(QEasingCurve.OutCubic)
    anim.start()
    return anim


def smooth_scroll(scroll_area, target_value: int, duration: int = 280):
    """Padanan Lenis: gerak scroll halus untuk QScrollArea."""
    bar = scroll_area.verticalScrollBar()
    anim = QPropertyAnimation(bar, b"value", scroll_area)
    anim.setStartValue(bar.value())
    anim.setEndValue(int(target_value))
    anim.setDuration(duration)
    anim.setEasingCurve(QEasingCurve.OutCubic)
    anim.start()
    return anim


class SmoothScrollArea(QScrollArea):
    """QScrollArea dengan guliran halus ala Lenis untuk konten pengaturan."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scroll_animation = None

    def wheelEvent(self, event):
        bar = self.verticalScrollBar()
        if bar.maximum() <= bar.minimum():
            super().wheelEvent(event)
            return

        delta = event.angleDelta().y()
        if delta == 0:
            super().wheelEvent(event)
            return

        if self._scroll_animation is not None:
            self._scroll_animation.stop()

        target = bar.value() - int(delta * 1.4)
        target = max(bar.minimum(), min(bar.maximum(), target))
        self._scroll_animation = smooth_scroll(self, target, duration=240)
        event.accept()
