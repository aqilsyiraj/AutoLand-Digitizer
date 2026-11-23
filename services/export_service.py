"""
AutoLand Digitizer - Export Service
Menghasilkan rekapitulasi pekerjaan dalam format Excel (.xlsx), CSV (.csv),
dan paket arsip ZIP berisi seluruh file DWG, berkas koordinat, beserta rekapitulasi.
"""

import importlib
import os
import csv
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional


class _Lazy:
    """Pembungkus import lambat (openpyxl dipakai hanya saat ekspor)."""

    __slots__ = ("_path",)

    def __init__(self, path: str):
        object.__setattr__(self, "_path", path)

    def _resolve(self):
        path = object.__getattribute__(self, "_path")
        module_name, dot, attr = path.rpartition(".")
        if not dot:
            return importlib.import_module(path)
        obj = importlib.import_module(module_name)
        for part in [p for p in attr.split(".") if p]:
            obj = getattr(obj, part)
        return obj

    def __getattr__(self, item):
        return getattr(self._resolve(), item)

    def __call__(self, *args, **kwargs):
        return self._resolve()(*args, **kwargs)


openpyxl = _Lazy("openpyxl")
Font = _Lazy("openpyxl.styles.Font")
PatternFill = _Lazy("openpyxl.styles.PatternFill")
Alignment = _Lazy("openpyxl.styles.Alignment")
Border = _Lazy("openpyxl.styles.Border")
Side = _Lazy("openpyxl.styles.Side")
get_column_letter = _Lazy("openpyxl.utils.get_column_letter")

from config import HASIL_DIGITASI_DIR, STATUS_LABELS, STATUS_SELESAI  # noqa: E402
from database.db import get_batch, get_documents_by_batch, get_batch_stats, add_log  # noqa: E402

def check_batch_readiness(batch_id: int) -> Dict[str, Any]:
    """
    Memeriksa kesiapan batch sebelum ekspor final.
    Mengembalikan daftar dokumen yang belum selesai jika ada.
    """
    stats = get_batch_stats(batch_id)
    docs = get_documents_by_batch(batch_id)
    pending_docs = [d for d in docs if d["status"] != STATUS_SELESAI]
    
    return {
        "is_ready": (len(docs) > 0 and len(pending_docs) == 0),
        "total": len(docs),
        "selesai": stats["selesai"],
        "pending_count": len(pending_docs),
        "pending_docs": pending_docs,
    }

