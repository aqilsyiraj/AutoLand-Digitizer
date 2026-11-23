"""
AutoLand Digitizer - Backup & Work Package Service
Mendukung pencadangan (backup) dan pemulihan (restore) database lokal,
serta ekspor/impor paket pekerjaan offline untuk pertukaran data via flashdisk.
"""

import os
import shutil
import sqlite3
import zipfile
import json
from datetime import datetime
from pathlib import Path
from typing import Tuple, Dict, Any, Optional

from config import (
    DB_PATH,
    BACKUP_DIR,
    DATA_DIR,
    DOKUMEN_MASUK_DIR,
    HASIL_DIGITASI_DIR,
    TEMPORARY_DIR,
    COORDINATE_DIR_NAME,
    ensure_directories
)
from database.db import get_connection, add_log, create_batch, create_document, update_document

def create_database_backup(custom_dest_folder: Optional[str] = None) -> Tuple[bool, str]:
    """
    Membuat salinan cadangan database lokal autoland.db dengan timestamp.
    """
    ensure_directories()
    dest_dir = Path(custom_dest_folder) if custom_dest_folder else BACKUP_DIR
    dest_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"autoland_backup_{timestamp}.db"
    target_path = dest_dir / backup_filename
    
    src_conn = None
    dst_conn = None
    try:
        src_conn = sqlite3.connect(str(DB_PATH))
        dst_conn = sqlite3.connect(str(target_path))
        src_conn.backup(dst_conn)
        add_log(aktivitas="Backup Database", detail=f"Database dicadangkan ke: {target_path.name}")
        return True, str(target_path)
    except Exception as e:
        return False, f"Gagal membuat backup database: {str(e)}"
    finally:
        if dst_conn:
            dst_conn.close()
        if src_conn:
            src_conn.close()

def restore_database_backup(backup_file_path: str) -> Tuple[bool, str]:
    """
    Memulihkan database lokal dari file cadangan .db.
    Membuat cadangan sementara file lama sebelum menimpa.
    """
    src_file = Path(backup_file_path)
    if not src_file.exists():
        return False, "File cadangan tidak ditemukan."
        
    test_conn = None
    try:
        # Verifikasi file adalah database SQLite yang valid
        test_conn = sqlite3.connect(str(src_file))
        cursor = test_conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='batches';")
        if not cursor.fetchone():
            return False, "File yang dipilih bukan database AutoLand Digitizer yang valid."
    except Exception as e:
        return False, f"File backup tidak dapat diverifikasi: {str(e)}"
    finally:
        if test_conn:
            test_conn.close()
            
    backup_conn = None
    current_conn = None
    try:
        # Simpan backup sementara sebelum menimpa
        temp_backup = DB_PATH.with_suffix(".db.restore_backup")
        if DB_PATH.exists():
            shutil.copy2(str(DB_PATH), str(temp_backup))
            
        # Pulihkan dengan SQLite backup API
        backup_conn = sqlite3.connect(str(src_file))
        current_conn = sqlite3.connect(str(DB_PATH))
        backup_conn.backup(current_conn)
                
        if temp_backup.exists():
            temp_backup.unlink()
            
        add_log(aktivitas="Restore Database", detail=f"Database dipulihkan dari: {src_file.name}")
        return True, "Database berhasil dipulihkan."
    except Exception as e:
        return False, f"Gagal memulihkan database: {str(e)}"
    finally:
        if backup_conn:
            backup_conn.close()
        if current_conn:
            current_conn.close()

