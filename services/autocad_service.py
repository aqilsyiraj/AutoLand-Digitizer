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
from typing import Tuple, Dict, Any, Optional, List

from config import (
    DWG_LABEL_HEIGHT_RATIO,
    DWG_LABEL_MAX_WIDTH_RATIO,
    DWG_MAX_COLUMNS,
    DWG_PLOT_GAP_RATIO,
    DWG_PLOT_MIN_GAP,
)

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
        self._active_raster_handle = ""
        self._active_polyline_obj = None
        self._active_polyline_handle = ""
        self._active_label_obj = None
        self._active_label_handle = ""
        self.active_image_size = (0, 0)
        self.active_scale_factor = 1.0
        self.active_image_path = ""
        self._last_saved_doc = None
        self._last_saved_path = ""
        self._active_desa_path = ""

    def _find_desa_doc(self):
        """Mencari dokumen desa yang terbuka berdasarkan nama path simpan."""
        target = (getattr(self, "_active_desa_path", "") or "").lower()
        if not target:
            return None
        target_name = os.path.basename(target).lower()
        for doc in self._documents_snapshot():
            full = self._document_full_path(doc).lower()
            name = self._document_name(doc).lower()
            if (full and os.path.abspath(full).lower() == target) or (name == target_name):
                return doc
        return None

    def _reset_active_objects(self):
        """Mengosongkan referensi objek dari dokumen AutoCAD sebelumnya."""
        self._active_raster_obj = None
        self._active_raster_handle = ""
        self._active_polyline_obj = None
        self._active_polyline_handle = ""
        self._active_label_obj = None
        self._active_label_handle = ""
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

    def _reconnect_active_document(self):
        """
        Ambil handle dokumen saat ini (mungkin stale setelah open/close
        siklus di AutoCAD), lalu aktifkan sebagai dokumen layanan.
        """
        desa_doc = None
        try:
            desa_doc = self._find_desa_doc()
        except Exception:
            desa_doc = None
        if desa_doc is not None:
            self.doc = desa_doc
            try:
                desa_doc.Activate()
            except Exception:
                pass
            return desa_doc

        try:
            current = self.acad.ActiveDocument
            if current is not None:
                self.doc = current
        except Exception:
            pass
        if self.doc is None and self.acad is not None:
            try:
                for pid in (
                    "AutoCAD.Application.24",
                    "AutoCAD.Application",
                    "AutoCAD.Application.23",
                ):
                    try:
                        self.acad = win32com.client.Dispatch(pid)
                        break
                    except Exception:
                        continue
                try:
                    self.doc = self.acad.ActiveDocument
                except Exception:
                    pass
            except Exception:
                pass
        return self._activate_service_document()

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

    def open_or_create_desa_drawing(
        self, dwg_path: str, template_path: str = ""
    ) -> Tuple[bool, str, bool]:
        """Membuka DWG desa yang sudah ada, atau membuatnya dari template.

        Satu desa memakai satu file DWG. File baru dibuat dari template hanya
        saat file desa belum ada; proses berikutnya membuka file yang sama lalu
        menambahkan denah baru.

        Mengembalikan: (success, message, created_new_file)
        """
        ok, msg = self.connect(launch_if_closed=True)
        if not ok:
            return False, msg, False

        abs_path = os.path.abspath(dwg_path)
        folder = os.path.dirname(abs_path)
        if folder:
            os.makedirs(folder, exist_ok=True)
        target_name = os.path.basename(abs_path).lower()

        # Pakai dokumen yang sudah terbuka agar tidak menumpuk Drawing1/Drawing2.
        for doc in self._documents_snapshot():
            full = self._document_full_path(doc).lower()
            name = self._document_name(doc).lower()
            same_path = bool(full) and os.path.abspath(full).lower() == abs_path.lower()
            if same_path or (name and name == target_name):
                self.doc = doc
                self._activate_service_document()
                self._active_desa_path = abs_path
                self._close_empty_drawings(keep_doc=self.doc)
                self.acad.Visible = True
                return True, f"DWG desa sudah terbuka: {target_name}", False

        try:
            opened = None
            open_error = ""
            if os.path.exists(abs_path):
                # File desa sudah ada: buka dulu, lanjutkan kedudukan
                # denah lama. Jika Documents.Open gagal, fallback buat baru.
                try:
                    opened = self.acad.Documents.Open(abs_path)
                except Exception as exc:
                    open_error = str(exc)

            if opened is not None:
                self.doc = opened
                self._active_desa_path = abs_path
                created = False
                message = f"DWG desa dibuka: {target_name}"
                if open_error:
                    message += f" (fallback: {open_error})"
            elif os.path.exists(abs_path):
                # File ada tapi gagal membukanya: buat baru sebagai cadangan,
                # agar pekerjaan tetap berlanjut daripada menemui galat saat save.
                if template_path and os.path.exists(template_path):
                    ok, msg = self.open_template(template_path)
                    if ok:
                        self.doc.SaveAs(abs_path)
                else:
                    ok, msg = self.create_new_drawing()
                    if ok:
                        self.doc.SaveAs(abs_path)
                created = True
                message = f"DWG desa dibuat ulang dari template/belum bisa dibuka: {target_name}"
            elif template_path and os.path.exists(template_path):
                ok, msg = self.open_template(template_path)
                if not ok:
                    return False, msg, False
                self.doc.SaveAs(abs_path)
                created = True
                message = f"DWG desa dibuat dari template: {target_name}"
            else:
                ok, msg = self.create_new_drawing()
                if not ok:
                    return False, msg, False
                self.doc.SaveAs(abs_path)
                created = True
                message = f"DWG desa baru dibuat: {target_name}"

            self._activate_service_document()
            self._active_desa_path = abs_path
            self._close_empty_drawings(keep_doc=self.doc)
            self.acad.Visible = True
            self._reset_active_objects()
            return True, message, created
        except Exception as exc:
            return False, f"Gagal membuka/membuat DWG desa: {exc}", False

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
            try:
                raster_obj = model_space.AddRaster(
                    abs_image, pt_variant, float(base_scale), float(rad)
                )
            except Exception:
                # Handle dokumen bisa stale (pesan AutoCAD: "Open.ModelSpace")
                # setelah open/close siklus kedua ke-8; cobakan sekali lagi
                # dengan handle ActiveDocument yang baru.
                self._reconnect_active_document()
                model_space = self.doc.ModelSpace
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
            self._active_raster_handle = str(getattr(raster_obj, "Handle", "") or "")
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
            doc_name = ""
            try:
                doc_name = self._document_name(self.doc)
            except Exception:
                doc_name = ""
            suffix = f" ({doc_name})" if doc_name else ""
            return False, f"Gagal memasukkan raster image ke AutoCAD{suffix}: {str(e)}"

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

    # ------------------------------------------------------------------
    # Tata letak DWG desa: satu file per desa, denah berjajar 10 kolom.
    # ------------------------------------------------------------------
    @staticmethod
    def _plot_gap(width: float) -> float:
        """Jarak antar denah: 10% lebar denah, minimal 5 satuan gambar."""
        return max(float(DWG_PLOT_MIN_GAP), abs(float(width)) * float(DWG_PLOT_GAP_RATIO))

    @staticmethod
    def compute_desa_layout(
        plots: List[Dict[str, Any]], template_bbox=None
    ) -> Dict[str, Any]:
        """Menghitung posisi denah berikutnya dari daftar polyline yang ada.

        Denah disusun maksimal 10 kolom per baris. Baris berikutnya dimulai
        dari x yang sama dengan denah pertama (turun ke bawah), bukan dari
        kolom terakhir.
        """
        plots = [p for p in (plots or []) if p.get("bbox")]
        if template_bbox:
            tpl_w = max(1.0, float(template_bbox[2]) - float(template_bbox[0]))
            origin_x = float(template_bbox[2]) + AutoCADService._plot_gap(tpl_w)
            origin_y = float(template_bbox[1])
        else:
            origin_x = 0.0
            origin_y = 0.0

        if not plots:
            return {
                "plots": [],
                "rows": [],
                "template_bbox": template_bbox,
                "origin": (origin_x, origin_y),
                "next_slot": {
                    "x": origin_x,
                    "y": origin_y,
                    "row": 0,
                    "column": 0,
                },
                "plot_count": 0,
            }

        heights = [float(p["bbox"][3]) - float(p["bbox"][1]) for p in plots]
        tolerance = max(1e-6, (sum(heights) / len(heights)) * 0.05)
        rows: List[Dict[str, Any]] = []
        for plot in plots:
            baseline = float(plot["bbox"][1])
            for row in rows:
                if abs(baseline - row["baseline"]) <= tolerance:
                    row["plots"].append(plot)
                    break
            else:
                rows.append({"baseline": baseline, "plots": [plot]})

        first_row = rows[0]
        row_start_x = min(float(p["bbox"][0]) for p in first_row["plots"])

        current_row = rows[-1]
        current_plots = current_row["plots"]
        row_index = len(rows) - 1
        column_index = len(current_plots)

        if column_index >= int(DWG_MAX_COLUMNS):
            row_height = max(
                float(p["bbox"][3]) - float(p["bbox"][1]) for p in current_plots
            )
            row_width = max(
                float(p["bbox"][2]) - float(p["bbox"][0]) for p in current_plots
            )
            next_x = row_start_x
            # Baris baru dimulai tepat di bawah baris sebelumnya. Tinggi denah
            # baru belum diketahui di sini, jadi simpan batas atas baris dan
            # pemanggil menyesuaikan y setelah polyline selesai diskalakan.
            row_top = float(current_row["baseline"]) - AutoCADService._plot_gap(row_width)
            next_y = row_top - row_height
            starts_new_row = True
            row_index += 1
            column_index = 0
        else:
            last_right = max(float(p["bbox"][2]) for p in current_plots)
            last_width = max(
                float(p["bbox"][2]) - float(p["bbox"][0]) for p in current_plots
            )
            next_x = last_right + AutoCADService._plot_gap(last_width)
            next_y = float(current_row["baseline"])
            row_top = None
            starts_new_row = False

        return {
            "plots": plots,
            "rows": rows,
            "template_bbox": template_bbox,
            "origin": (row_start_x, float(first_row["baseline"])),
            "next_slot": {
                "x": next_x,
                "y": next_y,
                "row": row_index,
                "column": column_index,
                "starts_new_row": starts_new_row,
                "row_top": row_top,
            },
            "plot_count": len(plots),
        }

    def _modelspace_entities(self) -> list:
        try:
            return list(self.doc.ModelSpace)
        except Exception:
            return []

    @staticmethod
    def _polyline_bbox(obj) -> Optional[Tuple[float, float, float, float]]:
        try:
            coords = list(obj.Coordinates)
        except Exception:
            return None
        if len(coords) < 4:
            return None
        try:
            xs = [float(v) for v in coords[0::2]]
            ys = [float(v) for v in coords[1::2]]
        except Exception:
            return None
        return (min(xs), min(ys), max(xs), max(ys))

    def _entity_bbox(self, obj) -> Optional[Tuple[float, float, float, float]]:
        try:
            result = obj.GetBoundingBox()
        except Exception:
            result = None
        if isinstance(result, (tuple, list)) and len(result) >= 2:
            try:
                min_pt, max_pt = result[0], result[1]
                return (
                    float(min_pt[0]),
                    float(min_pt[1]),
                    float(max_pt[0]),
                    float(max_pt[1]),
                )
            except Exception:
                pass
        return self._polyline_bbox(obj)

    def get_entity_bbox(
        self, handle: str
    ) -> Optional[Tuple[float, float, float, float]]:
        try:
            obj = self.doc.HandleToObject(str(handle))
        except Exception:
            return None
        return self._entity_bbox(obj)

    def get_polyline_bbox(
        self, handle: str
    ) -> Optional[Tuple[float, float, float, float]]:
        try:
            obj = self.doc.HandleToObject(str(handle))
        except Exception:
            return None
        return self._polyline_bbox(obj)

    def get_active_handles(self) -> Dict[str, str]:
        """Handle objek denah yang baru dibuat (raster + polyline)."""
        raster_handle = (
            self._active_raster_handle
            or str(getattr(self._active_raster_obj, "Handle", "") or "")
        )
        return {
            "raster": str(raster_handle or ""),
            "polyline": str(self._active_polyline_handle or ""),
        }

    def get_desa_layout(self) -> Dict[str, Any]:
        """Membaca isi DWG desa lalu menghitung slot untuk denah berikutnya."""
        plots: List[Dict[str, Any]] = []
        template_bbox = None
        for obj in self._modelspace_entities():
            layer = str(getattr(obj, "Layer", "") or "")
            name = str(getattr(obj, "ObjectName", "") or "")
            # Data aktivitas diampuni: raster denah (gambar dasar) mendefinisikan
            # sel posisi agar pinggiran gambar tidak tumpang tindih.
            if layer == "AUTOLAND_DENAH":
                bbox = self._entity_bbox(obj)
                if bbox:
                    plots.append(
                        {
                            "handle": str(getattr(obj, "Handle", "") or ""),
                            "bbox": bbox,
                        }
                    )
                continue
            # Objek milik AutoLand lain tidak dihitung sebagai isi template.
            if layer.startswith("AUTOLAND_"):
                continue
            bbox = self._entity_bbox(obj)
            if not bbox:
                continue
            if template_bbox is None:
                template_bbox = bbox
            else:
                template_bbox = (
                    min(template_bbox[0], bbox[0]),
                    min(template_bbox[1], bbox[1]),
                    max(template_bbox[2], bbox[2]),
                    max(template_bbox[3], bbox[3]),
                )
        return self.compute_desa_layout(plots, template_bbox)

    def move_entities(
        self, handles: Dict[str, Any], dx: float, dy: float
    ) -> Tuple[bool, str]:
        """Menggeser raster/polyline/label sejauh (dx, dy) di ModelSpace."""
        dx = float(dx)
        dy = float(dy)
        if abs(dx) < 1e-9 and abs(dy) < 1e-9:
            return True, "Objek tidak perlu digeser."
        if not self.doc:
            return False, "Dokumen AutoCAD belum aktif."

        moved = 0
        for key in ("raster", "polyline", "label"):
            handle = str((handles or {}).get(key) or "")
            if not handle:
                continue
            try:
                obj = self.doc.HandleToObject(handle)
            except Exception as exc:
                return False, f"Objek {key} tidak ditemukan: {exc}"
            try:
                obj.Move(
                    to_variant_point(0.0, 0.0, 0.0),
                    to_variant_point(dx, dy, 0.0),
                )
                moved += 1
            except Exception as exc:
                return False, f"Gagal menggeser objek {key}: {exc}"

        try:
            self.acad.ZoomExtents()
        except Exception:
            pass
        return True, f"{moved} objek digeser ({dx:.2f}, {dy:.2f})"

    def delete_entities(self, handles: Dict[str, Any]) -> Tuple[int, List[str]]:
        """Menghapus objek denah lama saat dokumen diproses ulang."""
        if not self.doc:
            return 0, ["Dokumen AutoCAD belum aktif."]
        deleted = 0
        errors: List[str] = []
        for key in ("label", "polyline", "raster"):
            handle = str((handles or {}).get(key) or "")
            if not handle:
                continue
            try:
                obj = self.doc.HandleToObject(handle)
                obj.Delete()
                deleted += 1
            except Exception as exc:
                errors.append(f"{key}: {exc}")
        try:
            self.acad.ZoomExtents()
        except Exception:
            pass
        return deleted, errors

    def add_parcel_label(
        self,
        lines: List[str],
        center: Tuple[float, float],
        plot_w: float,
        plot_h: float,
    ) -> Tuple[bool, str, str]:
        """Menulis label 2 baris rata tengah di dalam denah.

        Tinggi huruf mengikuti 6% tinggi denah, lalu diperkecil otomatis bila
        teks lebih lebar dari 80% denah atau dua baris tidak muat vertikal.
        """
        if not self.is_connected or not self.acad:
            ok, msg = self.connect()
            if not ok:
                return False, "", msg

        lines = [str(line) for line in (lines or []) if str(line).strip()]
        if not lines:
            return False, "", "Tidak ada teks label yang akan ditulis."

        try:
            self._activate_service_document()
            plot_w = max(1e-6, float(plot_w))
            plot_h = max(1e-6, float(plot_h))

            height = plot_h * float(DWG_LABEL_HEIGHT_RATIO)
            max_width = plot_w * float(DWG_LABEL_MAX_WIDTH_RATIO)
            longest = max(len(line) for line in lines)
            estimated_width = longest * height * 0.65
            if estimated_width > max_width:
                height *= max_width / estimated_width

            # Dua baris (termasuk jarak antarbaris) harus muat di dalam denah.
            max_height = plot_h * 0.55
            total_height = height * len(lines) * 1.25
            if total_height > max_height:
                height *= max_height / total_height
            height = max(height, 1e-4)

            text = "\\P".join(self._escape_mtext(line) for line in lines)
            try:
                self.doc.Layers.Add("AUTOLAND_LABEL")
            except Exception:
                pass

            label_width = max(plot_w * 0.95, 1e-6)
            label = self.doc.ModelSpace.AddMText(
                to_variant_point(center[0], center[1], 0.0), label_width, text
            )
            try:
                label.Layer = "AUTOLAND_LABEL"
            except Exception:
                pass
            try:
                label.AttachmentPoint = 5  # acAttachmentPointMiddleCenter
            except Exception:
                pass
            try:
                label.Height = float(height)
            except Exception:
                pass
            try:
                label.InsertionPoint = to_variant_point(center[0], center[1], 0.0)
            except Exception:
                pass
            try:
                label.Update()
            except Exception:
                pass

            self._active_label_obj = label
            self._active_label_handle = str(getattr(label, "Handle", "") or "")
            return (
                True,
                self._active_label_handle,
                f"Label 2 baris ditulis di tengah denah (tinggi {height:.3f}).",
            )
        except Exception as exc:
            return False, "", f"Gagal menulis label denah: {exc}"

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
            current = self._document_full_path(self.doc)
            same_file = bool(current) and os.path.abspath(current).lower() == abs_output.lower()
            if same_file:
                # File desa sudah terbuka: simpan di tempat agar AutoCAD tidak
                # memunculkan dialog "file sudah ada" saat proses berikutnya.
                self.doc.Save()
            else:
                self.doc.SaveAs(abs_output)
            self._active_desa_path = abs_output
            self._last_saved_doc = self.doc
            self._last_saved_path = abs_output
            return True, f"Dokumen DWG berhasil disimpan ke: {abs_output}"
        except Exception as e:
            return False, f"Gagal menyimpan file DWG: {str(e)}"


# Singleton instance
autocad_service = AutoCADService()
