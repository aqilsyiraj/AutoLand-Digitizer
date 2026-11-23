"""
AutoLand Digitizer - Image Service
Pengolahan gambar hasil crop denah, rotasi 90 derajat, penyesuaian kontras untuk mempermudah tracing.
"""

import os
from PIL import Image, ImageEnhance
from typing import Tuple, Optional

def rotate_image(image_path: str, degrees: int) -> Tuple[bool, str]:
    """
    Memutar gambar hasil crop dengan sudut tertentu (90, 180, 270 derajat).
    """
    if not os.path.exists(image_path):
        return False, "File gambar tidak ditemukan."
        
    try:
        with Image.open(image_path) as img:
            rotated = img.rotate(-degrees, expand=True) # searah jarum jam jika positif
            rotated.save(image_path)
        return True, image_path
    except Exception as e:
        return False, f"Gagal memutar gambar: {str(e)}"

def enhance_image_contrast(image_path: str, factor: float = 1.3) -> Tuple[bool, str]:
    """
    Meningkatkan kontras gambar denah agar garis batas bidang lebih tegas saat di-trace.
    """
    if not os.path.exists(image_path):
        return False, "File gambar tidak ditemukan."
        
    try:
        with Image.open(image_path) as img:
            enhancer = ImageEnhance.Contrast(img)
            enhanced = enhancer.enhance(factor)
            enhanced.save(image_path)
        return True, image_path
    except Exception as e:
        return False, f"Gagal meningkatkan kontras: {str(e)}"
