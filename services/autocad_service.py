"""
AutoLand Digitizer - AutoCAD Integration Service
Komunikasi langsung dengan AutoCAD Desktop via Windows COM Automation (pywin32).
Menangani koneksi, pembukaan template DWG, penyisipan raster, pembacaan polyline tertutup,
perhitungan dan eksekusi scaling seragam, penggantian teks TEXT/MTEXT, serta penyimpanan DWG.
Seluruh proses memakai AutoCAD Desktop asli (COM Automation); tidak ada mode simulasi.
"""

import os
import sys
import math
import time
from pathlib import Path
from typing import Tuple, Dict, Any, Optional, List

# Cek ketersediaan pywin32 — import dijalankan bertahap saat dibutuhkan.
PYWIN32_AVAILABLE = False
win32com = None
pythoncom = None


def _ensure_win32() -> bool:
    """Import win32com/pythoncom dari komputer; tanpa impor di waktu muat."""
    global PYWIN32_AVAILABLE, win32com, pythoncom
    if PYWIN32_AVAILABLE:
        return True
    try:
        import win32com.client  # noqa: F401
        import pythoncom  # noqa: F401
    except ImportError:
        return False
    win32com = sys.modules.get("win32com")
    pythoncom = sys.modules.get("pythoncom")
    PYWIN32_AVAILABLE = win32com is not None
    return PYWIN32_AVAILABLE


def to_variant_point(x: float, y: float, z: float = 0.0):
    """
    Mengonversi koordinat 3D ke format VARIANT array VT_R8 yang diterima oleh AutoCAD COM API.
    """
    if _ensure_win32() and win32com is not None:
        try:
            return win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, [float(x), float(y), float(z)])
        except Exception:
            return (float(x), float(y), float(z))
    return (float(x), float(y), float(z))


def to_variant_double_array(values: List[float]):
    """Mengonversi daftar angka ke VARIANT array VT_R8 untuk AddLightWeightPolyline."""
    data = [float(v) for v in values]
    if _ensure_win32() and win32com is not None:
        try:
            return win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, data)
        except Exception:
            return data
    return data


