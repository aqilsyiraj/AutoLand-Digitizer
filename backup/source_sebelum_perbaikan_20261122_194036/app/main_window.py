"""
AutoLand Digitizer - Main Window
Jendela utama desktop Windows dengan navigasi sidebar profesional,
sinkronisasi batch aktif, indikator AutoCAD, dan integrasi antar halaman.
"""

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QStackedWidget, QFrame, QMessageBox, QApplication
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon, QFont

from config import APP_NAME, APP_VERSION, APP_SUBTITLE
from database.db import get_batch, get_all_batches
from services.autocad_service import autocad_service
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
        self.resize(1300, 820)
        self.setMinimumSize(1060, 700)
        self.setStyleSheet(MAIN_STYLESHEET)

    def _setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ==================== SIDEBAR KIRI ====================
        self.sidebar = QFrame()
        self.sidebar.setObjectName("Sidebar")
        sb_layout = QVBoxLayout(self.sidebar)
        sb_layout.setContentsMargins(0, 0, 0, 16)
        sb_layout.setSpacing(4)

        # Header Sidebar
        sb_header = QFrame()
        sb_header.setObjectName("SidebarHeader")
        sbh_layout = QVBoxLayout(sb_header)
        sbh_layout.setContentsMargins(18, 18, 18, 16)
        sbh_layout.setSpacing(4)

        lbl_logo = QLabel("📐 AutoLand")
        lbl_logo.setObjectName("SidebarTitle")
        sbh_layout.addWidget(lbl_logo)

        lbl_desc = QLabel("Digitizer Pertanahan")
        lbl_desc.setObjectName("SidebarSubtitle")
        sbh_layout.addWidget(lbl_desc)

        sb_layout.addWidget(sb_header)

        # Active Batch Card
        self.active_batch_card = QFrame()
        self.active_batch_card.setObjectName("ActiveBatchCard")
        abc_layout = QVBoxLayout(self.active_batch_card)
        abc_layout.setContentsMargins(12, 10, 12, 10)
        abc_layout.setSpacing(2)

        lbl_ab_tag = QLabel("BATCH AKTIF")
        lbl_ab_tag.setObjectName("ActiveBatchLabel")
        abc_layout.addWidget(lbl_ab_tag)

        self.lbl_active_batch_name = QLabel("Belum Ada Batch")
        self.lbl_active_batch_name.setObjectName("ActiveBatchValue")
        self.lbl_active_batch_name.setWordWrap(True)
        abc_layout.addWidget(self.lbl_active_batch_name)

        sb_layout.addWidget(self.active_batch_card)

        # Sidebar Menu Buttons
        self.nav_buttons = []
        menus = [
            ("📊 Dashboard", 0),
            ("📁 Batch Pekerjaan", 1),
            ("📋 Antrean Dokumen", 2),
            ("⚡ Proses Digitasi", 3),
            ("🏆 Hasil Digitasi", 4),
            ("📈 Rekapitulasi", 5),
            ("⚙️ Pengaturan", 6),
        ]

        for title, idx in menus:
            btn = QPushButton(title)
            btn.setProperty("class", "sidebar-btn")
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked=False, i=idx: self.switch_page(i))
            sb_layout.addWidget(btn)
            self.nav_buttons.append(btn)

        sb_layout.addStretch()

        # AutoCAD Connection Status Bar di Bagian Bawah Sidebar
        self.acad_status_card = QFrame()
        self.acad_status_card.setStyleSheet("""
            background-color: #1E293B;
            border-radius: 8px;
            padding: 8px 12px;
            margin: 12px;
            border: 1px solid #334155;
        """)
        asc_layout = QVBoxLayout(self.acad_status_card)
        asc_layout.setContentsMargins(4, 4, 4, 4)
        asc_layout.setSpacing(4)

        self.lbl_acad_sidebar = QLabel("AutoCAD: Memeriksa...")
        self.lbl_acad_sidebar.setStyleSheet("color: #38BDF8; font-size: 11px; font-weight: 700;")
        asc_layout.addWidget(self.lbl_acad_sidebar)
        sb_layout.addWidget(self.acad_status_card)

        main_layout.addWidget(self.sidebar)

        # ==================== KONTEN UTAMA (STACKED WIDGET) ====================
        content_container = QWidget()
        content_layout = QVBoxLayout(content_container)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # Stacked Pages
        self.stack = QStackedWidget()

        self.page_dashboard = DashboardPage()
        self.page_batch = BatchPage()
        self.page_queue = QueuePage()
        self.page_digitize = DigitizationPage()
        self.page_result = ResultPage()
        self.page_report = ReportPage()
        self.page_settings = SettingsPage()

        self.stack.addWidget(self.page_dashboard) # 0
        self.stack.addWidget(self.page_batch)     # 1
        self.stack.addWidget(self.page_queue)     # 2
        self.stack.addWidget(self.page_digitize)  # 3
        self.stack.addWidget(self.page_result)    # 4
        self.stack.addWidget(self.page_report)    # 5
        self.stack.addWidget(self.page_settings)  # 6

        content_layout.addWidget(self.stack)
        main_layout.addWidget(content_container, 1)

    def _connect_signals(self):
        # Navigasi dari dashboard
        self.page_dashboard.navigate_to_page.connect(self.switch_page)

        # Saat batch berubah dari halaman Batch
        self.page_batch.batch_changed.connect(self.set_active_batch)

        # Mulai digitasi dokumen dari halaman antrean
        self.page_queue.start_process_doc.connect(self._on_start_digitize_doc)

        # Saat dokumen selesai didigitasi
        self.page_digitize.digitization_completed.connect(self._on_digitization_done)

        # Tombol kembali ke antrean dari halaman digitasi
        self.page_digitize.back_to_queue.connect(lambda: self.switch_page(2))

    def _initialize_data(self):
        batches = get_all_batches()
        if batches:
            self.set_active_batch(batches[0]["id"])
        else:
            self.set_active_batch(None)

        self.switch_page(0)
        self._check_autocad()

    def set_active_batch(self, batch_id):
        self.active_batch_id = batch_id
        if batch_id:
            b = get_batch(batch_id)
            if b:
                self.lbl_active_batch_name.setText(f"Desa {b['nama_desa']}\n({b['kecamatan']})")
                self.page_dashboard.set_active_batch(batch_id)
                self.page_queue.set_active_batch(batch_id)
                self.page_report.set_active_batch(batch_id)
                return

        self.lbl_active_batch_name.setText("Tidak Ada Batch Aktif")
        self.page_dashboard.set_active_batch(None)
        self.page_queue.set_active_batch(None)
        self.page_report.set_active_batch(None)

    def switch_page(self, index: int):
        self.stack.setCurrentIndex(index)
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
        self.page_digitize.load_document(doc_id)
        self.switch_page(3)

    def _on_digitization_done(self, doc_id: int):
        self.page_queue.load_data()
        self.page_dashboard.refresh_data()
        self.page_result.load_data()

    def _check_autocad(self):
        status = autocad_service.get_status()
        if status["connected"]:
            self.lbl_acad_sidebar.setText("● AutoCAD: Terhubung")
            self.lbl_acad_sidebar.setStyleSheet("color: #10B981; font-size: 11px; font-weight: 700;")
        elif status["is_simulation"]:
            self.lbl_acad_sidebar.setText("● AutoCAD: Mode Simulasi")
            self.lbl_acad_sidebar.setStyleSheet("color: #F59E0B; font-size: 11px; font-weight: 700;")
        else:
            self.lbl_acad_sidebar.setText("○ AutoCAD: Offline")
            self.lbl_acad_sidebar.setStyleSheet("color: #94A3B8; font-size: 11px; font-weight: 700;")
