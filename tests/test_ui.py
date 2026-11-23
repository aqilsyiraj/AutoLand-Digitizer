"""
AutoLand Digitizer - UI Instantiation Test
Memastikan seluruh komponen antarmuka PySide6, tabel, kanvas, dan navigasi berhasil dimuat tanpa error.
"""

import gc
import os
import sys
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

# Jalankan dalam mode offscreen jika headless
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication
from app.main_window import MainWindow
from app.dashboard import DashboardPage
from app.batch_page import BatchPage
from app.queue_page import QueuePage
from app.digitization_page import DigitizationPage
from app.result_page import ResultPage
from app.report_page import ReportPage
from app.settings_page import SettingsPage
from ui.components.stat_card import StatCard
from ui.components.status_badge import StatusBadge
from ui.components.crop_canvas import InteractiveCropCanvas
from config import STATUS_LABELS, STATUS_LIST

class TestUIComponents(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not QApplication.instance():
            cls.app = QApplication([])
        else:
            cls.app = QApplication.instance()

    @classmethod
    def tearDownClass(cls):
        # Tutup jendela dan kosongkan referensi Qt sebelum interpreter selesai.
        for widget in QApplication.topLevelWidgets():
            try:
                widget.close()
            except Exception:
                pass
        cls.app.processEvents()
        gc.collect()
        cls.app.quit()
        cls.app = None

    def test_components(self):
        # StatCard
        card = StatCard("Test Metric", "99", "Sub info")
        self.assertEqual(card.value_label.text(), "99")

        # StatusBadge
        for s in STATUS_LIST:
            badge = StatusBadge(s)
            self.assertEqual(badge.text(), STATUS_LABELS.get(s, s))

        # Crop Canvas
        canvas = InteractiveCropCanvas()
        self.assertIsNotNone(canvas)

    def test_all_pages(self):
        dash = DashboardPage()
        dash.refresh_data()

        batch = BatchPage()
        batch.load_data()

        queue = QueuePage()
        queue.load_data()

        dig = DigitizationPage()
        res = ResultPage()
        res.load_data()

        rep = ReportPage()
        rep.load_batches()

        sett = SettingsPage()

    def test_main_window(self):
        win = MainWindow()
        self.assertEqual(win.stack.count(), 7)
        # Beralih ke setiap tab. Halaman digitasi hanya terbuka jika ada dokumen.
        win.page_digitize.doc_id = -1
        for i in range(7):
            win.switch_page(i)
            self.assertEqual(win.stack.currentIndex(), i)
        win.close()

if __name__ == "__main__":
    unittest.main()
