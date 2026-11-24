"""
AutoLand Digitizer - Pengujian otomatis (isolated test database).

Pengujian ini sengaja memakai folder temporari agar data produksi
di data/autoland.db tidak pernah berubah saat menjalankan test.
"""

import importlib
import os
import sys
import math
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

import config

# --- Isolasi seluruh path sebelum modul lain diimpor ---
TEST_ROOT = Path(tempfile.mkdtemp(prefix="autoland_test_"))
config.DB_PATH = TEST_ROOT / "data" / "autoland_test.db"
config.DATA_DIR = TEST_ROOT / "data"
config.DOKUMEN_MASUK_DIR = TEST_ROOT / "dokumen_masuk"
config.TEMPORARY_DIR = TEST_ROOT / "temporary"
config.HASIL_DIGITASI_DIR = TEST_ROOT / "hasil_digitasi"
config.BACKUP_DIR = TEST_ROOT / "backup"
config.LOGS_DIR = TEST_ROOT / "logs"
config.TEMPLATE_DIR = TEST_ROOT / "template"
config.LOG_FILE_PATH = config.LOGS_DIR / "autoland_activity.log"
config.ensure_directories()

from config import (
    STATUS_MENUNGGU, STATUS_SELESAI, STATUS_LABELS,
)
from services.naming_service import (
    format_document_identity, sanitize_filename, validate_document_input,
    normalize_gs_number,
)
from services.geometry_service import (
    calculate_scale_factor, analyze_scaling, verify_final_area,
)
import database.db as db
from database.db import (
    init_db, create_batch, get_batch, update_document, get_document,
    get_batch_stats, save_detection_result,
    get_detection_candidates,
)
import services.pdf_service as pdf_service
import services.export_service as export_service
import services.backup_service as backup_service
from services.export_service import (
    check_batch_readiness, export_batch_to_excel, export_batch_to_csv, export_batch_to_zip,
)
from services.backup_service import (
    create_database_backup, restore_database_backup,
    export_work_package, import_work_package,
)
from services.detection_service import (
    polygon_area, detect_polylines_from_array, write_coordinate_files,
)
autocad_module = importlib.import_module("services.autocad_service")
from services.autocad_service import autocad_service

# Samakan konstanta modul yang diimpor dengan path test.
db.DB_PATH = config.DB_PATH
pdf_service.TEMPORARY_DIR = config.TEMPORARY_DIR
export_service.HASIL_DIGITASI_DIR = config.HASIL_DIGITASI_DIR
backup_service.DB_PATH = config.DB_PATH
backup_service.BACKUP_DIR = config.BACKUP_DIR
backup_service.DATA_DIR = config.DATA_DIR
backup_service.DOKUMEN_MASUK_DIR = config.DOKUMEN_MASUK_DIR
backup_service.HASIL_DIGITASI_DIR = config.HASIL_DIGITASI_DIR
backup_service.TEMPORARY_DIR = config.TEMPORARY_DIR


# --- Fake COM untuk menguji kode AutoCAD asli tanpa membuka AutoCAD ----------
class FakePolyline:
    _next_handle = 1

    def __init__(self, coords):
        self.ObjectName = "AcDbPolyline"
        self.Closed = False
        self.Layer = "0"
        self.Handle = f"FAKE_POLY_{FakePolyline._next_handle}"
        FakePolyline._next_handle += 1
        self._coords = [(float(x), float(y)) for x, y in coords]
        self.Area = 0.0
        self.update_count = 0
        self.deleted = False
        self.model_space = None
        self._recalculate()

    def _recalculate(self):
        total = 0.0
        for i, (x1, y1) in enumerate(self._coords):
            x2, y2 = self._coords[(i + 1) % len(self._coords)]
            total += x1 * y2 - x2 * y1
        self.Area = abs(total) / 2.0

    @property
    def Coordinates(self):
        flat = []
        for x, y in self._coords:
            flat.extend([float(x), float(y)])
        return flat

    def GetBoundingBox(self):
        xs = [x for x, _ in self._coords]
        ys = [y for _, y in self._coords]
        return ((min(xs), min(ys), 0.0), (max(xs), max(ys), 0.0))

    def Update(self):
        self.update_count += 1

    def Move(self, point1, point2):
        dx = float(point2[0]) - float(point1[0])
        dy = float(point2[1]) - float(point1[1])
        self._coords = [(x + dx, y + dy) for x, y in self._coords]

    def Delete(self):
        self.deleted = True
        if self.model_space is not None:
            self.model_space.remove_entity(self)

    def ScaleEntity(self, base_point, scale_factor):
        bx, by = float(base_point[0]), float(base_point[1])
        factor = float(scale_factor)
        self._coords = [
            (bx + (x - bx) * factor, by + (y - by) * factor)
            for x, y in self._coords
        ]
        self._recalculate()


