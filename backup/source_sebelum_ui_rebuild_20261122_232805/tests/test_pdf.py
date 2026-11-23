"""
AutoLand Digitizer - PDF Processing Unit Test
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

import pymupdf
from services.pdf_service import get_pdf_info, render_pdf_page_to_pixmap, crop_pdf_region_to_file
from services.image_service import rotate_image, enhance_image_contrast

class TestPDFService(unittest.TestCase):
    def test_pdf_workflow(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # 1. Buat PDF dummy 2 halaman dengan PyMuPDF
            sample_pdf = os.path.join(tmpdir, "test_denah.pdf")
            doc = pymupdf.open()
            
            # Halaman 1
            p1 = doc.new_page(width=595, height=842) # A4
            p1.draw_rect(pymupdf.Rect(100, 100, 400, 400), color=(0, 0, 1), fill=(0.9, 0.9, 1))
            p1.insert_text((120, 150), "DENAH BIDANG TANAH - TEST PTSL", fontsize=16)
            
            # Halaman 2
            p2 = doc.new_page(width=595, height=842)
            p2.insert_text((100, 100), "Halaman 2 - Uraian", fontsize=12)
            
            doc.save(sample_pdf)
            doc.close()

            # 2. Uji get_pdf_info
            info = get_pdf_info(sample_pdf)
            self.assertTrue(info["success"])
            self.assertEqual(info["page_count"], 2)

            # 3. Uji render_pdf_page_to_pixmap
            pix_bytes = render_pdf_page_to_pixmap(sample_pdf, 1, dpi=100)
            self.assertIsNotNone(pix_bytes)
            self.assertGreater(len(pix_bytes), 500)

            # 4. Uji crop_pdf_region_to_file
            # Koordinat ternormalisasi tengah halaman
            crop_target = os.path.join(tmpdir, "crop_out.png")
            ok_crop, res_path = crop_pdf_region_to_file(
                sample_pdf,
                page_number=1,
                norm_rect=(0.15, 0.1, 0.7, 0.5),
                output_filename="crop_out.png",
                dpi=200
            )
            self.assertTrue(ok_crop)
            self.assertTrue(os.path.exists(res_path))
            self.assertGreater(os.path.getsize(res_path), 500)

            # 5. Uji rotasi dan penyesuaian kontras gambar
            ok_rot, _ = rotate_image(res_path, 90)
            self.assertTrue(ok_rot)

            ok_enh, _ = enhance_image_contrast(res_path, 1.2)
            self.assertTrue(ok_enh)

if __name__ == "__main__":
    unittest.main()