def export_batch_to_excel(batch_id: int, output_filepath: Optional[str] = None) -> Tuple[bool, str]:
    """
    Mengekspor rekapitulasi batch desa ke file Excel (.xlsx) dengan format resmi.
    """
    batch = get_batch(batch_id)
    if not batch:
        return False, "Batch tidak ditemukan."
        
    docs = get_documents_by_batch(batch_id)
    if not docs:
        return False, "Batch ini belum memiliki dokumen untuk diekspor."
        
    # Tentukan lokasi output
    if not output_filepath:
        safe_desa = batch["nama_desa"].replace(" ", "_")
        folder = HASIL_DIGITASI_DIR / f"Batch_{batch_id}_{safe_desa}"
        folder.mkdir(parents=True, exist_ok=True)
        output_filepath = str(folder / f"Rekapitulasi_Digitasi_{safe_desa}_{datetime.now().strftime('%Y%m%d')}.xlsx")
        
    try:
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Rekapitulasi Digitasi"
        ws.views.sheetView[0].showGridLines = True
        
        # Styles
        title_font = Font(name="Segoe UI", size=15, bold=True, color="1E3A8A")
        subtitle_font = Font(name="Segoe UI", size=10, italic=True, color="475569")
        meta_label_font = Font(name="Segoe UI", size=10, bold=True, color="0F172A")
        meta_val_font = Font(name="Segoe UI", size=10, color="1E293B")
        header_font = Font(name="Segoe UI", size=10, bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="1E40AF", end_color="1E40AF", fill_type="solid")
        zebra_fill = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")
        total_font = Font(name="Segoe UI", size=10, bold=True, color="0F172A")
        total_fill = PatternFill(start_color="E2E8F0", end_color="E2E8F0", fill_type="solid")
        
        thin_border = Border(
            left=Side(style="thin", color="CBD5E1"),
            right=Side(style="thin", color="CBD5E1"),
            top=Side(style="thin", color="CBD5E1"),
            bottom=Side(style="thin", color="CBD5E1")
        )
        
        # 1. Judul Header
        ws["A1"] = "REKAPITULASI HASIL DIGITALISASI DOKUMEN PERTANAHAN"
        ws["A1"].font = title_font
        ws["A2"] = f"Aplikasi AutoLand Digitizer — Dibuat pada: {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}"
        ws["A2"].font = subtitle_font
        
        # 2. Metadata Batch
        ws["A4"] = "Desa / Kelurahan:"
        ws["A4"].font = meta_label_font
        ws["B4"] = batch["nama_desa"]
        ws["B4"].font = meta_val_font
        
        ws["D4"] = "Kecamatan:"
        ws["D4"].font = meta_label_font
        ws["E4"] = batch["kecamatan"]
        ws["E4"].font = meta_val_font
        
        ws["A5"] = "Kabupaten:"
        ws["A5"].font = meta_label_font
        ws["B5"] = batch["kabupaten"]
        ws["B5"].font = meta_val_font
        
        ws["D5"] = "Tanggal Batch:"
        ws["D5"].font = meta_label_font
        ws["E5"] = batch["tanggal"]
        ws["E5"].font = meta_val_font
        
        ws["A6"] = "Operator:"
        ws["A6"].font = meta_label_font
        ws["B6"] = batch.get("operator", "-") or "-"
        ws["B6"].font = meta_val_font
        
        ws["D6"] = "Keterangan:"
        ws["D6"].font = meta_label_font
        ws["E6"] = batch.get("keterangan", "-") or "-"
        ws["E6"].font = meta_val_font
        
        # 3. Tabel Kolom Header (Baris 8)
        headers = [
            "No", "Nama PDF", "Identitas", "Jenis Hak", "Nomor Hak",
            "Nomor GS", "Tahun", "Luas Dokumen (m²)", "Luas Akhir (m²)",
            "Faktor Scaling", "Metode Deteksi", "Keyakinan Deteksi",
            "Status", "File DWG", "File Koordinat"
        ]
        
        start_row = 8
        for col_idx, header_text in enumerate(headers, start=1):
            cell = ws.cell(row=start_row, column=col_idx, value=header_text)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            cell.border = thin_border
            
        ws.row_dimensions[start_row].height = 28
        
        # 4. Data Dokumen
        current_row = start_row + 1
        total_luas_dokumen = 0.0
        total_luas_akhir = 0.0
        
        for idx, doc in enumerate(docs, start=1):
            luas_doc = doc.get("luas_dokumen") or 0.0
            luas_fin = doc.get("luas_akhir") or 0.0
            scale_fac = doc.get("faktor_scaling") or 0.0
            dwg_filename = os.path.basename(doc.get("path_dwg", "")) if doc.get("path_dwg") else "-"
            coord_filename = os.path.basename(doc.get("koordinat_csv", "")) if doc.get("koordinat_csv") else "-"
            metode = doc.get("detection_method") or "-"
            keyakinan = doc.get("detection_confidence")
            keyakinan_str = f"{float(keyakinan) * 100:.0f}%" if keyakinan else "-"
            
            total_luas_dokumen += luas_doc
            total_luas_akhir += luas_fin
            
            row_data = [
                idx,
                doc.get("nama_pdf", "-"),
                doc.get("identitas_dokumen", "-"),
                doc.get("jenis_hak", "-"),
                doc.get("nomor_hak", "-"),
                doc.get("nomor_gs", "-"),
                doc.get("tahun", "-"),
                luas_doc if luas_doc > 0 else "-",
                luas_fin if luas_fin > 0 else "-",
                f"{scale_fac:.6f}" if scale_fac > 0 else "-",
                metode,
                keyakinan_str,
                STATUS_LABELS.get(doc.get("status", "-"), doc.get("status", "-")),
                dwg_filename,
                coord_filename
            ]
            
            is_zebra = (idx % 2 == 0)
            for col_idx, val in enumerate(row_data, start=1):
                cell = ws.cell(row=current_row, column=col_idx, value=val)
                cell.font = Font(name="Segoe UI", size=9)
                cell.border = thin_border
                if is_zebra:
                    cell.fill = zebra_fill
                    
                # Alignment
                if col_idx in [1, 4, 7, 10, 11, 12, 13]:
                    cell.alignment = Alignment(horizontal="center", vertical="center")
                elif col_idx in [8, 9]:
                    cell.alignment = Alignment(horizontal="right", vertical="center")
                    if isinstance(val, (int, float)):
                        cell.number_format = "#,##0.00"
                else:
                    cell.alignment = Alignment(horizontal="left", vertical="center")
                    
            ws.row_dimensions[current_row].height = 20
            current_row += 1
            
        # 5. Baris Total Summary
        ws.merge_cells(start_row=current_row, start_column=1, end_row=current_row, end_column=7)
        total_label_cell = ws.cell(row=current_row, column=1, value="TOTAL:")
        total_label_cell.font = total_font
        total_label_cell.alignment = Alignment(horizontal="right", vertical="center")
        
        # Format sel gabungan
        for c in range(1, 8):
            cell = ws.cell(row=current_row, column=c)
            cell.fill = total_fill
            cell.border = thin_border
            
        c_doc = ws.cell(row=current_row, column=8, value=total_luas_dokumen)
        c_doc.font = total_font
        c_doc.fill = total_fill
        c_doc.alignment = Alignment(horizontal="right", vertical="center")
        c_doc.number_format = "#,##0.00"
        c_doc.border = thin_border
        
        c_fin = ws.cell(row=current_row, column=9, value=total_luas_akhir)
        c_fin.font = total_font
        c_fin.fill = total_fill
        c_fin.alignment = Alignment(horizontal="right", vertical="center")
        c_fin.number_format = "#,##0.00"
        c_fin.border = thin_border
        
        for c in range(10, 16):
            cell = ws.cell(row=current_row, column=c, value="")
            cell.fill = total_fill
            cell.border = thin_border
            
        ws.row_dimensions[current_row].height = 24
        
        # 6. Auto-fit column widths
        for col in ws.columns:
            max_len = 0
            col_letter = get_column_letter(col[0].column)
            for cell in col:
                val_str = str(cell.value or '')
                if cell.row < 8:  # Jangan hitung baris judul untuk lebar kolom
                    continue
                if len(val_str) > max_len:
                    max_len = len(val_str)
            ws.column_dimensions[col_letter].width = max(max_len + 4, 12)
            
        wb.save(output_filepath)
        add_log(aktivitas="Ekspor Excel", detail=f"Rekapitulasi diekspor: {os.path.basename(output_filepath)}", batch_id=batch_id)
        return True, output_filepath
    except Exception as e:
        return False, f"Gagal mengekspor Excel: {str(e)}"

