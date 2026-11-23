"""
AutoLand Digitizer - AutoCAD Integration Service
Komunikasi langsung dengan AutoCAD Desktop via Windows COM Automation (pywin32).
Menangani koneksi, pembukaan template DWG, penyisipan raster, pembacaan polyline tertutup,
perhitungan dan eksekusi scaling seragam, penggantian teks TEXT/MTEXT, serta penyimpanan DWG.
Mendukung mode simulasi jika komputer belum terpasang AutoCAD.
"""

import os
import sys
import math
from pathlib import Path
from typing import Tuple, Dict, Any, Optional, List

# Cek ketersediaan pywin32
PYWIN32_AVAILABLE = False
try:
    import win32com.client
    import pythoncom
    PYWIN32_AVAILABLE = True
except ImportError:
    PYWIN32_AVAILABLE = False


def to_variant_point(x: float, y: float, z: float = 0.0):
    """
    Mengonversi koordinat 3D ke format VARIANT array VT_R8 yang diterima oleh AutoCAD COM API.
    """
    if PYWIN32_AVAILABLE:
        try:
            return win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, [float(x), float(y), float(z)])
        except Exception:
            return (float(x), float(y), float(z))
    return (float(x), float(y), float(z))


class AutoCADService:
    """
    Layanan integrasi AutoCAD Desktop berbasis COM Automation.
    """
    def __init__(self):
        self.acad = None
        self.doc = None
        self.is_connected = False
        self.simulation_mode = False
        self.version_string = ""
        self.last_error = ""
        self.active_template_path = ""
        
        # State simulasi (untuk pengujian di lingkungan tanpa AutoCAD)
        self._sim_polyline_area = 100.0
        self._sim_scaled_area = 100.0
        self._sim_text = "DUMMY TEXT"

    def connect(self, launch_if_closed: bool = True) -> Tuple[bool, str]:
        """
        Menghubungkan aplikasi ke AutoCAD Desktop yang sedang berjalan atau membukanya.
        """
        self.last_error = ""
        
        # Jika mode simulasi aktif secara manual
        if self.simulation_mode:
            self.is_connected = True
            return True, "Mode Simulasi Aktif (AutoCAD Virtual)"

        if not PYWIN32_AVAILABLE:
            self.last_error = "Library pywin32 belum terpasang atau sistem bukan Windows."
            return False, self.last_error

        # Coba hubungkan ke AutoCAD yang sedang terbuka
        try:
            self.acad = win32com.client.GetActiveObject("AutoCAD.Application")
            self.is_connected = True
            try:
                self.version_string = f"AutoCAD {self.acad.Caption}"
            except Exception:
                self.version_string = "AutoCAD Desktop Terhubung"
            return True, f"Terhubung ke {self.version_string} (Instance Aktif)"
        except Exception:
            pass

        # Jika belum terbuka dan diizinkan untuk membuka baru
        if launch_if_closed:
            try:
                # Coba beberapa ProgID umum AutoCAD
                prog_ids = [
                    "AutoCAD.Application",
                    "AutoCAD.Application.24", # AutoCAD 2021-2024
                    "AutoCAD.Application.23", # AutoCAD 2019-2020
                    "AutoCAD.Application.22", # AutoCAD 2018
                ]
                for pid in prog_ids:
                    try:
                        self.acad = win32com.client.Dispatch(pid)
                        self.acad.Visible = True
                        self.is_connected = True
                        self.version_string = f"AutoCAD {getattr(self.acad, 'Caption', 'Desktop')}"
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
        Mengembalikan status koneksi AutoCAD saat ini.
        """
        if self.simulation_mode:
            return {
                "connected": True,
                "version": "Mode Simulasi (AutoCAD Virtual)",
                "active_document": "SIMULASI_DRAWING.dwg",
                "is_simulation": True,
                "error": ""
            }
            
        if not self.is_connected or not self.acad:
            return {
                "connected": False,
                "version": "Tidak Terhubung",
                "active_document": "-",
                "is_simulation": False,
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
                "is_simulation": False,
                "error": ""
            }
        except Exception as e:
            self.is_connected = False
            return {
                "connected": False,
                "version": "Terputus",
                "active_document": "-",
                "is_simulation": False,
                "error": f"Koneksi terputus: {str(e)}"
            }

    def open_template(self, template_path: str) -> Tuple[bool, str]:
        """
        Membuka file template DWG di AutoCAD.
        """
        if self.simulation_mode:
            self.active_template_path = template_path
            return True, f"Simulasi: Template {os.path.basename(template_path)} berhasil dibuka."

        ok, msg = self.connect(launch_if_closed=True)
        if not ok:
            return False, msg

        abs_template = os.path.abspath(template_path)
        if not os.path.exists(abs_template):
            return False, f"File template DWG tidak ditemukan di: {abs_template}"

        try:
            # Buka dokumen template
            self.doc = self.acad.Documents.Open(abs_template)
            self.acad.Visible = True
            self.acad.WindowState = 3 # 3 = Maximized
            self.active_template_path = abs_template
            return True, f"Template {os.path.basename(abs_template)} berhasil dibuka di AutoCAD."
        except Exception as e:
            # Alternatif jika dokumen sudah terbuka
            try:
                if self.acad.ActiveDocument and os.path.basename(abs_template).lower() in self.acad.ActiveDocument.Name.lower():
                    self.doc = self.acad.ActiveDocument
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
        """
        if self.simulation_mode:
            return True, f"Simulasi: Gambar denah {os.path.basename(image_path)} dimasukkan ke ModelSpace (0,0,0)."

        if not self.is_connected or not self.acad:
            ok, msg = self.connect()
            if not ok:
                return False, msg

        abs_image = os.path.abspath(image_path)
        if not os.path.exists(abs_image):
            return False, f"File gambar raster tidak ditemukan: {abs_image}"

        try:
            self.doc = self.acad.ActiveDocument
            model_space = self.doc.ModelSpace
            
            # Format titik penyisipan
            pt_variant = to_variant_point(insert_pt[0], insert_pt[1], insert_pt[2])
            rad = math.radians(rotation_deg)
            
            # AddRaster(ImageFileName, InsertionPoint, ScaleFactor, RotationAngle)
            raster_obj = model_space.AddRaster(abs_image, pt_variant, float(scale), float(rad))
            
            # Zoom ke seluruh gambar agar denah terlihat jelas
            try:
                self.acad.ZoomExtents()
            except Exception:
                pass
                
            return True, f"Gambar denah {os.path.basename(abs_image)} berhasil dimasukkan ke AutoCAD ModelSpace."
        except Exception as e:
            return False, f"Gagal memasukkan raster image ke AutoCAD: {str(e)}"

    def get_polyline_area(self) -> Tuple[bool, float, str, str]:
        """
        Meminta operator memilih objek polyline tertutup di AutoCAD, memvalidasi tipe objek dan status tertutup,
        kemudian membaca nilai properti Area.
        
        Mengembalikan: (success, area_m2, entity_handle, message)
        """
        if self.simulation_mode:
            # Mode simulasi mengembalikan nilai luas simulasi
            return True, self._sim_polyline_area, "SIM_HANDLE_1", f"Simulasi: Luas polyline terbaca {self._sim_polyline_area} m²."

        if not self.is_connected or not self.acad:
            ok, msg = self.connect()
            if not ok:
                return False, 0.0, "", msg

        try:
            self.doc = self.acad.ActiveDocument
            utility = self.doc.Utility
            
            # Meminta operator memilih satu objek di AutoCAD
            # Utility.GetEntity(Object, PickedPoint, Prompt)
            picked_obj, _ = utility.GetEntity("Klik/Pilih objek polyline batas bidang tanah di AutoCAD: ")
            
            if not picked_obj:
                return False, 0.0, "", "Tidak ada objek yang dipilih."
                
            obj_name = getattr(picked_obj, "ObjectName", "")
            
            # Validasi tipe objek harus AcDbPolyline atau AcDb2dPolyline
            if obj_name not in ["AcDbPolyline", "AcDb2dPolyline"]:
                return False, 0.0, "", f"Objek yang dipilih adalah '{obj_name}'. Harap pilih objek Polyline tertutup hasil tracing batas bidang!"
                
            # Validasi properti Closed
            is_closed = getattr(picked_obj, "Closed", False)
            if not is_closed:
                return False, 0.0, "", "Polyline belum ditutup (Closed = False). Harap tutup polyline terlebih dahulu di AutoCAD (gunakan perintah PL opsi Close atau PEDIT)."
                
            # Ambil nilai luas
            area = float(getattr(picked_obj, "Area", 0.0))
            if area <= 0.0:
                return False, 0.0, "", "Luas polyline bernilai 0 m² atau tidak valid."
                
            handle = getattr(picked_obj, "Handle", "")
            return True, area, handle, f"Polyline valid! Luas terbaca: {area:.4f} m²"
            
        except Exception as e:
            err_msg = str(e)
            if "User cancelled" in err_msg or "0x80020009" in err_msg:
                return False, 0.0, "", "Pemilihan polyline dibatalkan oleh operator."
            return False, 0.0, "", f"Gagal membaca luas polyline dari AutoCAD: {err_msg}"

    def scale_selected_objects(
        self,
        scale_factor: float,
        base_point: Optional[Tuple[float, float, float]] = None,
        polyline_handle: Optional[str] = None
    ) -> Tuple[bool, float, str]:
        """
        Menerapkan scaling seragam pada objek yang dipilih operator di AutoCAD.
        Setelah scaling, membaca kembali luas polyline untuk verifikasi.
        
        Mengembalikan: (success, final_area_m2, message)
        """
        if self.simulation_mode:
            # Hitung efek scaling simulasi
            self._sim_scaled_area = self._sim_polyline_area * (scale_factor ** 2)
            return True, self._sim_scaled_area, f"Simulasi: Scaling {scale_factor:.6f} berhasil diterapkan. Luas akhir: {self._sim_scaled_area:.4f} m²."

        if not self.is_connected or not self.acad:
            ok, msg = self.connect()
            if not ok:
                return False, 0.0, msg

        if scale_factor <= 0:
            return False, 0.0, "Faktor scaling harus lebih besar dari 0."

        try:
            self.doc = self.acad.ActiveDocument
            utility = self.doc.Utility
            
            # Buat SelectionSet sementara untuk menampung objek yang dipilih operator
            ss_name = "AutoLandScaleSet"
            try:
                self.doc.SelectionSets.Item(ss_name).Delete()
            except Exception:
                pass
                
            ss = self.doc.SelectionSets.Add(ss_name)
            
            # Meminta operator memilih seluruh objek yang akan diskalakan di AutoCAD
            # Utility.Prompt
            try:
                utility.Prompt("\n[AutoLand] Pilih objek yang akan diskalakan (Raster, Polyline, Gambar terkait), lalu tekan ENTER:\n")
                ss.SelectOnScreen()
            except Exception:
                pass
                
            if ss.Count == 0:
                ss.Delete()
                return False, 0.0, "Tidak ada objek yang dipilih untuk diskalakan."
                
            # Menentukan titik dasar (base point)
            if base_point is None:
                try:
                    pt_var = utility.GetPoint(to_variant_point(0, 0, 0), "\n[AutoLand] Klik titik dasar (base point) scaling di AutoCAD: ")
                    base_pt_var = pt_var
                except Exception:
                    # Default jika dibatalkan atau error: gunakan (0,0,0)
                    base_pt_var = to_variant_point(0, 0, 0)
            else:
                base_pt_var = to_variant_point(base_point[0], base_point[1], base_point[2])
                
            # Terapkan ScaleEntity pada setiap objek dalam SelectionSet
            scaled_count = 0
            for i in range(ss.Count):
                obj = ss.Item(i)
                try:
                    obj.ScaleEntity(base_pt_var, float(scale_factor))
                    scaled_count += 1
                except Exception:
                    pass
                    
            ss.Delete()
            
            # Membaca ulang luas polyline jika handle tersedia
            final_area = 0.0
            if polyline_handle:
                try:
                    poly_obj = self.doc.HandleToObject(polyline_handle)
                    if poly_obj and hasattr(poly_obj, "Area"):
                        final_area = float(poly_obj.Area)
                except Exception:
                    pass
                    
            return True, final_area, f"Berhasil menskalakan {scaled_count} objek di AutoCAD dengan faktor {scale_factor:.6f}."
            
        except Exception as e:
            return False, 0.0, f"Gagal menerapkan scaling di AutoCAD: {str(e)}"

    def replace_identity_text(self, new_identity_text: str) -> Tuple[bool, str]:
        """
        Meminta operator memilih objek TEXT atau MTEXT di AutoCAD,
        kemudian mengganti isi teks dengan identitas resmi dokumen.
        """
        if self.simulation_mode:
            self._sim_text = new_identity_text
            return True, f"Simulasi: Teks berhasil diganti menjadi '{new_identity_text}'."

        if not self.is_connected or not self.acad:
            ok, msg = self.connect()
            if not ok:
                return False, msg

        try:
            self.doc = self.acad.ActiveDocument
            utility = self.doc.Utility
            
            # Minta operator memilih objek teks
            picked_obj, _ = utility.GetEntity("\n[AutoLand] Klik objek TEXT atau MTEXT identitas di AutoCAD: ")
            
            if not picked_obj:
                return False, "Tidak ada objek teks yang dipilih."
                
            obj_name = getattr(picked_obj, "ObjectName", "")
            if obj_name not in ["AcDbText", "AcDbMText"]:
                return False, f"Objek yang dipilih adalah '{obj_name}'. Harap pilih objek TEXT atau MTEXT!"
                
            # Ganti TextString
            old_val = getattr(picked_obj, "TextString", "")
            picked_obj.TextString = str(new_identity_text)
            
            try:
                picked_obj.Update()
            except Exception:
                pass
                
            return True, f"Teks identitas berhasil diubah dari '{old_val}' menjadi '{new_identity_text}'."
            
        except Exception as e:
            err_msg = str(e)
            if "User cancelled" in err_msg or "0x80020009" in err_msg:
                return False, "Pemilihan teks dibatalkan oleh operator."
            return False, f"Gagal mengganti teks di AutoCAD: {err_msg}"

    def save_drawing_as(self, output_dwg_path: str, overwrite: bool = False) -> Tuple[bool, str]:
        """
        Menyimpan dokumen AutoCAD aktif sebagai file DWG hasil digitasi.
        """
        abs_output = os.path.abspath(output_dwg_path)
        folder = os.path.dirname(abs_output)
        os.makedirs(folder, exist_ok=True)
        
        if os.path.exists(abs_output) and not overwrite:
            return False, f"File DWG dengan nama '{os.path.basename(abs_output)}' sudah ada. Silakan konfirmasi untuk menimpa."

        if self.simulation_mode:
            # Buat file dummy DWG untuk simulasi
            with open(abs_output, "w", encoding="utf-8") as f:
                f.write(f"AUTOLAND_SIMULATED_DWG: {os.path.basename(abs_output)}\n")
            return True, f"Simulasi: File DWG disimpan ke: {abs_output}"

        if not self.is_connected or not self.acad:
            ok, msg = self.connect()
            if not ok:
                return False, msg

        try:
            self.doc = self.acad.ActiveDocument
            # Simpan sebagai DWG
            self.doc.SaveAs(abs_output)
            return True, f"Dokumen DWG berhasil disimpan ke: {abs_output}"
        except Exception as e:
            return False, f"Gagal menyimpan file DWG: {str(e)}"


# Singleton instance
autocad_service = AutoCADService()
