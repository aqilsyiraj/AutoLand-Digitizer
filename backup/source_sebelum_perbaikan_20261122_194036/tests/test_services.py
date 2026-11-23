"""
AutoLand Digitizer - Comprehensive Unit and Integration Tests
Menguji standarisasi penomoran, rumus scaling, operasi database, ekspor Excel/CSV,
backup/restore, dan integrasi AutoCAD dalam mode simulasi.
"""

import os
import sys
import math
import tempfile
import unittest
from pathlib import Path

# Tambahkan root path proyek
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from config import (
    STATUS_MENUNGGU, STATUS_SELESAI, STATUS_MENUNGGU_TRACING,
    JENIS_HAK_MAP, ensure_directories
)
from services.naming_service import (
    format_document_identity, sanitize_filename, validate_document_input,
    normalize_gs_number, get_awalan_hak
)
from services.geometry_service import (
    calculate_scale_factor, analyze_scaling, verify_final_area
)
from database.db import (
    init_db, create_batch, get_batch, get_all_batches, update_batch,
    delete_batch, create_document, get_document, get_documents_by_batch,
    update_document, delete_document, get_overall_stats, get_batch_stats,
    add_log, get_recent_logs
)
from services.export_service import (
    check_batch_readiness, export_batch_to_excel, export_batch_to_csv, export_batch_to_zip
)
from services.backup_service import (
    create_database_backup, restore_database_backup,
    export_work_package, import_work_package
)
from services.autocad_service import autocad_service