class FakeRaster:
    _next_handle = 1

    def __init__(self, image_path="", scale=1.0, rotation=0.0, point=(0.0, 0.0, 0.0)):
        self.ObjectName = "AcDbRasterImage"
        self.Handle = f"FAKE_RASTER_{FakeRaster._next_handle}"
        FakeRaster._next_handle += 1
        self.image_path = image_path
        self.ImageFile = image_path
        self.insert_point = (float(point[0]), float(point[1]))
        self.initial_scale = scale
        self.rotation = rotation
        self.ScaleFactor = float(scale)
        self.ImageWidth = 100.0
        self.ImageHeight = 100.0
        self.Layer = "0"
        self.scale_factors = []
        self.deleted = False
        self.model_space = None

    def GetBoundingBox(self):
        x, y = self.insert_point
        return (
            (x, y, 0.0),
            (x + self.ImageWidth, y + self.ImageHeight, 0.0),
        )

    def Move(self, point1, point2):
        dx = float(point2[0]) - float(point1[0])
        dy = float(point2[1]) - float(point1[1])
        self.insert_point = (self.insert_point[0] + dx, self.insert_point[1] + dy)

    def Delete(self):
        self.deleted = True
        if self.model_space is not None:
            self.model_space.remove_entity(self)

    def ScaleEntity(self, base_point, scale_factor):
        bx, by = float(base_point[0]), float(base_point[1])
        factor = float(scale_factor)
        x, y = self.insert_point
        self.insert_point = (bx + (x - bx) * factor, by + (y - by) * factor)
        self.ImageWidth *= factor
        self.ImageHeight *= factor
        self.scale_factors.append(scale_factor)
        self.ScaleFactor *= factor

    def Update(self):
        return True


class FakeText:
    _next_handle = 1

    def __init__(self, text=""):
        self.ObjectName = "AcDbText"
        self.Handle = f"FAKE_TEXT_{FakeText._next_handle}"
        FakeText._next_handle += 1
        self.TextString = text
        self.Height = 3.0
        self.Layer = "0"
        self.AttachmentPoint = 1
        self.InsertionPoint = (0.0, 0.0, 0.0)
        self.update_count = 0
        self.deleted = False
        self.model_space = None

    def GetBoundingBox(self):
        lines = self.TextString.replace("\\P", "\n").split("\n")
        width = max((len(line) for line in lines), default=1) * self.Height * 0.65
        height = max(1, len(lines)) * self.Height * 1.25
        x, y, _ = self.InsertionPoint
        if int(self.AttachmentPoint) == 5:
            return (
                (x - width / 2, y - height / 2, 0.0),
                (x + width / 2, y + height / 2, 0.0),
            )
        return ((x, y - height, 0.0), (x + width, y, 0.0))

    def Move(self, point1, point2):
        dx = float(point2[0]) - float(point1[0])
        dy = float(point2[1]) - float(point1[1])
        x, y, z = self.InsertionPoint
        self.InsertionPoint = (x + dx, y + dy, z)

    def Delete(self):
        self.deleted = True
        if self.model_space is not None:
            self.model_space.remove_entity(self)

    def Update(self):
        self.update_count += 1


class FakeModelSpace(list):
    def __init__(self):
        super().__init__()
        self.rasters = []
        self.polylines = []
        self.labels = []

    def _register(self, obj):
        obj.model_space = self
        self.append(obj)
        return obj

    def remove_entity(self, obj):
        if obj in self:
            self.remove(obj)
        for bucket in (self.rasters, self.polylines, self.labels):
            if obj in bucket:
                bucket.remove(obj)

    def AddRaster(self, image_path, point, scale, rotation):
        obj = FakeRaster(image_path, scale, rotation, point)
        self.rasters.append(obj)
        return self._register(obj)

    def AddLightWeightPolyline(self, variant):
        flat = [float(v) for v in variant]
        coords = list(zip(flat[0::2], flat[1::2]))
        obj = FakePolyline(coords)
        self.polylines.append(obj)
        return self._register(obj)

    def AddMText(self, point, width, text):
        obj = FakeText(text)
        obj.ObjectName = "AcDbMText"
        obj.InsertionPoint = point
        obj.Width = width
        self.labels.append(obj)
        return self._register(obj)

    def find_by_handle(self, handle):
        for obj in self:
            if str(getattr(obj, "Handle", "")) == str(handle):
                return obj
        return None


