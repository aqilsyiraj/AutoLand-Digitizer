"""
AutoLand Digitizer - Interactive Crop Canvas
Komponen interaktif untuk memotong denah bidang tanah dari preview PDF menggunakan mouse drag.
Dilengkapi efek dimming semi-transparan, penanda sudut, dan konversi koordinat ternormalisasi.
"""

from PySide6.QtWidgets import QWidget, QScrollArea, QVBoxLayout, QHBoxLayout, QLabel, QFrame
from PySide6.QtCore import Qt, QRectF, QPointF, Signal
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QPixmap, QImage, QFont
from typing import Optional, Tuple
import math

from ui.components.button import Button

class CropInteractiveWidget(QWidget):
    """
    Kanvas interaktif yang menggambar preview halaman PDF dan menangani mouse drag seleksi crop.
    """
    crop_changed = Signal(bool)                   # emit True jika ada area terseleksi
    polyline_changed = Signal(list)               # emit daftar titik ternormalisasi setelah diedit
    polyline_manual_finished = Signal(list)       # emit daftar titik ternormalisasi hasil manual drawing
    manual_draw_cancelled = Signal()              # emit saat mode manual dibatalkan (Esc)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.pixmap: Optional[QPixmap] = None
        self.start_point: Optional[QPointF] = None
        self.current_point: Optional[QPointF] = None
        self.selection_rect: Optional[QRectF] = None
        self.is_dragging = False
        self.zoom_factor = 1.0

        # Polyline hasil deteksi otomatis (koordinat ternormalisasi 0..1)
        self.polyline: list[QPointF] = []
        self.polyline_editable = False
        self._active_vertex = -1
        self._dragging_vertex = False

        # --- Mode Titik Manual Baru ---
        self.draw_mode = False               # sedang menggambar polyline manual?
        self.manual_points: list[QPointF] = []  # titik yang diklik saat draw mode
        self._hover_point: Optional[QPointF] = None  # posisi kursor untuk garis pratinjau
        self.setMouseTracking(True)
        self.setCursor(Qt.CrossCursor)
        self.setFocusPolicy(Qt.StrongFocus)

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

    def set_polyline(self, points: list, editable: bool = True):
        """Menampilkan polyline hasil deteksi di atas gambar. Titik ternormalisasi (0..1)."""
        self.polyline = [QPointF(float(x), float(y)) for x, y in points]
        self.polyline_editable = editable
        self._active_vertex = -1
        self._dragging_vertex = False
        self.update()

    def get_polyline(self) -> list:
        """Mengembalikan polyline saat ini sebagai daftar (x, y) ternormalisasi."""
        return [(round(float(p.x()), 6), round(float(p.y()), 6)) for p in self.polyline]

    def set_draw_mode(self, enabled: bool):
        """Mengaktifkan/menonaktifkan mode gambar polyline manual."""
        self.draw_mode = bool(enabled)
        self._hover_point = None
        if self.draw_mode:
            self.manual_points = []
            self.setCursor(Qt.CrossCursor)
            self.setFocus(Qt.MouseFocusReason)
        else:
            self.setCursor(Qt.ArrowCursor)
        self.update()

    def cancel_manual_draw(self):
        """Batalkan gambar manual tanpa mengirim polyline."""
        was_active = self.draw_mode
        self.manual_points = []
        self.set_draw_mode(False)
        if was_active:
            self.manual_draw_cancelled.emit()

    def finish_manual_polyline(self) -> bool:
        """
        Akhiri mode titik manual: konversi titik ke koordinat ternormalisasi
        dan emit melalui sinyal polyline_manual_finished.
        Panggil ini setelah user double-click atau klik tombol selesai.
        """
        # Konversi titik ke range 0..1 berdasarkan ukuran canvas saat ini
        w = max(1.0, float(self.width()))
        h = max(1.0, float(self.height()))
        normalized = [
            (
                round(max(0.0, min(1.0, float(p.x()))), 6),
                round(max(0.0, min(1.0, float(p.y()))), 6),
            )
            for p in self.manual_points
        ]
        valid = len(normalized) >= 3
        # Reset state lebih dulu agar tidak menggambar sisa titik
        self.manual_points = []
        self._hover_point = None
        self.set_draw_mode(False)
        if valid:
            self.polyline_manual_finished.emit(normalized)
        return valid

    def clear_polyline(self):
        self.polyline = []
        self.polyline_editable = False
        self.manual_points = []
        self._hover_point = None
        self.set_draw_mode(False)

    def _nearest_vertex(self, position: QPointF, tolerance: float = 14.0) -> int:
        if not self.polyline:
            return -1
        best, best_dist = -1, tolerance
        for idx, point in enumerate(self.polyline):
            screen = QPointF(point.x() * self.width(), point.y() * self.height())
            dist = math.hypot(screen.x() - position.x(), screen.y() - position.y())
            if dist < best_dist:
                best, best_dist = idx, dist
        return best

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
        if not self.pixmap:
            return

        position = event.position()

        # --- Mode Titik Manual: klik menambah titik ---
        if self.draw_mode:
            if event.button() != Qt.LeftButton:
                return
            nx = max(0.0, min(1.0, position.x() / max(1.0, float(self.width()))))
            ny = max(0.0, min(1.0, position.y() / max(1.0, float(self.height()))))
            self.manual_points.append(QPointF(nx, ny))
            self._hover_point = QPointF(nx, ny)
            self.update()
            # Double-click akan menyegel polyline (lihat mouseDoubleClickEvent)
            return

        # --- Mode normal (deteksi/koreksi existing) ---
        vertex_idx = self._nearest_vertex(position) if self.polyline_editable else -1

        if event.button() == Qt.RightButton and vertex_idx >= 0 and len(self.polyline) > 3:
            self.polyline.pop(vertex_idx)
            self.polyline_changed.emit(self.get_polyline())
            self.update()
            return

        if event.button() == Qt.LeftButton and vertex_idx >= 0:
            self._active_vertex = vertex_idx
            self._dragging_vertex = True
            return

        if event.button() == Qt.LeftButton:
            self.start_point = position
            self.current_point = position
            self.is_dragging = True
            self.selection_rect = QRectF(self.start_point, self.current_point).normalized()
            self.update()

    def mouseMoveEvent(self, event):
        # --- Mode Titik Manual: perbarui garis pratinjau ke posisi kursor ---
        if self.draw_mode:
            self._hover_point = QPointF(
                max(0.0, min(1.0, event.position().x() / max(1.0, float(self.width())))),
                max(0.0, min(1.0, event.position().y() / max(1.0, float(self.height())))),
            )
            self.update()
            return

        # --- Mode normal (vertex dragging / selection rect) ---
        if self._dragging_vertex and self._active_vertex >= 0:
            pos = event.position()
            nx = max(0.0, min(1.0, pos.x() / max(1.0, float(self.width()))))
            ny = max(0.0, min(1.0, pos.y() / max(1.0, float(self.height()))))
            self.polyline[self._active_vertex] = QPointF(nx, ny)
            self.polyline_changed.emit(self.get_polyline())
            self.update()
            return

        if self.is_dragging and self.pixmap:
            self.current_point = event.position()
            # Batasi agar tidak melebihi area gambar
            bounded_x = max(0.0, min(float(self.width()), self.current_point.x()))
            bounded_y = max(0.0, min(float(self.height()), self.current_point.y()))
            self.current_point = QPointF(bounded_x, bounded_y)

            self.selection_rect = QRectF(self.start_point, self.current_point).normalized()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self._dragging_vertex:
            self._dragging_vertex = False
            self._active_vertex = -1
            return

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

    def mouseDoubleClickEvent(self, event):
        # Jika sedang mode titik manual, double-click menyegel polyline
        if self.draw_mode:
            pos = event.position()
            nx = max(0.0, min(1.0, pos.x() / max(1.0, float(self.width()))))
            ny = max(0.0, min(1.0, pos.y() / max(1.0, float(self.height()))))
            if not self.manual_points or math.hypot(
                self.manual_points[-1].x() - nx, self.manual_points[-1].y() - ny
            ) > 0.001:
                self.manual_points.append(QPointF(nx, ny))
            if len(self.manual_points) >= 3:
                self.finish_manual_polyline()
            self.update()
            return

        # Jika ada polyline existennya dan editable, lakukan koreksi titik lama
        if not self.polyline_editable or len(self.polyline) < 2:
            return
        pos = event.position()
        best_idx, best_dist = -1, float("inf")
        for idx in range(len(self.polyline)):
            a = self.polyline[idx]
            b = self.polyline[(idx + 1) % len(self.polyline)]
            a_screen = QPointF(a.x() * self.width(), a.y() * self.height())
            b_screen = QPointF(b.x() * self.width(), b.y() * self.height())
            dist = self._distance_to_segment(pos, a_screen, b_screen)
            if dist < best_dist:
                best_dist, best_idx = dist, idx
        if best_idx >= 0 and best_dist < 18.0:
            nx = max(0.0, min(1.0, pos.x() / max(1.0, float(self.width()))))
            ny = max(0.0, min(1.0, pos.y() / max(1.0, float(self.height()))))
            self.polyline.insert(best_idx + 1, QPointF(nx, ny))
            self.polyline_changed.emit(self.get_polyline())
            self.update()

    def keyPressEvent(self, event):
        """Esc membatalkan mode gambar manual."""
        if self.draw_mode and event.key() == Qt.Key_Escape:
            self.cancel_manual_draw()
            return
        super().keyPressEvent(event)

    @staticmethod
    def _distance_to_segment(point: QPointF, a: QPointF, b: QPointF) -> float:
        dx, dy = b.x() - a.x(), b.y() - a.y()
        if dx == 0 and dy == 0:
            return math.hypot(point.x() - a.x(), point.y() - a.y())
        t = max(0.0, min(1.0, ((point.x() - a.x()) * dx + (point.y() - a.y()) * dy) / (dx * dx + dy * dy)))
        proj_x, proj_y = a.x() + t * dx, a.y() + t * dy
        return math.hypot(point.x() - proj_x, point.y() - proj_y)

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

        # 1b. Polyline hasil deteksi / koreksi operator
        if len(self.polyline) >= 3:
            screen_points = [
                QPointF(p.x() * self.width(), p.y() * self.height()) for p in self.polyline
            ]
            painter.setBrush(QBrush(QColor(16, 185, 129, 45)))
            painter.setPen(QPen(QColor("#10B981"), 3, Qt.SolidLine))
            for i in range(len(screen_points)):
                painter.drawLine(screen_points[i], screen_points[(i + 1) % len(screen_points)])

            for idx, point in enumerate(screen_points):
                color = QColor("#F59E0B") if idx == self._active_vertex else QColor("#059669")
                painter.setBrush(QBrush(color))
                painter.setPen(QPen(QColor("#FFFFFF"), 1.5))
                painter.drawEllipse(point, 6.5, 6.5)

        # 1c. Polyline manual drawing (mode titik manual)
        if self.draw_mode and self.manual_points:
            screen_pts = [
                QPointF(p.x() * self.width(), p.y() * self.height()) for p in self.manual_points
            ]
            # Garis penghubung antar titik yang sudah diklik
            if len(screen_pts) >= 2:
                painter.setBrush(Qt.NoBrush)
                painter.setPen(QPen(QColor("#F97316"), 2, Qt.SolidLine))
                for i in range(len(screen_pts) - 1):
                    painter.drawLine(screen_pts[i], screen_pts[i + 1])
            # Garis pratinjau putus-putus ke posisi kursor
            if self._hover_point is not None:
                painter.setBrush(Qt.NoBrush)
                painter.setPen(QPen(QColor("#FB923C"), 1.5, Qt.DashLine))
                painter.drawLine(
                    screen_pts[-1],
                    QPointF(
                        self._hover_point.x() * self.width(),
                        self._hover_point.y() * self.height(),
                    ),
                )
            # Titik yang sudah diklik + nomor urut
            painter.setFont(QFont("Segoe UI", 8, QFont.Bold))
            for i, point in enumerate(screen_pts):
                painter.setBrush(QBrush(QColor("#F97316")))
                painter.setPen(QPen(QColor("#FFFFFF"), 1.5))
                painter.drawEllipse(point, 7.0, 7.0)
                painter.setPen(QColor("#FFFFFF"))
                painter.drawText(
                    QRectF(point.x() - 7, point.y() - 7, 14, 14), Qt.AlignCenter, str(i + 1)
                )

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
    confirmed = Signal(tuple)       # emit (norm_x0, norm_y0, norm_x1, norm_y1)
    polyline_changed = Signal(list) # emit titik hasil koreksi operator
    polyline_manual_finished = Signal(list) # emit daftar titik ternormalisasi hasil manual drawing
    manual_draw_cancelled = Signal()        # emit saat mode manual dibatalkan

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Toolbar dua baris: petunjuk di atas, kontrol di bawah.
        toolbar = QFrame()
        toolbar.setObjectName("CanvasToolbar")
        tool_outer = QVBoxLayout(toolbar)
        tool_outer.setContentsMargins(12, 8, 12, 8)
        tool_outer.setSpacing(6)

        info_row = QHBoxLayout()
        info_row.setSpacing(12)
        self.info_label = QLabel("Tarik mouse pada denah untuk memilih area bidang tanah.")
        self.info_label.setObjectName("CanvasHint")
        self.info_label.setWordWrap(True)
        info_row.addWidget(self.info_label, 1)

        legend = QLabel(
            "<span style='color:#059669;'>● polyline</span> &nbsp; "
            "<span style='color:#1D4ED8;'>● potongan</span> &nbsp; "
            "<span style='color:#F59E0B;'>● titik aktif</span>"
        )
        legend.setObjectName("CanvasLegend")
        legend.setToolTip("Arti warna pada pratinjau denah")
        info_row.addWidget(legend)
        tool_outer.addLayout(info_row)

        control_row = QHBoxLayout()
        control_row.setSpacing(7)
        for text, tip, slot in [
            ("Perkecil", "Perkecil tampilan halaman PDF", self._on_zoom_out),
            ("Perbesar", "Perbesar tampilan halaman PDF", self._on_zoom_in),
            ("100%", "Kembalikan zoom ke ukuran normal", self._on_zoom_reset),
        ]:
            btn = Button(text, size="sm", tone="secondary", tooltip=tip)
            btn.clicked.connect(slot)
            control_row.addWidget(btn)

        control_row.addStretch()

        self.btn_reset_crop = Button(
            "Ulangi Potongan", size="sm", tone="warn",
            tooltip="Hapus area potongan lalu pilih ulang area denah",
        )
        self.btn_reset_crop.clicked.connect(self._on_reset_crop)
        control_row.addWidget(self.btn_reset_crop)

        self.btn_confirm_crop = Button(
            "Konfirmasi Potongan", size="sm", tone="primary",
            tooltip="Gunakan area denah yang dipilih untuk deteksi polyline",
        )
        self.btn_confirm_crop.setEnabled(False)
        self.btn_confirm_crop.clicked.connect(self._on_confirm_crop)
        control_row.addWidget(self.btn_confirm_crop)
        tool_outer.addLayout(control_row)

        layout.addWidget(toolbar)

        # Scroll Area untuk Preview Gambar
        self.scroll_area = QScrollArea()
        self.scroll_area.setObjectName("PreviewScroll")
        self.scroll_area.setWidgetResizable(False)
        self.scroll_area.setAlignment(Qt.AlignCenter)

        self.canvas = CropInteractiveWidget()
        self.canvas.crop_changed.connect(self._on_crop_changed)
        self.canvas.polyline_changed.connect(self.polyline_changed.emit)
        self.canvas.polyline_manual_finished.connect(self.polyline_manual_finished.emit)
        self.canvas.manual_draw_cancelled.connect(self.manual_draw_cancelled.emit)
        self.scroll_area.setWidget(self.canvas)
        layout.addWidget(self.scroll_area, 1)

    def load_page_image(self, img_bytes: bytes):
        """Memuat gambar halaman ke kanvas."""
        self.canvas.set_image_bytes(img_bytes)
        self.btn_confirm_crop.setEnabled(False)

    def _on_crop_changed(self, has_selection: bool):
        self.btn_confirm_crop.setEnabled(has_selection)
        if has_selection:
            self.info_label.setText("Area dipilih. Klik 'Konfirmasi Potongan' untuk melanjutkan.")
        else:
            self.info_label.setText("Tarik mouse pada denah untuk memilih area bidang tanah.")

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

    def show_polyline(self, points: list):
        """Menampilkan hasil deteksi otomatis di atas halaman PDF."""
        self.canvas.set_polyline(points, editable=True)
        self.info_label.setText(
            "Geser titik hijau untuk koreksi • Klik 2x pada garis untuk tambah titik • Klik kanan pada titik untuk hapus."
        )

    def get_polyline(self) -> list:
        return self.canvas.get_polyline()

    def clear_polyline(self):
        self.canvas.clear_polyline()

    # -----------------------------------------------------------------
    # Mode Titik Manual — API publik untuk halaman digitasi
    # -----------------------------------------------------------------
    @property
    def draw_mode(self) -> bool:
        return self.canvas.draw_mode

    @draw_mode.setter
    def draw_mode(self, value: bool):
        self.canvas.set_draw_mode(bool(value))

    @property
    def manual_points(self) -> list:
        return self.canvas.manual_points

    def has_image(self) -> bool:
        return self.canvas.pixmap is not None

    def start_manual_draw(self):
        """Aktifkan mode gambar polyline manual pada kanvas."""
        self.canvas.clear_polyline()
        self.canvas.set_draw_mode(True)
        self.info_label.setText(
            "Mode Titik Manual: klik pada denah untuk menambah titik, "
            "klik 2x untuk menyegel, Esc untuk membatalkan."
        )

    def cancel_manual_draw(self):
        """Batalkan mode gambar manual."""
        self.canvas.cancel_manual_draw()
        self.info_label.setText("Tarik mouse pada denah untuk memilih area bidang tanah.")

    def finish_manual_polyline(self) -> bool:
        """Segel polyline manual yang sedang digambar (dipanggil dari luar kanvas)."""
        return self.canvas.finish_manual_polyline()