class TestAutoLandDigitizer(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        ensure_directories()
        init_db()

    # 1. TEST IDENTITAS DAN PENOMORAN DOKUMEN
    def test_naming_service_format(self):
        # Contoh di prompt: Hak Milik, nomor hak 1342, GS1152, tahun 1998 -> M. 1342 GS1152/1998
        res = format_document_identity(kode_hak="1", nomor_hak="1342", nomor_gs="1152", tahun="1998")
        self.assertEqual(res, "M. 1342 GS1152/1998")

        # Uji jenis hak lainnya
        # HGB -> B.
        res_hgb = format_document_identity(kode_hak="3", nomor_hak="550", nomor_gs="GS204", tahun="2005")
        self.assertEqual(res_hgb, "B. 550 GS204/2005")

        # Hak Pakai -> P.
        res_hp = format_document_identity(kode_hak="4", nomor_hak="77", nomor_gs="301", tahun="2010")
        self.assertEqual(res_hp, "P. 77 GS301/2010")

        # Wakaf -> W.
        res_wakaf = format_document_identity(kode_hak="8", nomor_hak="12", nomor_gs="GS99", tahun="2020")
        self.assertEqual(res_wakaf, "W. 12 GS99/2020")

    def test_gs_normalization(self):
        # Angka murni -> tambahkan awalan GS
        self.assertEqual(normalize_gs_number("1152"), "GS1152")
        # Sudah ada GS -> pertahankan GS
        self.assertEqual(normalize_gs_number("GS1152"), "GS1152")
        # Ada spasi atau titik -> rapikan
        self.assertEqual(normalize_gs_number("GS. 1152"), "GS1152")
        self.assertEqual(normalize_gs_number("gs 204"), "GS204")

    def test_filename_sanitization(self):
        identity = "M. 1342 GS1152/1998"
        safe_dwg = sanitize_filename(identity, ".dwg")
        # Karakter / dan spasi harus dihilangkan
        self.assertNotIn("/", safe_dwg)
        self.assertNotIn("\\", safe_dwg)
        self.assertNotIn(" ", safe_dwg)
        self.assertTrue(safe_dwg.endswith(".dwg"))
        self.assertEqual(safe_dwg, "M_1342_GS1152_1998.dwg")

    def test_document_input_validation(self):
        # Input valid
        ok, msg = validate_document_input("1", "1342", "GS1152", "1998", 150.0)
        self.assertTrue(ok)
        self.assertEqual(msg, "")

        # Luas negatif atau 0
        ok, msg = validate_document_input("1", "1342", "GS1152", "1998", -10)
        self.assertFalse(ok)

        # Tahun bukan 4 digit
        ok, msg = validate_document_input("1", "1342", "GS1152", "98", 100)
        self.assertFalse(ok)

        # Nomor hak kosong
        ok, msg = validate_document_input("1", "", "GS1152", "1998", 100)
        self.assertFalse(ok)

    # 2. TEST PERHITUNGAN SCALING OTOMATIS
    def test_scale_factor_calculation(self):
        # Contoh di prompt:
        # Luas dokumen: 150 m2, Luas polyline: 100 m2
        # Faktor scaling = sqrt(150/100) = sqrt(1.5) = 1.22474487...
        factor, err = calculate_scale_factor(luas_dokumen=150.0, luas_polyline=100.0)
        self.assertEqual(err, "")
        self.assertAlmostEqual(factor, 1.22474487, places=5)

        # Uji jika sama
        factor_same, _ = calculate_scale_factor(100.0, 100.0)
        self.assertAlmostEqual(factor_same, 1.0, places=5)

        # Uji analisis scaling
        analysis = analyze_scaling(luas_dokumen=150.0, luas_awal_polyline=100.0)
        self.assertTrue(analysis["success"])
        self.assertEqual(analysis["luas_dokumen"], 150.0)
        self.assertEqual(analysis["luas_awal"], 100.0)
        self.assertEqual(analysis["selisih_awal"], 50.0)
        self.assertEqual(analysis["faktor_scaling"], 1.224745)

        # Uji verifikasi akhir
        eval_res = verify_final_area(luas_dokumen=150.0, luas_akhir_polyline=149.99, toleransi_persen=0.5)
        self.assertTrue(eval_res["is_acceptable"])
        self.assertEqual(eval_res["status_evaluasi"], "Sesuai Toleransi")

    # 3. TEST DATABASE CRUD
    def test_database_crud(self):
        # Buat Batch
        batch_id = create_batch(
            nama_desa="Sukamaju",
            kecamatan="Cikarang Barat",
            kabupaten="Bekasi",
            tanggal="2026-11-22",
            operator="Operator 1",
            keterangan="Proyek PTSL 2026"
        )
        self.assertIsInstance(batch_id, int)

        # Baca Batch
        batch = get_batch(batch_id)
        self.assertIsNotNone(batch)
        self.assertEqual(batch["nama_desa"], "Sukamaju")

        # Buat Dokumen dalam Batch
        doc_id = create_document(
            batch_id=batch_id,
            nama_pdf="denah_001.pdf",
            path_pdf="c:/test/denah_001.pdf",
            jenis_hak="Hak Milik",
            kode_hak="1",
            nomor_hak="1342",
            nomor_gs="GS1152",
            tahun="1998",
            identitas_dokumen="M. 1342 GS1152/1998",
            luas_dokumen=150.0,
            status=STATUS_MENUNGGU
        )
        self.assertIsInstance(doc_id, int)

        # Update Dokumen
        update_document(
            doc_id,
            luas_awal=100.0,
            luas_akhir=150.0,
            faktor_scaling=1.224745,
            status=STATUS_SELESAI,
            path_dwg="c:/test/hasil/M_1342_GS1152_1998.dwg"
        )

        doc = get_document(doc_id)
        self.assertEqual(doc["status"], STATUS_SELESAI)
        self.assertEqual(doc["luas_akhir"], 150.0)

        # Uji Statistik Batch
        stats = get_batch_stats(batch_id)
        self.assertEqual(stats["total"], 1)
        self.assertEqual(stats["selesai"], 1)
        self.assertTrue(stats["is_all_completed"])

    # 4. TEST EKSPOR EXCEL & CSV
    def test_export_excel_and_csv(self):
        batch_id = create_batch(
            nama_desa="Telajung",
            kecamatan="Cikarang Barat",
            kabupaten="Bekasi",
            tanggal="2026-11-22"
        )
        create_document(
            batch_id=batch_id,
            nama_pdf="buku_tanah_1.pdf",
            path_pdf="c:/dummy.pdf",
            kode_hak="1",
            nomor_hak="888",
            nomor_gs="GS55",
            tahun="2001",
            identitas_dokumen="M. 888 GS55/2001",
            luas_dokumen=250.0,
            status=STATUS_SELESAI
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            xl_path = os.path.join(tmpdir, "rekap_test.xlsx")
            ok_xl, msg_xl = export_batch_to_excel(batch_id, xl_path)
            self.assertTrue(ok_xl)
            self.assertTrue(os.path.exists(xl_path))
            self.assertGreater(os.path.getsize(xl_path), 1000)

            csv_path = os.path.join(tmpdir, "rekap_test.csv")
            ok_csv, msg_csv = export_batch_to_csv(batch_id, csv_path)
            self.assertTrue(ok_csv)
            self.assertTrue(os.path.exists(csv_path))

            zip_path = os.path.join(tmpdir, "paket_test.zip")
            ok_zip, msg_zip = export_batch_to_zip(batch_id, zip_path)
            self.assertTrue(ok_zip)
            self.assertTrue(os.path.exists(zip_path))

    # 5. TEST CADANGAN & PEMULIHAN DATABASE
    def test_backup_and_restore(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ok_backup, backup_file = create_database_backup(custom_dest_folder=tmpdir)
            self.assertTrue(ok_backup)
            self.assertTrue(os.path.exists(backup_file))

            # Uji restore
            ok_restore, msg_restore = restore_database_backup(backup_file)
            self.assertTrue(ok_restore)

    # 6. TEST AUTOCAD SERVICE SIMULATION
    def test_autocad_simulation_mode(self):
        autocad_service.simulation_mode = True
        ok, msg = autocad_service.connect()
        self.assertTrue(ok)

        status = autocad_service.get_status()
        self.assertTrue(status["connected"])
        self.assertTrue(status["is_simulation"])

        # Uji buka template
        ok_tpl, _ = autocad_service.open_template("c:/test/template.dwg")
        self.assertTrue(ok_tpl)

        # Uji insert raster
        ok_rst, _ = autocad_service.insert_raster_image("c:/test/crop.png")
        self.assertTrue(ok_rst)

        # Uji ambil luas polyline
        autocad_service._sim_polyline_area = 100.0
        ok_poly, area, handle, _ = autocad_service.get_polyline_area()
        self.assertTrue(ok_poly)
        self.assertEqual(area, 100.0)

        # Uji scaling
        ok_scale, final_area, _ = autocad_service.scale_selected_objects(scale_factor=1.224745)
        self.assertTrue(ok_scale)
        self.assertAlmostEqual(final_area, 150.0, places=1)

        # Uji ganti teks
        ok_txt, _ = autocad_service.replace_identity_text("M. 1342 GS1152/1998")
        self.assertTrue(ok_txt)

if __name__ == "__main__":
    unittest.main()