class FakeLayers:
    def Add(self, name):
        return None


class FakeDocument:
    def __init__(self, name="SMOKE_TEST.dwg", full_name=""):
        self.Name = name
        self.FullName = full_name or str(TEST_ROOT / name)
        self.ModelSpace = FakeModelSpace()
        self.Layers = FakeLayers()
        self.saved_path = ""
        self.closed = False
        self.documents = None

    def Activate(self):
        return True

    def Close(self, save_changes=False):
        self.closed = True
        if self.documents is not None:
            self.documents.remove_doc(self)

    def HandleToObject(self, handle):
        obj = self.ModelSpace.find_by_handle(handle)
        if obj is None:
            raise KeyError(handle)
        return obj

    def SaveAs(self, path):
        self.saved_path = path
        self.FullName = path
        Path(path).write_text("AC1032AUTOLANDTESTDWG", encoding="utf-8")

    def Save(self):
        self.saved_path = self.FullName
        Path(self.FullName).write_text("AC1032AUTOLANDTESTDWG", encoding="utf-8")
        return True


class FakeDocuments:
    def __init__(self, documents):
        self._docs = list(documents)
        self.active = self._docs[0] if self._docs else None
        self.owner = None
        for doc in self._docs:
            doc.documents = self

    @property
    def Count(self):
        return len(self._docs)

    def Item(self, index):
        return self._docs[int(index)]

    def __iter__(self):
        return iter(self._docs)

    def _set_active(self, doc):
        self.active = doc
        if self.owner is not None:
            self.owner.ActiveDocument = doc
        return doc

    def Add(self):
        doc = FakeDocument(f"Drawing{len(self._docs) + 1}.dwg")
        doc.documents = self
        self._docs.append(doc)
        return self._set_active(doc)

    def Open(self, path):
        doc = FakeDocument(Path(path).name, str(path))
        doc.documents = self
        self._docs.append(doc)
        return self._set_active(doc)

    def remove_doc(self, doc):
        if doc in self._docs:
            self._docs.remove(doc)
        if self.active is doc:
            self._set_active(self._docs[-1] if self._docs else None)

    def Close(self, doc):
        self.remove_doc(doc)


class FakeAutoCAD:
    def __init__(self, documents):
        if isinstance(documents, FakeDocument):
            documents = [documents]
        self.Documents = FakeDocuments(documents)
        self.Documents.owner = self
        self.ActiveDocument = self.Documents.active
        self.Visible = False
        self.WindowState = 0
        self.Caption = "AutoCAD 2021 Test"

    def ZoomExtents(self):
        return True


