"""
AutoLand Digitizer - Main Window

Jendela utama desktop: sidebar navigasi yang terstruktur, kartu batch aktif,
indikator koneksi AutoCAD, dan transisi halaman halus berbasis Qt.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from config import APP_NAME, APP_VERSION, APP_SUBTITLE
from database.db import get_batch, get_all_batches, get_setting, set_setting, get_document
from services.autocad_service import autocad_service
from ui.motion.qt_motion import fade_swap, pulse
from ui.styles.style import MAIN_STYLESHEET

from app.dashboard import DashboardPage
from app.batch_page import BatchPage
from app.queue_page import QueuePage
from app.digitization_page import DigitizationPage
from app.result_page import ResultPage
from app.report_page import ReportPage
from app.settings_page import SettingsPage


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.active_batch_id = None
        self._setup_window()
        self._setup_ui()
        self._connect_signals()
        self._initialize_data()

    def _setup_window(self):
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION} — {APP_SUBTITLE}")
        self.resize(1440, 900)
        self.setMinimumSize(1180, 720)
        self.setStyleSheet(MAIN_STYLESHEET)

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        main_layout.addWidget(self._build_sidebar())

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        self.stack = QStackedWidget()
        self.page_dashboard = DashboardPage()
        self.page_batch = BatchPage()
        self.page_queue = QueuePage()
        self.page_digitize = DigitizationPage()
        self.page_result = ResultPage()
        self.page_report = ReportPage()
        self.page_settings = SettingsPage()

        for page in (
            self.page_dashboard,
            self.page_batch,
            self.page_queue,
            self.page_digitize,
            self.page_result,
            self.page_report,
            self.page_settings,
        ):
            self.stack.addWidget(page)

        content_layout.addWidget(self.stack)
        main_layout.addWidget(content, 1)

    def _build_sidebar(self) -> QFrame:
        self.sidebar = QFrame()
        self.sidebar.setObjectName("Sidebar")
        sb = QVBoxLayout(self.sidebar)
        sb.setContentsMargins(0, 0, 0, 12)
        sb.setSpacing(2)

        # ---------- Merek ----------
        header = QFrame()
        header.setObjectName("SidebarHeader")
        h = QHBoxLayout(header)
        h.setContentsMargins(16, 18, 16, 14)
        h.setSpacing(10)

        mark = QLabel("AL")
        mark.setObjectName("BrandMark")
        mark.setAlignment(Qt.AlignCenter)
        mark.setFixedSize(36, 36)
        h.addWidget(mark)

        brand = QVBoxLayout()
        brand.setSpacing(0)
        title = QLabel("AutoLand")
        title.setObjectName("SidebarTitle")
        subtitle = QLabel("Digitizer Pertanahan")
        subtitle.setObjectName("SidebarSubtitle")
        brand.addWidget(title)
        brand.addWidget(subtitle)
        h.addLayout(brand, 1)
        sb.addWidget(header)

        # ---------- Batch aktif ----------
        self.active_batch_card = QFrame()
        self.active_batch_card.setObjectName("ActiveBatchCard")
        abc = QVBoxLayout(self.active_batch_card)
        abc.setContentsMargins(12, 9, 12, 10)
        abc.setSpacing(2)
        tag = QLabel("BATCH AKTIF")
        tag.setObjectName("ActiveBatchLabel")
        tag.setToolTip("Batch aktif dipilih pada menu '2. Batch / Desa'.")
        self.lbl_active_batch_name = QLabel("Belum ada batch dipilih")
        self.lbl_active_batch_name.setObjectName("ActiveBatchValue")
        self.lbl_active_batch_name.setWordWrap(True)
        self.active_batch_card.setToolTip(
            "Batch aktif ditentukan pada menu '2. Batch / Desa'."
        )
        abc.addWidget(tag)
        abc.addWidget(self.lbl_active_batch_name)
        sb.addWidget(self.active_batch_card)

        # ---------- Navigasi ----------
        menus = [
            ("1. Ringkasan", "Lihat progres seluruh pekerjaan."),
            ("2. Batch / Desa", "Buat atau pilih desa tempat dokumen diproses."),
            ("3. PDF && Antrean", "Impor PDF lalu klik 'Proses' pada dokumen."),
            ("4. Proses Digitasi", "Dibuka otomatis setelah memilih dokumen."),
            ("5. Hasil DWG", "Lihat file AutoCAD yang sudah jadi."),
            ("6. Laporan && Ekspor", "Unduh rekap Excel/CSV atau paket ZIP."),
            ("7. Pengaturan", "Template DWG, koneksi AutoCAD 2021, dan cadangan."),
        ]
        group_titles = {0: "ALUR KERJA", 4: "ARSIP & LAPORAN", 6: "SISTEM"}

        self.nav_buttons = []
        for idx, (text, tooltip) in enumerate(menus):
            if idx in group_titles:
                section = QLabel(group_titles[idx])
                section.setObjectName("SidebarSection")
                sb.addWidget(section)
            btn = QPushButton(text)
            btn.setProperty("role", "nav")
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setToolTip(tooltip)
            btn.clicked.connect(lambda checked=False, i=idx: self.switch_page(i))
            sb.addWidget(btn)
            self.nav_buttons.append(btn)

        sb.addStretch()

        # ---------- Status AutoCAD ----------
        self.acad_status_card = QFrame()
        self.acad_status_card.setObjectName("AcadStatusCard")
        asc = QVBoxLayout(self.acad_status_card)
        asc.setContentsMargins(12, 9, 12, 10)
        asc.setSpacing(2)

        acad_head = QHBoxLayout()
        acad_head.setSpacing(6)
        self.lbl_acad_dot = QLabel("●")
        self.lbl_acad_dot.setStyleSheet("color: #64748B; font-size: 9px;")
        self.lbl_acad_dot.setFixedWidth(10)
        acad_head.addWidget(self.lbl_acad_dot)
        acad_title = QLabel("AutoCAD 2021")
        acad_title.setObjectName("AcadStatusLabel")
        acad_head.addWidget(acad_title, 1)
        asc.addLayout(acad_head)

        self.lbl_acad_sidebar = QLabel("Memeriksa koneksi…")
        self.lbl_acad_sidebar.setObjectName("AcadStatusLabel")
        asc.addWidget(self.lbl_acad_sidebar)
        sb.addWidget(self.acad_status_card)

        foot = QLabel(f"v{APP_VERSION}  ·  Offline lokal")
        foot.setObjectName("SidebarFoot")
        foot.setAlignment(Qt.AlignCenter)
        sb.addWidget(foot)

        return self.sidebar

    def _connect_signals(self):
        self.page_dashboard.navigate_to_page.connect(self.switch_page)
        self.page_batch.batch_changed.connect(self.set_active_batch)
        self.page_queue.start_process_doc.connect(self._on_start_digitize_doc)
        self.page_digitize.digitization_completed.connect(self._on_digitization_done)
        self.page_digitize.back_to_queue.connect(lambda: self.switch_page(2))

    def _initialize_data(self):
        batches = get_all_batches()
        initial_batch_id = self._last_open_batch_id(batches)
        self.set_active_batch(initial_batch_id)
        self.switch_page(0)
        self._check_autocad()

    @staticmethod
    def _last_open_batch_id(batches):
        """Mengembalikan batch terakhir yang dipakai, lalu fallback ke yang baru."""
        try:
            stored = str(get_setting("last_active_batch_id", "") or "").strip()
        except Exception:
            stored = ""
        if stored:
            for batch in batches:
                if str(batch.get("id")) == stored:
                    return batch["id"]
        return batches[0]["id"] if batches else None

    def set_active_batch(self, batch_id):
        self.active_batch_id = batch_id
        if batch_id:
            try:
                set_setting("last_active_batch_id", str(batch_id))
            except Exception:
                pass

    def set_active_batch(self, batch_id):
        self.active_batch_id = batch_id
        if batch_id:
            batch = get_batch(batch_id)
            if batch:
                self.lbl_active_batch_name.setText(
                    f"Desa {batch['nama_desa']}\nKec. {batch['kecamatan']}"
                )
                self.page_dashboard.set_active_batch(batch_id)
                self.page_queue.set_active_batch(batch_id)
                self.page_report.set_active_batch(batch_id)
                return

        self.lbl_active_batch_name.setText("Belum ada batch dipilih")
        self.page_dashboard.set_active_batch(None)
        self.page_queue.set_active_batch(None)
        self.page_report.set_active_batch(None)

    def switch_page(self, index: int):
        if index == 3 and not getattr(self.page_digitize, "doc_id", None):
            QMessageBox.information(
                self,
                "Pilih Dokumen Dulu",
                "Buka menu '3. PDF & Antrean', lalu klik 'Proses' pada dokumen yang ingin didigitasi.",
            )
            index = 2

        previous = self.stack.currentWidget()
        target = self.stack.widget(index)
        self.stack.setCurrentIndex(index)
        if previous is not None and previous is not target:
            fade_swap(previous, target, duration=170)

        for i, btn in enumerate(self.nav_buttons):
            btn.setChecked(i == index)

        if index == 0:
            self.page_dashboard.refresh_data()
        elif index == 1:
            self.page_batch.load_data()
        elif index == 2:
            self.page_queue.load_data()
        elif index == 4:
            self.page_result.load_data()
        elif index == 5:
            self.page_report.load_batches()

        self._check_autocad()

    def _on_start_digitize_doc(self, doc_id: int):
        # Saat operator memulai dokumen (Proses), catat batch itu sebagai
        # batch terakhir yang dikerjakan, agar reopen aplikasi mendarahnya ke
        # dokumen yang baru di kerjakan, bukan batch terbaru yang baru dibuat.
        doc = get_document(doc_id)
        if doc and doc.get("batch_id"):
            self.set_active_batch(doc["batch_id"])
        self.page_digitize.load_document(doc_id)
        self.switch_page(3)

    def _on_digitization_done(self, doc_id: int):
        doc = get_document(doc_id)
        if doc and doc.get("batch_id"):
            self.set_active_batch(doc["batch_id"])
        self.page_queue.load_data()
        self.page_dashboard.refresh_data()
        self.page_result.load_data()

    def _check_autocad(self):
        status = autocad_service.get_status()
        connected = bool(status.get("connected"))
        self.lbl_acad_sidebar.setText(
            "Terhubung dan siap" if connected else "Tidak terhubung"
        )
        self.lbl_acad_sidebar.setProperty("tone", "ok" if connected else "off")
        self.lbl_acad_dot.setStyleSheet(
            "color: #34D399; font-size: 9px;"
            if connected
            else "color: #64748B; font-size: 9px;"
        )
        self.lbl_acad_sidebar.style().unpolish(self.lbl_acad_sidebar)
        self.lbl_acad_sidebar.style().polish(self.lbl_acad_sidebar)
        self.lbl_acad_sidebar.setToolTip(
            status.get("version") or status.get("error") or "AutoCAD Desktop 2021"
        )
        if connected and not getattr(self, "_acad_was_connected", False):
            pulse(self.lbl_acad_sidebar, cycles=1)
        self._acad_was_connected = connected
