"""
AutoLand Digitizer - Main Window
Jendela utama desktop Windows dengan navigasi sidebar profesional,
sinkronisasi batch aktif, indikator AutoCAD, dan integrasi antar halaman.
"""

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QStackedWidget, QFrame, QMessageBox, QApplication
)
from PySide6.QtCore import Qt

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
        self.resize(1480, 920)
        self.setMinimumSize(1280, 720)
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
        sb_layout.setContentsMargins(0, 0, 0, 10)
        sb_layout.setSpacing(2)

        # Header Sidebar
        sb_header = QFrame()
        sb_header.setObjectName("SidebarHeader")
        sbh_layout = QVBoxLayout(sb_header)
        sbh_layout.setContentsMargins(14, 12, 14, 10)
        sbh_layout.setSpacing(2)

        lbl_logo = QLabel("AutoLand")
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
        abc_layout.setContentsMargins(10, 8, 10, 8)
        abc_layout.setSpacing(1)

        lbl_ab_tag = QLabel("BATCH AKTIF")
        lbl_ab_tag.setObjectName("ActiveBatchLabel")
        lbl_ab_tag.setToolTip("Batch aktif dipilih pada menu '2. Batch / Desa'.")
        abc_layout.addWidget(lbl_ab_tag)

        self.lbl_active_batch_name = QLabel("Belum ada batch dipilih")
        self.lbl_active_batch_name.setObjectName("ActiveBatchValue")
        self.lbl_active_batch_name.setWordWrap(True)
        self.active_batch_card.setToolTip("Batch aktif ditentukan pada menu '2. Batch / Desa'.")
        abc_layout.addWidget(self.lbl_active_batch_name)

        sb_layout.addWidget(self.active_batch_card)

        lbl_menu_section = QLabel("ALUR KERJA / MENU UTAMA")
        lbl_menu_section.setObjectName("SidebarSection")
        sb_layout.addWidget(lbl_menu_section)

        # Sidebar Menu Buttons
        self.nav_buttons = []
        menus = [
            ("1. Ringkasan", 0, "Lihat progres seluruh pekerjaan."),
            ("2. Batch / Desa", 1, "Buat atau pilih desa tempat dokumen diproses."),
            ("3. PDF & Antrean", 2, "Import PDF lalu klik tombol biru 'Proses' pada dokumen."),
            ("4. Proses Digitasi", 3, "Dibuka otomatis dari menu 3 setelah memilih dokumen."),
            ("5. Hasil DWG", 4, "Lihat file AutoCAD yang sudah jadi."),
            ("6. Laporan & Ekspor", 5, "Unduh rekap Excel/CSV atau paket ZIP."),
            ("7. Pengaturan", 6, "Template DWG, koneksi AutoCAD 2021, dan cadangan data."),
        ]

        for title, idx, tooltip in menus:
            btn = QPushButton(title)
            btn.setProperty("class", "sidebar-btn")
            btn.setCheckable(True)
            btn.setToolTip(tooltip)
            btn.clicked.connect(lambda checked=False, i=idx: self.switch_page(i))
            sb_layout.addWidget(btn)
            self.nav_buttons.append(btn)

        sb_layout.addStretch()

        # AutoCAD Connection Status Bar di Bagian Bawah Sidebar
        self.acad_status_card = QFrame()
        self.acad_status_card.setObjectName("AcadStatusCard")
        asc_layout = QVBoxLayout(self.acad_status_card)
        asc_layout.setContentsMargins(10, 8, 10, 8)
        asc_layout.setSpacing(4)

        self.lbl_acad_sidebar = QLabel("AutoCAD: Memeriksa...")
        self.lbl_acad_sidebar.setObjectName("AcadStatusLabel")
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

        self.lbl_active_batch_name.setText("Belum ada batch dipilih")
        self.page_dashboard.set_active_batch(None)
        self.page_queue.set_active_batch(None)
        self.page_report.set_active_batch(None)

    def switch_page(self, index: int):
        if index == 3 and not getattr(self.page_digitize, "doc_id", None):
            QMessageBox.information(
                self, "Pilih Dokumen Dulu",
                "Buka menu '3. PDF & Antrean', lalu klik tombol 'Proses' pada dokumen yang ingin didigitasi."
            )
            index = 2
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
        connected = bool(status.get("connected"))
        self.lbl_acad_sidebar.setText(
            "● AutoCAD: Terhubung" if connected else "○ AutoCAD: Offline"
        )
        self.lbl_acad_sidebar.setProperty("tone", "ok" if connected else "off")
        self.lbl_acad_sidebar.style().unpolish(self.lbl_acad_sidebar)
        self.lbl_acad_sidebar.style().polish(self.lbl_acad_sidebar)
        self.lbl_acad_sidebar.setToolTip(
            status.get("version") or status.get("error") or "AutoCAD Desktop 2021"
        )