class TestAutoLandDigitizer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    # 1. IDENTITAS & PENOMORAN -------------------------------------------------
    def test_naming_service(self):
        self.assertEqual(
            format_document_identity("1", "1342", "1152", "1998"),
            "M. 1342 GS1152/1998",
        )
        self.assertEqual(
            format_document_identity("3", "550", "GS204", "2005"),
            "B. 550 GS204/2005",
        )
        self.assertEqual(normalize_gs_number("gs 204"), "GS204")
        self.assertEqual(
            sanitize_filename("M. 1342 GS1152/1998", ".dwg"),
            "M_1342_GS1152_1998.dwg",
        )
        ok, _ = validate_document_input("1", "1342", "GS1152", "1998", 150.0)
        self.assertTrue(ok)
        ok, _ = validate_document_input("1", "", "GS1152", "1998", 150.0)
        self.assertFalse(ok)

    # 2. GEOMETRI & SCALING ----------------------------------------------------
    def test_scaling(self):
        factor, err = calculate_scale_factor(150.0, 100.0)
        self.assertEqual(err, "")
        self.assertAlmostEqual(factor, math.sqrt(1.5), places=6)

        analysis = analyze_scaling(150.0, 100.0)
        self.assertTrue(analysis["success"])
        self.assertAlmostEqual(analysis["faktor_scaling"], 1.224745, places=5)

        evaluated = verify_final_area(150.0, 149.99, toleransi_persen=0.5)
        self.assertTrue(evaluated["is_acceptable"])

    # 3. DATABASE & MIGRASI ----------------------------------------------------
    def test_database_crud_and_migration(self):
        batch_id = create_batch(
            nama_desa="Sukamaju", kecamatan="Cikarang Barat",
            kabupaten="Bekasi", tanggal="2026-11-22", operator="Operator 1",
        )
        self.assertIsInstance(batch_id, int)
        self.assertEqual(get_batch(batch_id)["nama_desa"], "Sukamaju")

        doc_id = db.create_document(
            batch_id=batch_id,
            nama_pdf="denah_001.pdf",
            path_pdf="c:/test/denah_001.pdf",
            kode_hak="1",
            nomor_hak="1342",
            nomor_gs="GS1152",
            tahun="1998",
            identitas_dokumen="M. 1342 GS1152/1998",
            luas_dokumen=150.0,
            status=STATUS_MENUNGGU,
        )
        update_document(doc_id, status=STATUS_SELESAI, luas_akhir=150.0)
        self.assertEqual(get_document(doc_id)["status"], STATUS_SELESAI)
        self.assertEqual(get_batch_stats(batch_id)["selesai"], 1)
        self.assertEqual(STATUS_LABELS[STATUS_SELESAI], "Selesai")

        # Migrasi database lama: kolom baru harus ditambahkan tanpa menghapus data.
        legacy_path = TEST_ROOT / "legacy.db"
        conn = sqlite3.connect(str(legacy_path))
        conn.execute("""CREATE TABLE documents (
            id INTEGER PRIMARY KEY, batch_id INTEGER, nama_pdf TEXT, path_pdf TEXT,
            status TEXT)""")
        conn.execute("INSERT INTO documents VALUES (1, 1, 'lama.pdf', 'c:/lama.pdf', 'MENUNGGU')")
        conn.commit()
        cursor = conn.cursor()
        db._migrate_documents_table(cursor)
        conn.commit()
        columns = {row[1] for row in cursor.execute("PRAGMA table_info(documents)")}
        conn.close()
        self.assertIn("detected_vertices_json", columns)
        self.assertIn("koordinat_csv", columns)

    # 4. DETEKSI POLYLINE OFFLINE & KOORDINAT ---------------------------------
    def test_detection_and_coordinate_export(self):
        import cv2
        import numpy as np

        self.assertAlmostEqual(
            polygon_area([(0, 0), (4, 0), (4, 3), (0, 3)]), 12.0
        )

        image = np.full((500, 500, 3), 255, dtype=np.uint8)
        polygon = np.array([[80, 100], [420, 110], [430, 390], [70, 400]], dtype=np.int32)
        cv2.polylines(image, [polygon], isClosed=True, color=(0, 0, 0), thickness=5)
        result = detect_polylines_from_array(image)
        self.assertTrue(result["success"], result["message"])
        self.assertGreaterEqual(result["candidates"][0]["vertex_count"], 4)
        self.assertGreater(result["candidates"][0]["confidence"], 0.3)

        cand = result["candidates"][0]
        batch_id = create_batch(
            nama_desa="Deteksi", kecamatan="Uji", kabupaten="Test",
            tanggal="2026-11-22",
        )
        doc_id = db.create_document(
            batch_id=batch_id, nama_pdf="deteksi.pdf", path_pdf="c:/deteksi.pdf",
            luas_dokumen=1000.0, status=STATUS_MENUNGGU,
        )
        save_detection_result(
            doc_id, [cand], selected_index=0,
            crop_box=(0.0, 0.0, 1.0, 1.0), luas_dokumen=1000.0,
        )
        saved = get_document(doc_id)
        self.assertEqual(saved["status"], "TERDETEKSI")
        self.assertGreater(saved["scale_m_per_px"], 0)
        self.assertEqual(len(get_detection_candidates(doc_id)), 1)

        out_dir = TEST_ROOT / "koordinat_test"
        coords = write_coordinate_files(
            out_dir, "M. 1342 GS1152/1998",
            [(0, 0), (100, 0), (100, 100), (0, 100)],
            image_width=100, image_height=100,
            luas_dokumen=1000.0, area_px=10000.0,
            method="test", confidence=0.9,
        )
        self.assertTrue(os.path.exists(coords["csv"]))
        self.assertTrue(os.path.exists(coords["json"]))
        self.assertAlmostEqual(coords["scale_m_per_px"], math.sqrt(0.1), places=6)

    # 5. EKSPOR ---------------------------------------------------------------
    def test_export_excel_csv_zip(self):
        batch_id = create_batch(
            nama_desa="Telajung", kecamatan="Weru", kabupaten="Bondowoso",
            tanggal="2026-11-22",
        )
        doc_id = db.create_document(
            batch_id=batch_id, nama_pdf="buku_tanah_1.pdf",
            path_pdf="c:/dummy.pdf", kode_hak="1", nomor_hak="888",
            nomor_gs="GS55", tahun="2001",
            identitas_dokumen="M. 888 GS55/2001",
            luas_dokumen=250.0, status=STATUS_SELESAI,
        )
        update_document(doc_id, luas_akhir=250.0, faktor_scaling=1.0)
        dwg_path = TEST_ROOT / "dummy.dwg"
        dwg_path.write_text("AUTOLAND_SIMULATED_DWG", encoding="utf-8")
        coord_path = TEST_ROOT / "Koordinat_M_888_GS55_2001.csv"
        coord_path.write_text("No;X_piksel;Y_piksel\n1;0;0\n", encoding="utf-8")
        update_document(doc_id, path_dwg=str(dwg_path), koordinat_csv=str(coord_path))

        self.assertTrue(check_batch_readiness(batch_id)["is_ready"])
        with tempfile.TemporaryDirectory() as tmp:
            xlsx = Path(tmp) / "rekap.xlsx"
            ok, msg = export_batch_to_excel(batch_id, str(xlsx))
            self.assertTrue(ok, msg)
            self.assertGreater(xlsx.stat().st_size, 1000)

            csv_file = Path(tmp) / "rekap.csv"
            ok, msg = export_batch_to_csv(batch_id, str(csv_file))
            self.assertTrue(ok, msg)
            self.assertIn("M. 888 GS55/2001", csv_file.read_text(encoding="utf-8-sig"))

            zip_file = Path(tmp) / "paket.zip"
            ok, msg = export_batch_to_zip(batch_id, str(zip_file))
            self.assertTrue(ok, msg)

            pkg_zip = Path(tmp) / "paket_kerja.zip"
            ok, msg = export_work_package(batch_id, str(pkg_zip))
            self.assertTrue(ok, msg)
            ok, msg = import_work_package(str(pkg_zip))
            self.assertTrue(ok, msg)

    # 6. BACKUP & RESTORE ------------------------------------------------------
    def test_backup_restore(self):
        ok, backup_file = create_database_backup()
        self.assertTrue(ok, backup_file)
        ok, msg = restore_database_backup(backup_file)
        self.assertTrue(ok, msg)

    # 7. AUTOCAD OTOMASI ASLI (FAKE COM) --------------------------------------
    def test_autocad_automation_with_fake_com(self):
        """Menguji jalur COM asli tanpa mode simulasi dan tanpa AutoCAD terbuka."""
        from PIL import Image

        image_path = TEST_ROOT / "denah_uji.png"
        Image.new("RGB", (100, 100), "white").save(image_path)

        original_variant_double = autocad_module.to_variant_double_array
        original_variant_point = autocad_module.to_variant_point
        original_connect = autocad_service.connect

        autocad_module.to_variant_double_array = lambda values: [float(v) for v in values]
        autocad_module.to_variant_point = lambda x, y, z=0.0: (float(x), float(y), float(z))

        startup_doc = FakeDocument("Drawing1.dwg")
        extra_doc = FakeDocument("Drawing2.dwg")
        fake_acad = FakeAutoCAD([startup_doc, extra_doc])
        autocad_service._last_saved_doc = None
        autocad_service._last_saved_path = ""

        def fake_connect(launch_if_closed=True):
            autocad_service.acad = fake_acad
            autocad_service.doc = fake_acad.ActiveDocument
            autocad_service.is_connected = True
            autocad_service.version_string = "AutoCAD 2021 Test"
            autocad_service._sync_after_connect()
            return True, "Fake COM terhubung"

        autocad_service.connect = fake_connect

        try:
            # Koneksi harus menutup gambar kosong tambahan, bukan menambah Drawing2.
            ok, msg = autocad_service.connect()
            self.assertTrue(ok, msg)
            self.assertEqual(fake_acad.Documents.Count, 1)
            self.assertIs(autocad_service.doc, startup_doc)

            ok, msg = autocad_service.create_new_drawing()
            self.assertTrue(ok, msg)
            self.assertEqual(fake_acad.Documents.Count, 1)
            self.assertIs(autocad_service.doc, startup_doc)
            self.assertFalse(startup_doc.closed)

            status = autocad_service.get_status()
            self.assertTrue(status["connected"])
            self.assertNotIn("is_simulation", status)
            self.assertIn("2021", status["version"])

            autocad_service._active_raster_obj = None
            autocad_service._active_polyline_obj = None
            autocad_service._active_polyline_handle = ""

            ok, msg = autocad_service.insert_raster_image(str(image_path))
            self.assertTrue(ok, msg)
            rasters = autocad_service.doc.ModelSpace.rasters
            self.assertEqual(len(rasters), 1)
            self.assertEqual(Path(rasters[0].image_path).name, "denah_uji.png")
            self.assertEqual(rasters[0].Layer, "AUTOLAND_DENAH")
            self.assertEqual(autocad_service.active_image_size, (100, 100))
            # Tanpa metadata DPI, skala harus sama dengan lebar piksel. Ini
            # membuat raster sejajar dengan polyline dan tidak tampak hilang.
            self.assertAlmostEqual(rasters[0].initial_scale, 100.0, places=2)

            ok, handle, msg = autocad_service.create_polyline_from_vertices(
                [(0, 0), (100, 0), (100, 100), (0, 100)],
                image_width=100, image_height=100,
            )
            self.assertTrue(ok, msg)
            self.assertTrue(handle)
            self.assertEqual(
                autocad_service.doc.ModelSpace.polylines[0]._coords,
                [(0.0, 100.0), (100.0, 100.0), (100.0, 0.0), (0.0, 0.0)],
            )
            # Raster harus tetap terpasang setelah polyline dibuat.
            ok_raster, raster_msg = autocad_service.ensure_raster_attached()
            self.assertTrue(ok_raster, raster_msg)
            self.assertEqual(len(autocad_service.doc.ModelSpace.rasters), 1)

            ok, area, _, msg = autocad_service.get_polyline_area(handle=handle)
            self.assertTrue(ok, msg)
            self.assertAlmostEqual(area, 10000.0, places=2)

            ok, final_area, msg = autocad_service.scale_active_objects(
                0.1, base_point=(0.0, 0.0, 0.0), polyline_handle=handle
            )
            self.assertTrue(ok, msg)
            self.assertAlmostEqual(final_area, 100.0, places=2)
            self.assertAlmostEqual(autocad_service.active_scale_factor, 0.1, places=6)
            self.assertEqual(rasters[0].scale_factors, [0.1])

            # Label 2 baris di tengah denah (pengganti blok data dokumen).
            ok, label_handle, msg = autocad_service.add_parcel_label(
                ["M. 00888", "GS55/2001"],
                center=(5.0, 5.0),
                plot_w=10.0,
                plot_h=10.0,
            )
            self.assertTrue(ok, msg)
            self.assertTrue(label_handle)
            label = autocad_service.doc.HandleToObject(label_handle)
            self.assertIn("M. 00888", label.TextString)
            self.assertIn("GS55/2001", label.TextString)
            self.assertEqual(label.Layer, "AUTOLAND_LABEL")
            self.assertEqual(label.AttachmentPoint, 5)
            self.assertAlmostEqual(label.Height, 0.6, places=4)
            self.assertEqual(len(autocad_service.doc.ModelSpace.labels), 1)

            # Denah sempit: label harus diperkecil agar tidak melebihi 80% lebar.
            ok, narrow_handle, msg = autocad_service.add_parcel_label(
                ["M. 00888", "GS55/2001"],
                center=(0.0, 0.0),
                plot_w=2.0,
                plot_h=10.0,
            )
            self.assertTrue(ok, msg)
            narrow = autocad_service.doc.HandleToObject(narrow_handle)
            self.assertLess(narrow.Height, 0.6)
            autocad_service.delete_entities({"label": narrow_handle})

            # Tata letak: denah berikutnya diletakkan di kanan denah pertama.
            layout = autocad_service.get_desa_layout()
            self.assertEqual(layout["plot_count"], 1)
            self.assertGreater(layout["next_slot"]["x"], 10.0)
            self.assertAlmostEqual(layout["next_slot"]["y"], 0.0, places=4)
            self.assertEqual(layout["next_slot"]["row"], 0)
            self.assertEqual(layout["next_slot"]["column"], 1)

            # Geser denah + raster + label ke slot berikutnya.
            handles = autocad_service.get_active_handles()
            handles["label"] = label_handle
            ok, msg = autocad_service.move_entities(handles, 20.0, 0.0)
            self.assertTrue(ok, msg)
            poly = autocad_service.doc.HandleToObject(handle)
            xs = poly.Coordinates[0::2]
            self.assertGreaterEqual(min(xs), 20.0 - 1e-6)

            # Hapus objek (dipakai saat proses ulang).
            deleted, errors = autocad_service.delete_entities(handles)
            self.assertEqual(deleted, 3)
            self.assertEqual(errors, [])

            dwg_path = TEST_ROOT / "hasil_autocad_asli.dwg"
            ok, msg = autocad_service.save_drawing_as(str(dwg_path), overwrite=True)
            self.assertTrue(ok, msg)
            self.assertTrue(dwg_path.exists())

            # DWG desa: dibuat sekali, lalu dibuka ulang tanpa dokumen baru.
            desa_path = TEST_ROOT / "Desa_Sukamaju" / "Desa_Sukamaju.dwg"
            ok, msg, created = autocad_service.open_or_create_desa_drawing(str(desa_path))
            self.assertTrue(ok, msg)
            self.assertTrue(created)
            self.assertTrue(desa_path.exists())
            ok, msg, created_again = autocad_service.open_or_create_desa_drawing(str(desa_path))
            self.assertTrue(ok, msg)
            self.assertFalse(created_again)
            self.assertEqual(fake_acad.Documents.Count, 1)
        finally:
            autocad_module.to_variant_double_array = original_variant_double
            autocad_module.to_variant_point = original_variant_point
            autocad_service.connect = original_connect

    # 8. TATA LETAK DWG DESA ---------------------------------------------------
    def test_desa_layout_grid(self):
        from services.autocad_service import AutoCADService

        plots = [
            {"handle": str(i), "bbox": (i * 12.0, 0.0, i * 12.0 + 10.0, 10.0)}
            for i in range(10)
        ]
        layout = AutoCADService.compute_desa_layout(plots)
        self.assertEqual(layout["next_slot"]["row"], 1)
        self.assertEqual(layout["next_slot"]["column"], 0)
        self.assertAlmostEqual(layout["next_slot"]["x"], 0.0, places=6)
        self.assertLess(layout["next_slot"]["y"], 0.0)
        self.assertTrue(layout["next_slot"]["starts_new_row"])
        self.assertAlmostEqual(layout["next_slot"]["row_top"], -5.0, places=6)

        second_row = {"handle": "r2", "bbox": (0.0, -20.0, 10.0, -10.0)}
        layout2 = AutoCADService.compute_desa_layout(plots + [second_row])
        self.assertEqual(layout2["next_slot"]["row"], 1)
        self.assertEqual(layout2["next_slot"]["column"], 1)
        self.assertGreater(layout2["next_slot"]["x"], 10.0)
        self.assertFalse(layout2["next_slot"]["starts_new_row"])

        # Dua baris penuh: baris ketiga kembali mulai dari kolom pertama.
        row2 = [
            {"handle": f"r2-{i}", "bbox": (i * 12.0, -20.0, i * 12.0 + 10.0, -10.0)}
            for i in range(10)
        ]
        layout_full = AutoCADService.compute_desa_layout(plots + row2)
        self.assertEqual(layout_full["next_slot"]["row"], 2)
        self.assertEqual(layout_full["next_slot"]["column"], 0)
        self.assertAlmostEqual(layout_full["next_slot"]["x"], 0.0, places=6)
        self.assertLess(layout_full["next_slot"]["row_top"], -20.0)

        layout3 = AutoCADService.compute_desa_layout(
            [], template_bbox=(0.0, 0.0, 100.0, 50.0)
        )
        self.assertGreater(layout3["next_slot"]["x"], 100.0)
        self.assertAlmostEqual(layout3["next_slot"]["y"], 0.0, places=6)


if __name__ == "__main__":
    try:
        unittest.main(verbosity=2)
    finally:
        shutil.rmtree(TEST_ROOT, ignore_errors=True)