def export_batch_to_csv(batch_id: int, output_filepath: Optional[str] = None) -> Tuple[bool, str]:
    """
    Mengekspor rekapitulasi batch ke format CSV.
    """
    batch = get_batch(batch_id)
    if not batch:
        return False, "Batch tidak ditemukan."
        
    docs = get_documents_by_batch(batch_id)
    if not docs:
        return False, "Batch ini belum memiliki dokumen."
        
    if not output_filepath:
        safe_desa = batch["nama_desa"].replace(" ", "_")
        folder = HASIL_DIGITASI_DIR / f"Batch_{batch_id}_{safe_desa}"
        folder.mkdir(parents=True, exist_ok=True)
        output_filepath = str(folder / f"Rekapitulasi_Digitasi_{safe_desa}_{datetime.now().strftime('%Y%m%d')}.csv")
        
    try:
        headers = [
            "No", "Nama PDF", "Identitas", "Jenis Hak", "Nomor Hak",
            "Nomor GS", "Tahun", "Luas Dokumen (m2)", "Luas Akhir (m2)",
            "Faktor Scaling", "Metode Deteksi", "Keyakinan Deteksi",
            "Status", "File DWG", "File Koordinat"
        ]
        
        with open(output_filepath, mode="w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f, delimiter=";")
            # Metadata
            writer.writerow(["REKAPITULASI DIGITALISASI DOKUMEN PERTANAHAN"])
            writer.writerow([f"Desa: {batch['nama_desa']}", f"Kecamatan: {batch['kecamatan']}", f"Kabupaten: {batch['kabupaten']}"])
            writer.writerow([f"Tanggal: {batch['tanggal']}", f"Operator: {batch.get('operator', '-') or '-'}"])
            writer.writerow([])
            writer.writerow(headers)
            
            for idx, doc in enumerate(docs, start=1):
                dwg_filename = os.path.basename(doc.get("path_dwg", "")) if doc.get("path_dwg") else "-"
                coord_filename = os.path.basename(doc.get("koordinat_csv", "")) if doc.get("koordinat_csv") else "-"
                metode = doc.get("detection_method") or "-"
                keyakinan = doc.get("detection_confidence")
                keyakinan_str = f"{float(keyakinan) * 100:.0f}%" if keyakinan else "-"
                writer.writerow([
                    idx,
                    doc.get("nama_pdf", "-"),
                    doc.get("identitas_dokumen", "-"),
                    doc.get("jenis_hak", "-"),
                    doc.get("nomor_hak", "-"),
                    doc.get("nomor_gs", "-"),
                    doc.get("tahun", "-"),
                    doc.get("luas_dokumen") or 0.0,
                    doc.get("luas_akhir") or 0.0,
                    f"{doc.get('faktor_scaling', 0.0):.6f}" if doc.get("faktor_scaling") else "-",
                    metode,
                    keyakinan_str,
                    STATUS_LABELS.get(doc.get("status", "-"), doc.get("status", "-")),
                    dwg_filename,
                    coord_filename
                ])
                
        add_log(aktivitas="Ekspor CSV", detail=f"Rekapitulasi CSV diekspor: {os.path.basename(output_filepath)}", batch_id=batch_id)
        return True, output_filepath
    except Exception as e:
        return False, f"Gagal mengekspor CSV: {str(e)}"

def export_batch_to_zip(batch_id: int, output_filepath: Optional[str] = None) -> Tuple[bool, str]:
    """
    Membuat paket ZIP berisi seluruh file DWG, berkas koordinat, dan rekapitulasi Excel.
    """
    batch = get_batch(batch_id)
    if not batch:
        return False, "Batch tidak ditemukan."
        
    docs = get_documents_by_batch(batch_id)
    safe_desa = batch["nama_desa"].replace(" ", "_")
    batch_folder = HASIL_DIGITASI_DIR / f"Batch_{batch_id}_{safe_desa}"
    batch_folder.mkdir(parents=True, exist_ok=True)
    
    if not output_filepath:
        output_filepath = str(batch_folder / f"Paket_Hasil_Digitasi_{safe_desa}_{datetime.now().strftime('%Y%m%d')}.zip")
        
    try:
        # Buat Excel rekapitulasi terlebih dahulu di dalam folder batch
        temp_excel = str(batch_folder / f"Rekapitulasi_{safe_desa}.xlsx")
        success_xl, res_xl = export_batch_to_excel(batch_id, temp_excel)
        
        with zipfile.ZipFile(output_filepath, "w", zipfile.ZIP_DEFLATED) as zf:
            if success_xl and os.path.exists(temp_excel):
                zf.write(temp_excel, arcname=f"Rekapitulasi_{safe_desa}.xlsx")
                
            # Masukkan DWG, gambar denah yang direferensikan DWG, dan berkas koordinat.
            dwg_count = 0
            denah_count = 0
            coord_count = 0
            for doc in docs:
                dwg_path = doc.get("path_dwg")
                if dwg_path and os.path.exists(dwg_path):
                    dwg_name = os.path.basename(dwg_path)
                    zf.write(dwg_path, arcname=f"DWG/{dwg_name}")
                    dwg_count += 1

                denah_path = doc.get("path_crop")
                if denah_path and os.path.exists(denah_path):
                    zf.write(
                        denah_path,
                        arcname=f"Gambar_Denah/{os.path.basename(denah_path)}",
                    )
                    denah_count += 1

                for field in ("koordinat_csv", "koordinat_json"):
                    coord_path = doc.get(field)
                    if coord_path and os.path.exists(coord_path):
                        zf.write(coord_path, arcname=f"Koordinat/{os.path.basename(coord_path)}")
                        coord_count += 1

        add_log(
            aktivitas="Ekspor ZIP",
            detail=(
                f"Paket ZIP dibuat ({dwg_count} DWG, {denah_count} gambar denah, "
                f"{coord_count} berkas koordinat): {os.path.basename(output_filepath)}"
            ),
            batch_id=batch_id,
        )
        return True, output_filepath
    except Exception as e:
        return False, f"Gagal membuat file ZIP: {str(e)}"
