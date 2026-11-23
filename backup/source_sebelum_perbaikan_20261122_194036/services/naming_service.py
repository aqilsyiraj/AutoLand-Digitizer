"""
AutoLand Digitizer - Naming Service
Standarisasi pembuatan identitas dokumen pertanahan dan sanitasi nama file Windows.
Format: [Awalan Hak] [Nomor Hak] [Nomor GS]/[Tahun]
Contoh: M. 1342 GS1152/1998
"""

import re
from typing import Optional, Tuple
from config import JENIS_HAK_MAP, AWALAN_KE_KODE

def normalize_gs_number(nomor_gs: str) -> str:
    """
    Menormalkan nomor gambar situasi.
    Jika pengguna hanya memasukkan angka, otomatis tambahkan awalan 'GS'.
    Contoh: '1152' -> 'GS1152', 'GS1152' -> 'GS1152', 'GS 1152' -> 'GS1152'.
    """
    clean = nomor_gs.strip().upper()
    # Hapus spasi dan titik internal jika ada
    clean = clean.replace(" ", "").replace(".", "")
    if not clean.startswith("GS"):
        clean = f"GS{clean}"
    return clean

def get_awalan_hak(kode_atau_awalan: str) -> str:
    """
    Mengambil awalan jenis hak (M., B., P., W.) dari kode hak atau awalan.
    """
    val = kode_atau_awalan.strip()
    if val in JENIS_HAK_MAP:
        return JENIS_HAK_MAP[val]["awalan"]
    
    # Periksa apakah sudah berbentuk awalan langsung
    val_upper = val.upper()
    if not val_upper.endswith("."):
        val_upper = val_upper + "."
        
    for k, v in JENIS_HAK_MAP.items():
        if v["awalan"] == val_upper:
            return v["awalan"]
            
    # Default jika tidak ditemukan
    return "M."

def format_document_identity(kode_hak: str, nomor_hak: str, nomor_gs: str, tahun: str) -> str:
    """
    Membentuk identitas resmi dokumen pertanahan.
    Format: 'M. 1342 GS1152/1998'
    """
    awalan = get_awalan_hak(kode_hak)
    nomor_hak_clean = nomor_hak.strip()
    gs_clean = normalize_gs_number(nomor_gs)
    tahun_clean = str(tahun).strip()
    
    return f"{awalan} {nomor_hak_clean} {gs_clean}/{tahun_clean}"

def sanitize_filename(identity: str, extension: str = ".dwg") -> str:
    """
    Mengubah identitas dokumen menjadi nama file yang aman untuk sistem operasi Windows.
    Menghilangkan karakter terlarang: \\ / : * ? " < > |
    Contoh: 'M. 1342 GS1152/1998' -> 'M_1342_GS1152_1998.dwg'
    """
    # Ganti karakter khusus dan spasi
    safe_name = identity.replace("/", "_").replace("\\", "_").replace(" ", "_")
    safe_name = safe_name.replace(":", "_").replace("*", "_").replace("?", "_")
    safe_name = safe_name.replace('"', "_").replace("<", "_").replace(">", "_").replace("|", "_")
    safe_name = safe_name.replace(".", "_")
    
    # Hapus garis bawah ganda jika ada
    safe_name = re.sub(r'_+', '_', safe_name).strip('_')
    
    if not extension.startswith('.'):
        extension = '.' + extension
        
    return f"{safe_name}{extension}"

def validate_document_input(kode_hak: str, nomor_hak: str, nomor_gs: str, tahun: str, luas: float) -> Tuple[bool, str]:
    """
    Memvalidasi seluruh input data dokumen pertanahan.
    Mengembalikan (is_valid, error_message).
    """
    if not str(kode_hak).strip():
        return False, "Jenis Hak wajib dipilih."
        
    if not str(nomor_hak).strip():
        return False, "Nomor Hak tidak boleh kosong."
        
    if not str(nomor_gs).strip():
        return False, "Nomor Gambar Situasi (GS) tidak boleh kosong."
        
    tahun_str = str(tahun).strip()
    if not tahun_str or not tahun_str.isdigit() or len(tahun_str) != 4:
        return False, "Tahun dokumen harus berupa 4 digit angka (contoh: 1998)."
        
    try:
        luas_val = float(luas)
        if luas_val <= 0:
            return False, "Luas dokumen harus bernilai numerik positif lebih dari 0 m²."
    except (ValueError, TypeError):
        return False, "Luas dokumen harus berupa angka yang valid."
        
    return True, ""
