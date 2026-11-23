"""
AutoLand Digitizer - Interactive Crop Canvas
Komponen interaktif untuk memotong denah bidang tanah dari preview PDF menggunakan mouse drag.
Dilengkapi efek dimming semi-transparan, penanda sudut, dan konversi koordinat ternormalisasi.
"""

from PySide6.QtWidgets import QWidget, QScrollArea, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QFrame
from PySide6.QtCore import Qt, QRectF, QPointF, Signal
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QPixmap, QImage, QFont
from typing import Optional, Tuple

class CropInteractiveWidget(QWidget):
    """
    Kanvas interaktif yang menggambar preview halaman PDF dan menangani mouse drag seleksi crop.
    """
    crop_changed = Signal(bool) # emit True jika ada area terseleksi

    def __init__(self, parent=None):
        super().__init__(parent)
        self.pixmap: Optional[QPixmap] = None
        self.start_point: Optional[QPointF] = None
        self.current_point: Optional[QPointF] = None
        self.selection_rect: Optional[QRectF] = None
        self.is_dragging = False
        self.zoom_factor = 1.0
        
        self.setMouseTracking(True)
        self.setCursor(Qt.CrossCursor)

    def set_image_bytes(self, image_bytes: bytes):
        """Memuat gambar halaman PDF dari bytes (PNG)."""
        image = QImage.fromData(image_bytes)
        if not image.isNull():
            self.pixmap = QPixmap.fromImage(image)
            self.selection_rect = None
            self.zoom_factor = 1.0
            self.update_canvas_size()
            self.update()
            self.crop_changed.emit(False)

    def set_zoom(self, zoom: float):
        """Mengatur tingkat perbesaran gambar (0.5 s/d 3.0)."""
        self.zoom_factor = max(0.2, min(3.0, zoom))
        self.update_canvas_size()
        self.update()

    def update_canvas_size(self):
        if self.pixmap:
            w = int(self.pixmap.width() * self.zoom_factor)
            h = int(self.pixmap.height() * self.zoom_factor)
            self.setFixedSize(w, h)

    def reset_crop(self):
        """Mereset seleksi crop."""
        self.selection_rect = None
        self.start_point = None
        self.current_point = None
        self.is_dragging = False
        self.update()
        self.crop_changed.emit(False)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.pixmap:
            self.start_point = event.position()
            self.current_point = self.start_point
            self.is_dragging = True
            self.selection_rect = QRectF(self.start_point, self.current_point).normalized()
            self.update()

    def mouseMoveEvent(self, event):
        if self.is_dragging and self.pixmap:
            self.current_point = event.position()
            # Batasi agar tidak melebihi area gambar
            bounded_x = max(0.0, min(float(self.width()), self.current_point.x()))
            bounded_y = max(0.0, min(float(self.height()), self.current_point.y()))
            self.current_point = QPointF(bounded_x, bounded_y)
            
            self.selection_rect = QRectF(self.start_point, self.current_point).normalized()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.is_dragging:
            self.is_dragging = False
            if self.selection_rect:
                # Validasi ukuran minimal
                if self.selection_rect.width() > 10 and self.selection_rect.height() > 10:
                    self.crop_changed.emit(True)
                else:
                    self.selection_rect = None
                    self.crop_changed.emit(False)
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        if not self.pixmap:
            painter.fillRect(self.rect(), QColor("#F8FAFC"))
            painter.setPen(QColor("#94A3B8"))
            painter.setFont(QFont("Segoe UI", 12))
            painter.drawText(self.rect(), Qt.AlignCenter, "Belum ada halaman PDF yang dipilih.")
            return

        # 1. Gambar Pixmap Dasar
        target_rect = QRectF(0, 0, self.width(), self.height())
        painter.drawPixmap(target_rect.toRect(), self.pixmap)

        # 2. Efek Overlay Semi-Transparan & Crop Box
        if self.selection_rect and self.selection_rect.isValid() and self.selection_rect.width() > 0:
            # Masking gelap di luar area crop (dimming)
            mask_color = QColor(15, 23, 42, 140) # Slate-900 dengan transparansi
            
            # 4 kuadran di luar crop
            r = self.selection_rect
            w = float(self.width())
            h = float(self.height())
            
            # Top
            painter.fillRect(QRectF(0, 0, w, r.top()), mask_color)
            # Bottom
            painter.fillRect(QRectF(0, r.bottom(), w, h - r.bottom()), mask_color)
            # Left
            painter.fillRect(QRectF(0, r.top(), r.left(), r.height()), mask_color)
            # Right
            painter.fillRect(QRectF(r.right(), r.top(), w - r.right(), r.height()), mask_color)

            # Border Crop Box (Biru Tegas)
            border_pen = QPen(QColor("#2563EB"), 2, Qt.SolidLine)
            painter.setPen(border_pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(r)

            # Gambar Handle Sudut (Corner Knobs)
            knob_size = 8.0
            painter.setBrush(QBrush(QColor("#FFFFFF")))
            painter.setPen(QPen(QColor("#1D4ED8"), 1.5))
            
            corners = [
                r.topLeft(),
                r.topRight(),
                r.bottomLeft(),
                r.bottomRight(),
                QPointF(r.center().x(), r.top()),
                QPointF(r.center().x(), r.bottom()),
                QPointF(r.left(), r.center().y()),
                QPointF(r.right(), r.center().y()),
            ]
            for c in corners:
                painter.drawRect(QRectF(c.x() - knob_size / 2, c.y() - knob_size / 2, knob_size, knob_size))

            # Label Ukuran Crop
            badge_text = f"Denah: {int(r.width())} × {int(r.height())} px"
            painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
            badge_rect = QRectF(r.left() + 6, max(0.0, r.top() - 24), 140, 20)
            painter.fillRect(badge_rect, QColor(37, 99, 235, 220))
            painter.setPen(QColor("#FFFFFF"))
            painter.drawText(badge_rect, Qt.AlignCenter, badge_text)

    def get_normalized_box(self) -> Optional[Tuple[float, float, float, float]]:
        """
        Mengembalikan koordinat ternormalisasi (0.0 s/d 1.0) dari area yang dipotong:
        (norm_x0, norm_y0, norm_x1, norm_y1)
        Aman dari perubahan ukuran layar atau zoom.
        """
        if not self.selection_rect or self.selection_rect.width() <= 5 or self.selection_rect.height() <= 5:
            return None
            
        w = float(self.width())
        h = float(self.height())
        if w == 0 or h == 0:
            return None
            
        nx0 = max(0.0, min(1.0, self.selection_rect.left() / w))
        ny0 = max(0.0, min(1.0, self.selection_rect.top() / h))
        nx1 = max(0.0, min(1.0, self.selection_rect.right() / w))
        ny1 = max(0.0, min(1.0, self.selection_rect.bottom() / h))
        
        return (nx0, ny0, nx1, ny1)


class InteractiveCropCanvas(QWidget):
    """
    Wadah utama pengontrol kanvas crop dengan scroll area, tombol zoom in, zoom out, fit, dan reset.
    """
    confirmed = Signal(tuple) # emit (norm_x0, norm_y0, norm_x1, norm_y1)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Toolbar Pengontrol
        toolbar = QFrame()
        toolbar.setStyleSheet("background-color: #F1F5F9; border-radius: 8px; padding: 4px;")
        t_layout = QHBoxLayout(toolbar)
        t_layout.setContentsMargins(8, 4, 8, 4)
        t_layout.setSpacing(8)

        self.info_label = QLabel("Tarik kursor mouse (drag) untuk memilih area denah bidang tanah")
        self.info_label.setStyleSheet("color: #475569; font-weight: 600; font-size: 12px;")
        t_layout.addWidget(self.info_label)

        t_layout.addStretch()

        self.btn_zoom_out = QPushButton("Zoom -")
        self.btn_zoom_out.setProperty("class", "btn-secondary")
        self.btn_zoom_out.clicked.connect(self._on_zoom_out)
        t_layout.addWidget(self.btn_zoom_out)

        self.btn_zoom_reset = QPushButton("100%")
        self.btn_zoom_reset.setProperty("class", "btn-secondary")
        self.btn_zoom_reset.clicked.connect(self._on_zoom_reset)
        t_layout.addWidget(self.btn_zoom_reset)

        self.btn_zoom_in = QPushButton("Zoom +")
        self.btn_zoom_in.setProperty("class", "btn-secondary")
        self.btn_zoom_in.clicked.connect(self._on_zoom_in)
        t_layout.addWidget(self.btn_zoom_in)

        self.btn_reset_crop = QPushButton("Ulangi Crop")
        self.btn_reset_crop.setProperty("class", "btn-warning")
        self.btn_reset_crop.clicked.connect(self._on_reset_crop)
        t_layout.addWidget(self.btn_reset_crop)

        self.btn_confirm_crop = QPushButton("Konfirmasi Potongan")
        self.btn_confirm_crop.setProperty("class", "btn-primary")
        self.btn_confirm_crop.setEnabled(False)
        self.btn_confirm_crop.clicked.connect(self._on_confirm_crop)
        t_layout.addWidget(self.btn_confirm_crop)

        layout.addWidget(toolbar)

        # Scroll Area untuk Preview Gambar
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(False)
        self.scroll_area.setAlignment(Qt.AlignCenter)
        self.scroll_area.setStyleSheet("background-color: #334155; border: 1px solid #CBD5E1; border-radius: 8px;")

        self.canvas = CropInteractiveWidget()
        self.canvas.crop_changed.connect(self._on_crop_changed)
        self.scroll_area.setWidget(self.canvas)
        layout.addWidget(self.scroll_area, 1)

    def load_page_image(self, img_bytes: bytes):
        """Memuat gambar halaman ke kanvas."""
        self.canvas.set_image_bytes(img_bytes)
        self.btn_confirm_crop.setEnabled(False)

    def _on_crop_changed(self, has_selection: bool):
        self.btn_confirm_crop.setEnabled(has_selection)
        if has_selection:
            self.info_label.setText("Area denah berhasil dipilih. Klik 'Konfirmasi Potongan' untuk melanjutkan.")
        else:
            self.info_label.setText("Tarik kursor mouse (drag) untuk memilih area denah bidang tanah")

    def _on_zoom_in(self):
        self.canvas.set_zoom(self.canvas.zoom_factor + 0.2)

    def _on_zoom_out(self):
        self.canvas.set_zoom(self.canvas.zoom_factor - 0.2)

    def _on_zoom_reset(self):
        self.canvas.set_zoom(1.0)

    def _on_reset_crop(self):
        self.canvas.reset_crop()

    def _on_confirm_crop(self):
        norm_box = self.canvas.get_normalized_box()
        if norm_box:
            self.confirmed.emit(norm_box)

    def get_normalized_box(self) -> Optional[Tuple[float, float, float, float]]:
        return self.canvas.get_normalized_box()