def export_work_package(batch_id: int, target_zip_path: str) -> Tuple[bool, str]:
    """
    Mengekspor batch beserta dokumen, denah crop, DWG, koordinat, dan metadata ke dalam file ZIP
    agar dapat dipindahkan antar komputer secara offline menggunakan flashdisk.
    """
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM batches WHERE id = ?", (batch_id,))
            batch = cursor.fetchone()
            if not batch:
                return False, f"Batch ID {batch_id} tidak ditemukan."
                
            cursor.execute("SELECT * FROM documents WHERE batch_id = ?", (batch_id,))
            docs = [dict(row) for row in cursor.fetchall()]
            
            metadata = {
                "app": "AutoLand Digitizer",
                "version": "1.0",
                "exported_at": datetime.now().isoformat(),
                "batch": dict(batch),
                "documents": docs
            }
        
        target_zip = Path(target_zip_path)
        target_zip.parent.mkdir(parents=True, exist_ok=True)
        
        with zipfile.ZipFile(str(target_zip), 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("metadata.json", json.dumps(metadata, indent=2))
            
            for d in docs:
                pdf_path = d["path_pdf"]
                if pdf_path and os.path.exists(pdf_path):
                    zf.write(pdf_path, arcname=f"pdfs/{os.path.basename(pdf_path)}")
                crop_path = d["path_crop"]
                if crop_path and os.path.exists(crop_path):
                    zf.write(crop_path, arcname=f"crops/{os.path.basename(crop_path)}")
                dwg_path = d["path_dwg"]
                if dwg_path and os.path.exists(dwg_path):
                    zf.write(dwg_path, arcname=f"dwg/{os.path.basename(dwg_path)}")

                for field in ("koordinat_csv", "koordinat_json"):
                    coord_path = d.get(field)
                    if coord_path and os.path.exists(coord_path):
                        zf.write(
                            coord_path,
                            arcname=f"{COORDINATE_DIR_NAME}/{os.path.basename(coord_path)}",
                        )

        add_log(aktivitas="Ekspor Paket", detail=f"Ekspor paket pekerjaan: {target_zip.name}", batch_id=batch_id)
        return True, str(target_zip)
    except Exception as e:
        return False, f"Gagal mengekspor paket pekerjaan: {str(e)}"

def import_work_package(zip_path: str) -> Tuple[bool, str]:
    """
    Mengimpor paket pekerjaan dari file ZIP ke komputer lokal.
    """
    src_zip = Path(zip_path)
    if not src_zip.exists():
        return False, "File paket pekerjaan tidak ditemukan."
        
    try:
        ensure_directories()
        with zipfile.ZipFile(str(src_zip), 'r') as zf:
            if "metadata.json" not in zf.namelist():
                return False, "Format file tidak valid (tidak ada metadata.json)."
                
            metadata = json.loads(zf.read("metadata.json").decode('utf-8'))
            batch_data = metadata.get("batch")
            documents_data = metadata.get("documents", [])
            
            if not batch_data:
                return False, "Data batch tidak valid dalam paket."
                
            batch_name = f"{batch_data['nama_desa']} (Imported)"
            new_batch_id = create_batch(
                nama_desa=batch_name,
                kecamatan=batch_data.get("kecamatan", ""),
                kabupaten=batch_data.get("kabupaten", ""),
                tanggal=batch_data.get("tanggal", datetime.now().strftime("%Y-%m-%d")),
                operator=batch_data.get("operator", ""),
                keterangan=f"Diimpor dari paket: {src_zip.name}"
            )
            
            imported_count = 0
            for doc in documents_data:
                extracted_pdf_path = ""
                pdf_arcname = f"pdfs/{doc.get('nama_pdf', '')}"
                if pdf_arcname in zf.namelist():
                    dest_pdf = DOKUMEN_MASUK_DIR / f"import_{new_batch_id}_{doc.get('nama_pdf', '')}"
                    with open(dest_pdf, "wb") as f:
                        f.write(zf.read(pdf_arcname))
                    extracted_pdf_path = str(dest_pdf)
                else:
                    extracted_pdf_path = doc.get("path_pdf", "")
                    
                batch_output_folder = HASIL_DIGITASI_DIR / f"Batch_{new_batch_id}_{batch_name.replace(' ', '_')}"
                batch_output_folder.mkdir(parents=True, exist_ok=True)
                denah_folder = batch_output_folder / "Gambar_Denah"
                denah_folder.mkdir(parents=True, exist_ok=True)

                extracted_crop_path = ""
                crop_basename = os.path.basename(doc.get("path_crop", ""))
                crop_arcname = f"crops/{crop_basename}"
                if crop_basename and crop_arcname in zf.namelist():
                    dest_crop = denah_folder / crop_basename
                    with open(dest_crop, "wb") as f:
                        f.write(zf.read(crop_arcname))
                    extracted_crop_path = str(dest_crop)


                extracted_dwg_path = ""
                dwg_basename = os.path.basename(doc.get("path_dwg", ""))
                dwg_arcname = f"dwg/{dwg_basename}"
                if dwg_basename and dwg_arcname in zf.namelist():
                    dest_dwg = batch_output_folder / dwg_basename
                    with open(dest_dwg, "wb") as f:
                        f.write(zf.read(dwg_arcname))
                    extracted_dwg_path = str(dest_dwg)

                extracted_coords = {}
                for field in ("koordinat_csv", "koordinat_json"):
                    coord_basename = os.path.basename(doc.get(field, "") or "")
                    coord_arcname = f"{COORDINATE_DIR_NAME}/{coord_basename}"
                    if coord_basename and coord_arcname in zf.namelist():
                        coord_folder = batch_output_folder / COORDINATE_DIR_NAME
                        coord_folder.mkdir(parents=True, exist_ok=True)
                        dest_coord = coord_folder / coord_basename
                        with open(dest_coord, "wb") as f:
                            f.write(zf.read(coord_arcname))
                        extracted_coords[field] = str(dest_coord)

                imported_doc_id = create_document(
                    batch_id=new_batch_id,
                    nama_pdf=doc.get("nama_pdf", "dokumen.pdf"),
                    path_pdf=extracted_pdf_path,
                    halaman_pdf=doc.get("halaman_pdf", 1),
                    path_crop=extracted_crop_path,
                    jenis_hak=doc.get("jenis_hak", ""),
                    kode_hak=doc.get("kode_hak", ""),
                    nomor_hak=doc.get("nomor_hak", ""),
                    nomor_gs=doc.get("nomor_gs", ""),
                    tahun=doc.get("tahun", ""),
                    identitas_dokumen=doc.get("identitas_dokumen", ""),
                    luas_dokumen=doc.get("luas_dokumen"),
                    status=doc.get("status", "MENUNGGU")
                )
                update_document(
                    imported_doc_id,
                    path_dwg=extracted_dwg_path,
                    koordinat_csv=extracted_coords.get("koordinat_csv", ""),
                    koordinat_json=extracted_coords.get("koordinat_json", ""),
                    luas_awal=doc.get("luas_awal"),
                    luas_akhir=doc.get("luas_akhir"),
                    faktor_scaling=doc.get("faktor_scaling"),
                    completed_at=doc.get("completed_at"),
                    crop_box_json=doc.get("crop_box_json"),
                    crop_dpi=doc.get("crop_dpi"),
                    detected_vertices_json=doc.get("detected_vertices_json"),
                    detection_method=doc.get("detection_method"),
                    detection_confidence=doc.get("detection_confidence"),
                    detected_area_px=doc.get("detected_area_px"),
                    detected_area_m2=doc.get("detected_area_m2"),
                    scale_m_per_px=doc.get("scale_m_per_px"),
                    is_auto_detected=doc.get("is_auto_detected"),
                    detection_revision=doc.get("detection_revision"),
                    auto_detected_at=doc.get("auto_detected_at"),
                )
                imported_count += 1
                
        return True, f"Paket berhasil diimpor: Batch ID {new_batch_id} dengan {imported_count} dokumen."
    except Exception as e:
        return False, f"Gagal mengimpor paket pekerjaan: {str(e)}"
