"""
AutoLand Digitizer - Geometry Service
Perhitungan faktor scaling, selisih luas, dan verifikasi geometri bidang tanah.
Rumus: Faktor Scaling = sqrt(Luas Dokumen / Luas Polyline AutoCAD)
"""

import math
from typing import Dict, Any, Tuple

def calculate_scale_factor(luas_dokumen: float, luas_polyline: float) -> Tuple[float, str]:
    """
    Menghitung faktor scaling seragam (uniform scale factor) untuk AutoCAD.
    Faktor = sqrt(Luas Dokumen / Luas Polyline)
    
    Mengembalikan (faktor_scaling, pesan_error).
    Jika perhitungan valid, pesan_error adalah string kosong.
    """
    if luas_dokumen <= 0:
        return 0.0, "Luas dokumen harus lebih besar dari 0 m²."
        
    if luas_polyline <= 0:
        return 0.0, "Luas polyline hasil deteksi harus lebih besar dari 0 m²."
        
    try:
        ratio = luas_dokumen / luas_polyline
        scale_factor = math.sqrt(ratio)
        return scale_factor, ""
    except Exception as e:
        return 0.0, f"Gagal menghitung faktor scaling: {str(e)}"

def analyze_scaling(luas_dokumen: float, luas_awal_polyline: float) -> Dict[str, Any]:
    """
    Menghasilkan data analisis lengkap sebelum scaling diterapkan.
    """
    scale_factor, err = calculate_scale_factor(luas_dokumen, luas_awal_polyline)
    if err:
        return {
            "success": False,
            "error": err,
            "luas_dokumen": luas_dokumen,
            "luas_awal": luas_awal_polyline,
            "faktor_scaling": 0.0,
            "selisih_awal": 0.0,
        }
        
    selisih = abs(luas_dokumen - luas_awal_polyline)
    persen_perubahan = ((scale_factor - 1.0) * 100)
    
    return {
        "success": True,
        "error": "",
        "luas_dokumen": round(luas_dokumen, 4),
        "luas_awal": round(luas_awal_polyline, 4),
        "selisih_awal": round(selisih, 4),
        "faktor_scaling": round(scale_factor, 6),
        "faktor_scaling_raw": scale_factor,
        "persen_skala": round(persen_perubahan, 2),
    }

def verify_final_area(luas_dokumen: float, luas_akhir_polyline: float, toleransi_persen: float = 0.5) -> Dict[str, Any]:
    """
    Membandingkan luas polyline setelah scaling dengan luas target dokumen.
    Mengembalikan evaluasi akurasi dan kesesuaian toleransi.
    """
    selisih = abs(luas_dokumen - luas_akhir_polyline)
    persen_error = (selisih / luas_dokumen * 100) if luas_dokumen > 0 else 0.0
    is_acceptable = persen_error <= toleransi_persen
    
    return {
        "luas_target": round(luas_dokumen, 4),
        "luas_akhir": round(luas_akhir_polyline, 4),
        "selisih": round(selisih, 4),
        "persen_error": round(persen_error, 3),
        "is_acceptable": is_acceptable,
        "toleransi_persen": toleransi_persen,
        "status_evaluasi": "Sesuai Toleransi" if is_acceptable else "Perlu Periksa Ulang",
    }