class AutoCADService:
    """
    Layanan integrasi AutoCAD Desktop berbasis COM Automation.
    """
    def __init__(self):
        self.acad = None
        self.doc = None
        self.is_connected = False
        self.version_string = ""
        self.last_error = ""
        self.active_template_path = ""
        
        # Objek aktif hasil otomasi (tanpa perlu seleksi manual operator)
        self._active_raster_obj = None
        self._active_polyline_obj = None
        self._active_polyline_handle = ""
        self.active_image_size = (0, 0)
        self.active_scale_factor = 1.0
        self.active_image_path = ""
        self._last_saved_doc = None
        self._last_saved_path = ""

    def _reset_active_objects(self):
        """Mengosongkan referensi objek dari dokumen AutoCAD sebelumnya."""
        self._active_raster_obj = None
        self._active_polyline_obj = None
        self._active_polyline_handle = ""
        self.active_image_size = (0, 0)
        self.active_scale_factor = 1.0
        self.active_image_path = ""

    # ------------------------------------------------------------------
    # Manajemen dokumen AutoCAD: pakai satu gambar aktif, jangan menumpuk
    # Drawing1/Drawing2 saat proses otomatis dijalankan.
    # ------------------------------------------------------------------
    def _documents_snapshot(self) -> list:
        """Ambil daftar dokumen yang sedang terbuka di AutoCAD (toleran ke fake COM)."""
        if not self.acad:
            return []
        try:
            documents = self.acad.Documents
        except Exception:
            return []

        result = []
        try:
            count = int(getattr(documents, "Count", 0))
        except Exception:
            count = 0

        if count > 0:
            try:
                result = [documents.Item(i) for i in range(count)]
            except Exception:
                try:
                    result = [documents.Item(i + 1) for i in range(count)]
                except Exception:
                    result = []

        if not result:
            try:
                result = list(documents)
            except Exception:
                pass
        return [doc for doc in result if doc is not None]

    @staticmethod
    def _document_is_empty(doc) -> bool:
        """Dokumen kosong = ModelSpace tidak berisi objek. conservative bila ragu."""
        try:
            return int(doc.ModelSpace.Count) == 0
        except Exception:
            try:
                return len(doc.ModelSpace) == 0
            except Exception:
                return False

    @staticmethod
    def _document_name(doc) -> str:
        try:
            return str(getattr(doc, "Name", "") or "")
        except Exception:
            return ""

    @staticmethod
    def _document_full_path(doc) -> str:
        for attr in ("FullName", "Path", "Name"):
            try:
                value = str(getattr(doc, attr, "") or "")
                if value:
                    return value
            except Exception:
                continue
        return ""

    def _same_document(self, first, second) -> bool:
        if first is None or second is None:
            return False
        if first is second:
            return True
        first_name = self._document_name(first).lower()
        second_name = self._document_name(second).lower()
        return bool(first_name) and first_name == second_name

    def _activate_service_document(self):
        """Pastikan semua operasi memakai dokumen yang sama dengan dokumen hasil otomasi."""
        desired = self.doc
        if desired is not None:
            try:
                desired.Activate()
            except Exception:
                pass
        try:
            current = self.acad.ActiveDocument
        except Exception:
            current = None

        if current is None:
            self.doc = desired
        elif desired is None or self._same_document(current, desired):
            self.doc = current
        else:
            self.doc = desired
        return self.doc

    def _close_empty_drawings(self, keep_doc=None, only_startup: bool = False) -> int:
        """Tutup dokumen kosong yang tidak dipakai agar hanya satu gambar aktif."""
        if not self.acad:
            return 0
        keep = keep_doc if keep_doc is not None else self.doc
        closed = 0
        for doc in self._documents_snapshot():
            if self._same_document(doc, keep):
                continue
            if not self._document_is_empty(doc):
                continue
            name = self._document_name(doc).lower()
            if only_startup and not name.startswith("drawing"):
                continue
            try:
                doc.Close(False)
                closed += 1
            except Exception:
                try:
                    doc.Close()
                    closed += 1
                except Exception:
                    pass
        return closed

    def _sync_after_connect(self):
        """
        Samakan dokumen internal dengan AutoCAD setelah koneksi dibuat, lalu
        tutup gambar kosong bawaan tambahan agar tidak muncul Drawing1 + Drawing2.
        """
        try:
            current = self.acad.ActiveDocument
        except Exception:
            current = None
        if current is not None:
            self.doc = current
        self._close_empty_drawings(keep_doc=self.doc, only_startup=True)

    def _retire_previous_result(self, current) -> bool:
        """
        Tutup gambar hasil sebelumnya yang sudah disimpan agar dokumen baru
        tidak menumpuk di AutoCAD saat memproses batch berikutnya.
        """
        if current is None or self._last_saved_doc is None:
            return False
        if not self._same_document(current, self._last_saved_doc):
            return False
        try:
            current.Close(False)
            self._last_saved_doc = None
            return True
        except Exception:
            return False

    def connect(self, launch_if_closed: bool = True) -> Tuple[bool, str]:
        """
        Menghubungkan aplikasi ke AutoCAD Desktop yang sedang berjalan atau membukanya.
        """
        self.last_error = ""

        if not _ensure_win32():
            self.last_error = "Library pywin32 belum terpasang atau sistem bukan Windows."
            return False, self.last_error

        try:
            pythoncom.CoInitialize()
        except Exception:
            pass

        # Coba hubungkan ke AutoCAD yang sedang terbuka
        try:
            self.acad = win32com.client.GetActiveObject("AutoCAD.Application")
            self.is_connected = True
            try:
                self.version_string = f"AutoCAD {self.acad.Caption}"
            except Exception:
                self.version_string = "AutoCAD Desktop Terhubung"
            self._sync_after_connect()
            return True, f"Terhubung ke {self.version_string} (Instance Aktif)"
        except Exception:
            pass

        # Jika belum terbuka dan diizinkan untuk membuka baru
        if launch_if_closed:
            try:
                # Coba beberapa ProgID umum AutoCAD
                prog_ids = [
                    "AutoCAD.Application.24", # AutoCAD 2021-2024 (prioritas laptop operator)
                    "AutoCAD.Application",
                    "AutoCAD.Application.23", # AutoCAD 2019-2020
                    "AutoCAD.Application.22", # AutoCAD 2018
                ]
                for pid in prog_ids:
                    try:
                        self.acad = win32com.client.Dispatch(pid)
                        self.acad.Visible = True
                        self.is_connected = True
                        self.version_string = f"AutoCAD {getattr(self.acad, 'Caption', 'Desktop')}"
                        self._sync_after_connect()
                        return True, f"AutoCAD berhasil dijalankan dan terhubung ({self.version_string})"
                    except Exception:
                        continue
            except Exception as e:
                self.last_error = f"Gagal menjalankan AutoCAD: {str(e)}"
                return False, self.last_error

        self.last_error = "AutoCAD Desktop tidak ditemukan atau belum berjalan pada komputer ini."
        self.is_connected = False
        return False, self.last_error

    def get_status(self) -> Dict[str, Any]:
        """
        Mengembalikan status koneksi AutoCAD Desktop saat ini.
        """
        if not self.is_connected or not self.acad:
            return {
                "connected": False,
                "version": "Tidak Terhubung",
                "active_document": "-",
                "error": self.last_error
            }
            
        try:
            active_doc_name = "-"
            if self.acad.ActiveDocument:
                active_doc_name = self.acad.ActiveDocument.Name
            return {
                "connected": True,
                "version": self.version_string or "AutoCAD Desktop Terhubung",
                "active_document": active_doc_name,
                "error": ""
            }
        except Exception as e:
            self.is_connected = False
            return {
                "connected": False,
                "version": "Terputus",
                "active_document": "-",
                "error": f"Koneksi terputus: {str(e)}"
            }

    def create_new_drawing(self) -> Tuple[bool, str]:
        """
        Membuat dokumen DWG baru di AutoCAD saat template bawaan tidak tersedia.
        """
        ok, msg = self.connect(launch_if_closed=True)
        if not ok:
            return False, msg
        try:
            try:
                pythoncom.CoInitialize()
            except Exception:
                pass

            # AutoCAD yang baru dijalankan sudah punya Drawing1 kosong. Pakai itu,
            # jangan menambah Drawing2 hanya karena proses butuh DWG baru.
            candidate = None
            for _ in range(3):
                try:
                    candidate = self.acad.ActiveDocument
                    if candidate is not None:
                        break
                except Exception:
                    time.sleep(0.3)

            if candidate is not None and self._document_is_empty(candidate):
                self.doc = candidate
                reused = True
            else:
                self._retire_previous_result(candidate)
                # Tambah dokumen baru via Documents.Add() dengan retry jika AutoCAD sibuk/modal
                doc_added = None
                last_exc = None
                for attempt in range(3):
                    try:
                        docs = self.acad.Documents
                        try:
                            doc_added = docs.Add()
                        except TypeError:
                            doc_added = docs.Add("")
                        if doc_added is not None:
                            break
                    except Exception as exc:
                        last_exc = exc
                        time.sleep(0.5)

                if doc_added is not None:
                    self.doc = doc_added
                    reused = False
                elif candidate is not None:
                    # Fallback ke dokumen aktif yang sudah ada jika Add() ditolak
                    self.doc = candidate
                    reused = True
                else:
                    raise RuntimeError(
                        f"AutoCAD menolak pembuatan dokumen baru ({last_exc or 'AutoCAD.Application.Documents'}). "
                        "Pastikan: 1) AutoCAD sudah terbuka dengan gambar aktif (misal Drawing1.dwg), "
                        "2) Tidak ada kotak dialog/peringatan yang menghalangi, "
                        "3) Tekan ESC beberapa kali di AutoCAD untuk membatalkan perintah yang menggantung."
                    )

            self._close_empty_drawings(keep_doc=self.doc)
            self._activate_service_document()
            self.acad.Visible = True
            self.active_template_path = ""
            self._reset_active_objects()
            note = " (gambar kosong yang sudah terbuka dipakai ulang)" if reused else ""
            return True, f"Dokumen DWG baru siap di AutoCAD{note}."
        except Exception as e:
            return False, f"Gagal membuat dokumen DWG baru: {e}"

    def open_template(self, template_path: str) -> Tuple[bool, str]:
        """
        Membuka file template DWG di AutoCAD.
        """
        ok, msg = self.connect(launch_if_closed=True)
        if not ok:
            return False, msg

        abs_template = os.path.abspath(template_path)
        if not os.path.exists(abs_template):
            return False, f"File template DWG tidak ditemukan di: {abs_template}"

        try:
            basename = os.path.basename(abs_template).lower()
            existing = None
            for doc in self._documents_snapshot():
                full = self._document_full_path(doc).lower()
                name = self._document_name(doc).lower()
                if (full and os.path.abspath(full) == abs_template.lower()) or name == basename:
                    existing = doc
                    break

            if existing is not None:
                self.doc = existing
                message = "Template sudah terbuka dan aktif di AutoCAD."
            else:
                try:
                    active = self.acad.ActiveDocument
                except Exception:
                    active = None
                self._retire_previous_result(active)
                self.doc = self.acad.Documents.Open(abs_template)
                message = f"Template {os.path.basename(abs_template)} berhasil dibuka di AutoCAD."

            self._close_empty_drawings(keep_doc=self.doc)
            self._activate_service_document()
            self.acad.Visible = True
            self.acad.WindowState = 3 # 3 = Maximized
            self.active_template_path = abs_template
            self._reset_active_objects()
            return True, message
        except Exception as e:
            # Alternatif jika dokumen sudah terbuka
            try:
                if self.acad.ActiveDocument and os.path.basename(abs_template).lower() in self.acad.ActiveDocument.Name.lower():
                    self._activate_service_document()
                    self._close_empty_drawings(keep_doc=self.doc)
                    self._reset_active_objects()
                    return True, "Template sudah terbuka dan aktif di AutoCAD."
            except Exception:
                pass
            return False, f"Gagal membuka template di AutoCAD: {str(e)}"

    def insert_raster_image(
        self,
        image_path: str,
        insert_pt: Tuple[float, float, float] = (0.0, 0.0, 0.0),
        scale: float = 1.0,
        rotation_deg: float = 0.0
    ) -> Tuple[bool, str]:
        """
        Memasukkan gambar denah hasil crop sebagai objek raster image ke ModelSpace AutoCAD.

        Parameter ``scale`` dipertahankan untuk kompatibilitas pemanggil lama,
        tetapi skala aktual dihitung dari ukuran piksel/DPI gambar agar raster
        sejajar dengan polyline yang memakai koordinat piksel.
        """
        if not self.is_connected or not self.acad:
            ok, msg = self.connect()
            if not ok:
                return False, msg

        abs_image = os.path.abspath(image_path)
        if not os.path.exists(abs_image):
            return False, f"File gambar raster tidak ditemukan: {abs_image}"

        # Baca ukuran dan DPI SEBELUM AddRaster. AutoCAD menentukan ukuran
        # raster dari metadata DPI; PNG hasil crop PyMuPDF biasanya tidak
        # memiliki metadata itu sehingga scale=1 membuat lebarnya hanya
        # 1 unit, sementara polyline memakai koordinat piksel. Akibatnya denah
        # tampak hilang setelah ZoomExtents. Samakan satuan keduanya di sini.
        from PIL import Image

        try:
            with Image.open(abs_image) as img:
                image_w, image_h = img.size
                dpi_info = img.info.get("dpi") or (0, 0)
        except Exception as exc:
            return False, f"Gagal membaca gambar raster: {exc}"

        dpi_x = float(dpi_info[0]) if dpi_info else 0.0
        if 10.0 <= dpi_x <= 2400.0:
            base_scale = dpi_x
        else:
            base_scale = float(image_w)

        self.active_image_path = abs_image
        self.active_image_size = (image_w, image_h)

        try:
            self._activate_service_document()
            model_space = self.doc.ModelSpace

            # Format titik penyisipan
            pt_variant = to_variant_point(insert_pt[0], insert_pt[1], insert_pt[2])
            rad = math.radians(rotation_deg)

            # AddRaster(ImageFileName, InsertionPoint, ScaleFactor, RotationAngle)
            raster_obj = model_space.AddRaster(
                abs_image, pt_variant, float(base_scale), float(rad)
            )
            if raster_obj is None:
                return False, (
                    "AutoCAD tidak mengembalikan objek raster; gambar denah gagal disisipkan."
                )
            try:
                self.doc.Layers.Add("AUTOLAND_DENAH")
            except Exception:
                pass
            try:
                raster_obj.Layer = "AUTOLAND_DENAH"
            except Exception:
                pass

            # Koreksi kedua: pakai ImageWidth/ImageHeight bila tersedia agar
            # ukuran di ModelSpace benar-benar sama dengan ukuran piksel crop.
            try:
                inserted_w = float(getattr(raster_obj, "ImageWidth", 0) or 0)
                inserted_h = float(getattr(raster_obj, "ImageHeight", 0) or 0)
                if inserted_w > 0 and abs(inserted_w - image_w) > 0.5:
                    try:
                        raster_obj.ImageWidth = float(image_w)
                        if inserted_h > 0:
                            raster_obj.ImageHeight = float(image_h)
                    except Exception:
                        correction = float(image_w) / inserted_w
                        current = float(getattr(raster_obj, "ScaleFactor", base_scale) or base_scale)
                        raster_obj.ScaleFactor = current * correction
            except Exception:
                pass

            # Pastikan folder gambar masuk support path. Raster di DWG adalah
            # tautan ke file, bukan data tertanam, sehingga path harus valid.
            try:
                image_folder = os.path.dirname(abs_image)
                files_pref = self.acad.Preferences.Files
                current_paths = [
                    p.strip()
                    for p in str(files_pref.SupportPath or "").split(";")
                    if p.strip()
                ]
                lowered = [p.lower() for p in current_paths]
                if image_folder.lower() not in lowered:
                    files_pref.SupportPath = ";".join(current_paths + [image_folder])
            except Exception:
                pass

            self._active_raster_obj = raster_obj
            try:
                raster_obj.Update()
            except Exception:
                pass
            try:
                self.doc.Regen()
            except Exception:
                pass
            try:
                self.acad.ZoomExtents()
            except Exception:
                pass

            return True, (
                f"Gambar denah {os.path.basename(abs_image)} berhasil dimasukkan "
                f"ke AutoCAD ModelSpace ({image_w}×{image_h} unit, sejajar dengan polyline)."
            )
        except Exception as e:
            return False, f"Gagal memasukkan raster image ke AutoCAD: {str(e)}"

    def ensure_raster_attached(self) -> Tuple[bool, str]:
        """
        Pastikan raster denah masih terpasang di dokumen aktif. Dipanggil setelah
        polyline dibuat dan setelah scaling supaya gambar tidak pernah hilang.
        """
        if not self.active_image_path or not self._active_raster_obj:
            return False, "Raster denah belum disisipkan."

        target = os.path.abspath(self.active_image_path).lower()
        model_space = getattr(self, "doc", None).ModelSpace if getattr(self, "doc", None) else None
        candidates = []
        try:
            # Fake COM/tests menyimpan raster di atribut khusus; AutoCAD asli
            # mengembalikannya saat iteration ModelSpace.
            fake_rasters = getattr(model_space, "rasters", None)
            if fake_rasters:
                candidates.extend(list(fake_rasters))
        except Exception:
            pass
        try:
            candidates.extend(list(model_space))
        except Exception:
            pass

        try:
            for obj in candidates:
                try:
                    path = str(
                        getattr(obj, "ImageFile", "")
                        or getattr(obj, "image_path", "")
                        or ""
                    )
                    if path and os.path.abspath(path).lower() == target:
                        self._active_raster_obj = obj
                        return True, "Gambar denah masih terpasang di ModelSpace."
                    handle = str(getattr(obj, "Handle", "") or "")
                    active_handle = str(getattr(self._active_raster_obj, "Handle", "") or "")
                    if handle and handle == active_handle:
                        return True, "Gambar denah masih terpasang di ModelSpace."
                except Exception:
                    continue
        except Exception:
            pass

        # Raster tidak ditemukan (misalnya dokumen dibuka ulang). Pasang ulang
        # dari file crop permanen yang sama.
        return self.insert_raster_image(self.active_image_path)

    def create_polyline_from_vertices(
        self,
        vertices: List[Tuple[float, float]],
        image_width: int = 0,
        image_height: int = 0,
        closed: bool = True,
        layer: str = "AUTOLAND_BOUNDARY",
    ) -> Tuple[bool, str, str]:
        """
        Membuat polyline tertutup di AutoCAD langsung dari titik hasil deteksi.
        Titik masuk adalah koordinat piksel gambar (sumbu Y ke bawah).
        Konversi ke ModelSpace: x = x_piksel, y = tinggi_gambar - y_piksel.

        Mengembalikan: (success, handle, message)
        """
        pts = [(float(x), float(y)) for x, y in vertices]
        if len(pts) < 3:
            return False, "", "Minimal tiga titik diperlukan untuk membuat polyline."

        height = float(image_height or self.active_image_size[1] or 0.0)
        if height <= 0:
            height = max(y for _, y in pts) + 1.0
        model_points = [(x, height - y) for x, y in pts]

        if not self.is_connected or not self.acad:
            ok, msg = self.connect()
            if not ok:
                return False, "", msg

        try:
            self._activate_service_document()
            flat: List[float] = []
            for x, y in model_points:
                flat.extend([x, y])
            variant = to_variant_double_array(flat)
            poly = self.doc.ModelSpace.AddLightWeightPolyline(variant)
            poly.Closed = bool(closed)
            try:
                if layer:
                    try:
                        self.doc.Layers.Add(layer)
                    except Exception:
                        pass
                    poly.Layer = layer
            except Exception:
                pass
            poly.Update()
            self._active_polyline_obj = poly
            self._active_polyline_handle = str(getattr(poly, "Handle", ""))
            try:
                self.acad.ZoomExtents()
            except Exception:
                pass
            return True, self._active_polyline_handle, f"Polyline otomatis ({len(pts)} titik) berhasil dibuat di AutoCAD."
        except Exception as exc:
            return False, "", f"Gagal membuat polyline otomatis di AutoCAD: {exc}"

    @staticmethod
    def _shoelace_area(points: List[Tuple[float, float]]) -> float:
        if len(points) < 3:
            return 0.0
        total = 0.0
        for i, (x1, y1) in enumerate(points):
            x2, y2 = points[(i + 1) % len(points)]
            total += x1 * y2 - x2 * y1
        return abs(total) / 2.0

    def scale_active_objects(
        self,
        scale_factor: float,
        base_point: Tuple[float, float, float] = (0.0, 0.0, 0.0),
        polyline_handle: Optional[str] = None,
    ) -> Tuple[bool, float, str]:
        """
        Menskalakan raster + polyline yang dibuat otomatis tanpa seleksi manual.
        """
        if scale_factor <= 0:
            return False, 0.0, "Faktor skala harus lebih besar dari 0."

        handle = polyline_handle or self._active_polyline_handle
        objects = [obj for obj in (self._active_raster_obj, self._active_polyline_obj) if obj is not None]
        if not objects:
            return False, 0.0, "Tidak ada objek otomatis untuk diskalakan. Buka template dan sisipkan denah dahulu."

        try:
            base = to_variant_point(*base_point)
            for obj in objects:
                try:
                    obj.ScaleEntity(base, float(scale_factor))
                except Exception as scale_error:
                    # Beberapa versi AutoCAD menolak ScaleEntity pada raster image.
                    # Properti ScaleFactor tetap dipakai agar denah tidak hilang.
                    if obj is not self._active_raster_obj:
                        raise
                    try:
                        current = float(getattr(obj, "ScaleFactor", 1.0) or 1.0)
                        obj.ScaleFactor = current * float(scale_factor)
                    except Exception:
                        raise scale_error
            self.active_scale_factor *= float(scale_factor)
            try:
                self.acad.ZoomExtents()
            except Exception:
                pass

            final_area = 0.0
            if handle:
                try:
                    poly_obj = self.doc.HandleToObject(handle)
                    final_area = float(getattr(poly_obj, "Area", 0.0))
                except Exception:
                    final_area = 0.0
            return True, final_area, f"Skala {scale_factor:.6f} berhasil diterapkan ke {len(objects)} objek otomatis."
        except Exception as exc:
            return False, 0.0, f"Gagal menerapkan skala otomatis: {exc}"

    def set_identity_text(self, new_identity_text: str) -> Tuple[bool, str]:
        """
        Mengganti teks identitas pada objek TEXT/MTEXT pertama yang ditemukan.
        Jika tidak ada, membuat objek TEXT baru di dekat denah.
        """
        if not self.is_connected or not self.acad:
            ok, msg = self.connect()
            if not ok:
                return False, msg

        try:
            self._activate_service_document()
            for obj in self.doc.ModelSpace:
                try:
                    if getattr(obj, "ObjectName", "") in ("AcDbText", "AcDbMText"):
                        obj.TextString = str(new_identity_text)
                        obj.Update()
                        return True, f"Teks identitas berhasil diubah menjadi '{new_identity_text}'."
                except Exception:
                    continue

            text = self.doc.ModelSpace.AddText(
                str(new_identity_text), to_variant_point(10.0, -10.0, 0.0), 2.5
            )
            text.Update()
            return True, f"Teks identitas '{new_identity_text}' ditambahkan ke gambar."
        except Exception as exc:
            return False, f"Gagal mengubah teks identitas secara otomatis: {exc}"

    def get_polyline_area(self, handle: Optional[str] = None) -> Tuple[bool, float, str, str]:
        """
        Membaca luas polyline. Jika handle diberikan (alur otomatis), objek diambil
        langsung tanpa meminta operator mengklik. Tanpa handle, perilaku lama dipertahankan.

        Mengembalikan: (success, area_m2, entity_handle, message)
        """
        if not self.is_connected or not self.acad:
            ok, msg = self.connect()
            if not ok:
                return False, 0.0, "", msg

        try:
            self._activate_service_document()

            if handle:
                try:
                    picked_obj = self.doc.HandleToObject(handle)
                except Exception as exc:
                    return False, 0.0, "", f"Polyline dengan handle {handle} tidak ditemukan: {exc}"
            else:
                picked_obj = self._active_polyline_obj

            if not picked_obj:
                return False, 0.0, "", "Polyline otomatis belum tersedia. Jalankan deteksi dan buat polyline terlebih dahulu."
                
            obj_name = getattr(picked_obj, "ObjectName", "")
            
            # Validasi tipe objek harus AcDbPolyline atau AcDb2dPolyline
            if obj_name not in ["AcDbPolyline", "AcDb2dPolyline"]:
                return False, 0.0, "", f"Objek bukan polyline ({obj_name}). Polyline harus dibuat otomatis oleh aplikasi."
                
            # Validasi properti Closed
            is_closed = getattr(picked_obj, "Closed", False)
            if not is_closed:
                return False, 0.0, "", "Polyline otomatis belum tertutup. Periksa hasil deteksi lalu jalankan kembali proses."
                
            # Ambil nilai luas
            area = float(getattr(picked_obj, "Area", 0.0))
            if area <= 0.0:
                return False, 0.0, "", "Luas polyline bernilai 0 m² atau tidak valid."
                
            handle = getattr(picked_obj, "Handle", "")
            return True, area, handle, f"Polyline valid! Luas terbaca: {area:.4f} m²"
            
        except Exception as e:
            return False, 0.0, "", f"Gagal membaca luas polyline dari AutoCAD: {e}"

    @staticmethod
    def _escape_mtext(value: str) -> str:
        """Mengamankan karakter khusus MTEXT AutoCAD."""
        return (
            str(value)
            .replace("\\", "\\\\")
            .replace("{", "\\{")
            .replace("}", "\\}")
        )

    def add_document_info_block(
        self,
        lines: List[str],
        title: str = "DATA DOKUMEN PERTANAHAN",
    ) -> Tuple[bool, str]:
        """
        Menulis blok data dokumen di atas gambar denah yang telah diskalakan.

        Blok ini berisi identitas, jenis hak, nomor hak/GS, tahun, luas, dan
        informasi batch. Teks ditempatkan tepat di atas batas atas raster hasil
        scaling sehingga denah + polyline + data dokumen tampil dalam satu DWG.
        """
        if not self.is_connected or not self.acad:
            ok, msg = self.connect()
            if not ok:
                return False, msg

        if not lines:
            return False, "Tidak ada data dokumen yang akan ditulis."

        try:
            self._activate_service_document()

            img_w = float(self.active_image_size[0]) * self.active_scale_factor
            img_h = float(self.active_image_size[1]) * self.active_scale_factor
            text_height = max(2.5, img_h * 0.025) if img_h > 0 else 3.0
            width = max(img_w * 0.85, 260.0)
            insert_x = 0.0

            escaped = [self._escape_mtext(title)] + [self._escape_mtext(line) for line in lines]
            mtext_value = "\\P".join(escaped)

            # AddMText memakai titik sambung kiri-atas (top-left). Hitung tinggi
            # perkiraan seluruh blok agar teks benar-benar berada di atas raster,
            # bukan menimpa denah yang sudah diskalakan.
            estimated_height = max(1, len(escaped)) * text_height * 1.25
            gap = text_height * 1.5
            insert_y = img_h + gap + estimated_height

            try:
                self.doc.Layers.Add("AUTOLAND_INFO")
            except Exception:
                pass

            info = self.doc.ModelSpace.AddMText(
                to_variant_point(insert_x, insert_y, 0.0),
                float(width),
                mtext_value,
            )
            try:
                info.Layer = "AUTOLAND_INFO"
            except Exception:
                pass
            try:
                info.Height = float(text_height)
            except Exception:
                pass
            try:
                info.Update()
            except Exception:
                pass

            try:
                self.acad.ZoomExtents()
            except Exception:
                pass

            return True, f"Blok data dokumen ({len(lines)} baris) ditulis di atas denah."
        except Exception as exc:
            return False, f"Gagal menulis data dokumen di AutoCAD: {exc}"

    def save_drawing_as(self, output_dwg_path: str, overwrite: bool = False) -> Tuple[bool, str]:
        """
        Menyimpan dokumen AutoCAD aktif sebagai file DWG hasil digitasi.
        """
        abs_output = os.path.abspath(output_dwg_path)
        folder = os.path.dirname(abs_output)
        os.makedirs(folder, exist_ok=True)
        
        if os.path.exists(abs_output) and not overwrite:
            return False, f"File DWG dengan nama '{os.path.basename(abs_output)}' sudah ada. Silakan konfirmasi untuk menimpa."

        if not self.is_connected or not self.acad:
            ok, msg = self.connect()
            if not ok:
                return False, msg

        try:
            self._activate_service_document()
            # Simpan sebagai DWG
            self.doc.SaveAs(abs_output)
            self._last_saved_doc = self.doc
            self._last_saved_path = abs_output
            return True, f"Dokumen DWG berhasil disimpan ke: {abs_output}"
        except Exception as e:
            return False, f"Gagal menyimpan file DWG: {str(e)}"


# Singleton instance
autocad_service = AutoCADService()
