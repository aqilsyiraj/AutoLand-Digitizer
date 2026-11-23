"""
AutoLand Digitizer - PDF Service
Ekstraksi, rendering preview, dan pemotongan (crop) denah bidang tanah resolusi tinggi dari dokumen PDF.
Menggunakan PyMuPDF (fitz) dan Pillow.
"""

import io
import os
from pathlib import Path
from typing import Tuple, Optional, Dict, Any


class _LazyModule:
    """Pembungkus import lambat: pustaka cuma muat saat pertama diakses."""

    __slots__ = ("_name", "_fallback", "_module")

    def __init__(self, name: str, fallback: str = ""):
        object.__setattr__(self, "_name", name)
        object.__setattr__(self, "_fallback", fallback)
        object.__setattr__(self, "_module", None)

    def _load(self):
        module = object.__getattribute__(self, "_module")
        if module is None:
            name = object.__getattribute__(self, "_name")
            module = None
            if name == "fitz":
                # PyMuPDF 2.x merekomendasikan nama pymupdf; fallback kompatibilitas lama.
                try:
                    module = __import__("pymupdf")
                except ImportError:
                    module = __import__("fitz")
            else:
                module = __import__(name)
            object.__setattr__(self, "_module", module)
        return module

    def __getattr__(self, item):
        return getattr(self._load(), item)


fitz = _LazyModule("fitz")

from PIL import Image  # noqa: E402  (Pillow ringan; tetap sesudah konfigurasi)

from config import TEMPORARY_DIR, ensure_directories

def get_pdf_info(pdf_path: str) -> Dict[str, Any]:
    """
    Mengambil informasi dasar dokumen PDF: jumlah halaman, ukuran halaman, dan metadata.
    """
    if not os.path.exists(pdf_path):
        return {"success": False, "error": "File PDF tidak ditemukan.", "page_count": 0}
        
    try:
        doc = fitz.open(pdf_path)
        count = len(doc)
        pages_info = []
        for i in range(count):
            p = doc[i]
            rect = p.rect
            pages_info.append({
                "page_number": i + 1,
                "width": rect.width,
                "height": rect.height,
            })
            
        doc.close()
        return {
            "success": True,
            "page_count": count,
            "pages": pages_info,
            "filename": os.path.basename(pdf_path),
        }
    except Exception as e:
        return {"success": False, "error": f"Gagal membaca PDF: {str(e)}", "page_count": 0}

def render_pdf_page_to_pixmap(pdf_path: str, page_number: int, dpi: int = 150) -> Optional[bytes]:
    """
    Merender satu halaman PDF ke format gambar PNG (dalam bentuk bytes) untuk ditampilkan pada UI.
    page_number menggunakan basis 1 (halaman 1, 2, dst).
    """
    if not os.path.exists(pdf_path):
        return None
        
    try:
        doc = fitz.open(pdf_path)
        idx = page_number - 1
        if idx < 0 or idx >= len(doc):
            doc.close()
            return None
            
        page = doc[idx]
        zoom = dpi / 72.0
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img_bytes = pix.tobytes("png")
        doc.close()
        return img_bytes
    except Exception as e:
        print(f"Error rendering PDF page: {e}")
        return None

def crop_pdf_region_to_file(
    pdf_path: str,
    page_number: int,
    norm_rect: Tuple[float, float, float, float],
    output_filename: Optional[str] = None,
    dpi: int = 300
) -> Tuple[bool, str]:
    """
    Memotong area denah dari halaman PDF berdasarkan koordinat ternormalisasi (0.0 s/d 1.0)
    dengan resolusi tinggi (default 300 DPI) agar hasil tracing di AutoCAD tajam dan akurat.
    
    norm_rect: (norm_x0, norm_y0, norm_x1, norm_y1)
    """
    ensure_directories()
    if not os.path.exists(pdf_path):
        return False, "File PDF tidak ditemukan."
        
    try:
        doc = fitz.open(pdf_path)
        idx = page_number - 1
        if idx < 0 or idx >= len(doc):
            doc.close()
            return False, f"Halaman {page_number} tidak tersedia dalam PDF."
            
        page = doc[idx]
        p_rect = page.rect
        
        # Ekstrak koordinat ternormalisasi ke koordinat titik halaman PDF
        nx0, ny0, nx1, ny1 = norm_rect
        x0 = min(nx0, nx1) * p_rect.width
        y0 = min(ny0, ny1) * p_rect.height
        x1 = max(nx0, nx1) * p_rect.width
        y1 = max(ny0, ny1) * p_rect.height
        
        # Validasi luas crop
        if (x1 - x0) < 5 or (y1 - y0) < 5:
            doc.close()
            return False, "Area pemotongan terlalu kecil atau tidak valid."
            
        crop_rect = fitz.Rect(x0, y0, x1, y1)
        
        # Render hanya region yang dipotong pada resolusi tinggi
        zoom = dpi / 72.0
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, clip=crop_rect, alpha=False)
        
        if not output_filename:
            import uuid
            output_filename = f"crop_{uuid.uuid4().hex[:8]}.png"
            
        output_path = TEMPORARY_DIR / output_filename
        pix.save(str(output_path))
        doc.close()
        
        return True, str(output_path)
    except Exception as e:
        return False, f"Gagal memotong area PDF: {str(e)}"
