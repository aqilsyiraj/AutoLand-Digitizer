"""
AutoLand Digitizer - Database Manager
Manajemen database SQLite lokal, transaksi aman, foreign keys, dan operasi CRUD.
Menggunakan context manager untuk penutupan koneksi yang bersih.
"""

import sqlite3
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
from contextlib import contextmanager

from config import (
    DB_PATH,
    ensure_directories,
    STATUS_MENUNGGU,
    STATUS_PDF_DIPROSES,
    STATUS_MENUNGGU_TRACING,
    STATUS_MENUNGGU_SCALING,
    STATUS_MENUNGGU_VERIFIKASI,
    STATUS_SELESAI,
    STATUS_GAGAL,
)

@contextmanager
def get_connection():
    """Membuka koneksi ke database SQLite lokal dengan context manager yang menjamin penutupan koneksi."""
    ensure_directories()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    """Menginisialisasi tabel-tabel database jika belum ada."""
    ensure_directories()
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Tabel Batches
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS batches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nama_desa TEXT NOT NULL,
            kecamatan TEXT NOT NULL,
            kabupaten TEXT NOT NULL,
            tanggal TEXT NOT NULL,
            operator TEXT,
            keterangan TEXT,
            created_at TEXT DEFAULT (datetime('now', 'localtime'))
        );
        """)

        # Tabel Documents
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id INTEGER NOT NULL REFERENCES batches(id) ON DELETE CASCADE,
            nama_pdf TEXT NOT NULL,
            path_pdf TEXT NOT NULL,
            halaman_pdf INTEGER DEFAULT 1,
            path_crop TEXT,
            jenis_hak TEXT,
            kode_hak TEXT,
            nomor_hak TEXT,
            nomor_gs TEXT,
            tahun TEXT,
            identitas_dokumen TEXT,
            luas_dokumen REAL,
            luas_awal REAL,
            luas_akhir REAL,
            faktor_scaling REAL,
            status TEXT DEFAULT 'MENUNGGU',
            path_dwg TEXT,
            created_at TEXT DEFAULT (datetime('now', 'localtime')),
            updated_at TEXT DEFAULT (datetime('now', 'localtime')),
            completed_at TEXT
        );
        """)

        # Tabel Activity Logs
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS activity_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id INTEGER REFERENCES batches(id) ON DELETE SET NULL,
            document_id INTEGER REFERENCES documents(id) ON DELETE SET NULL,
            aktivitas TEXT NOT NULL,
            detail TEXT,
            timestamp TEXT DEFAULT (datetime('now', 'localtime'))
        );
        """)

        # Tabel Settings
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS app_settings (
            key TEXT PRIMARY KEY,
            value TEXT
        );
        """)

        # Indeks untuk efisiensi query
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_doc_batch ON documents(batch_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_doc_status ON documents(status);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_doc_identitas ON documents(identitas_dokumen);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_logs_batch ON activity_logs(batch_id);")

        conn.commit()

# ==================== BATCH OPERATIONS ====================

def create_batch(nama_desa: str, kecamatan: str, kabupaten: str, tanggal: str, operator: str = "", keterangan: str = "") -> int:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO batches (nama_desa, kecamatan, kabupaten, tanggal, operator, keterangan)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (nama_desa, kecamatan, kabupaten, tanggal, operator, keterangan))
        batch_id = cursor.lastrowid
        conn.commit()
        
        # Log aktivitas
        add_log(conn, aktivitas="Buat Batch", detail=f"Membuat batch baru: Desa {nama_desa}, {kecamatan}, {kabupaten}", batch_id=batch_id)
        return batch_id

def get_batch(batch_id: int) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM batches WHERE id = ?", (batch_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

def get_all_batches() -> List[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM batches ORDER BY id DESC")
        return [dict(row) for row in cursor.fetchall()]

def update_batch(batch_id: int, nama_desa: str, kecamatan: str, kabupaten: str, tanggal: str, operator: str, keterangan: str):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE batches
            SET nama_desa = ?, kecamatan = ?, kabupaten = ?, tanggal = ?, operator = ?, keterangan = ?
            WHERE id = ?
        """, (nama_desa, kecamatan, kabupaten, tanggal, operator, keterangan, batch_id))
        conn.commit()
        add_log(conn, aktivitas="Perbarui Batch", detail=f"Memperbarui data batch ID {batch_id} ({nama_desa})", batch_id=batch_id)

def delete_batch(batch_id: int):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM batches WHERE id = ?", (batch_id,))
        conn.commit()
        add_log(conn, aktivitas="Hapus Batch", detail=f"Menghapus batch ID {batch_id} beserta dokumen di dalamnya")

# ==================== DOCUMENT OPERATIONS ====================

def create_document(
    batch_id: int,
    nama_pdf: str,
    path_pdf: str,
    halaman_pdf: int = 1,
    path_crop: str = "",
    jenis_hak: str = "",
    kode_hak: str = "",
    nomor_hak: str = "",
    nomor_gs: str = "",
    tahun: str = "",
    identitas_dokumen: str = "",
    luas_dokumen: Optional[float] = None,
    status: str = STATUS_MENUNGGU,
) -> int:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO documents (
                batch_id, nama_pdf, path_pdf, halaman_pdf, path_crop,
                jenis_hak, kode_hak, nomor_hak, nomor_gs, tahun,
                identitas_dokumen, luas_dokumen, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            batch_id, nama_pdf, path_pdf, halaman_pdf, path_crop,
            jenis_hak, kode_hak, nomor_hak, nomor_gs, tahun,
            identitas_dokumen, luas_dokumen, status
        ))
        doc_id = cursor.lastrowid
        conn.commit()
        add_log(conn, aktivitas="Import Dokumen", detail=f"Menambahkan dokumen {nama_pdf} ke batch ID {batch_id}", batch_id=batch_id, document_id=doc_id)
        return doc_id

def get_document(doc_id: int) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM documents WHERE id = ?", (doc_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

def get_documents_by_batch(batch_id: int, status_filter: Optional[str] = None, search_query: Optional[str] = None) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        query = "SELECT * FROM documents WHERE batch_id = ?"
        params: List[Any] = [batch_id]
        
        if status_filter and status_filter != "SEMUA":
            query += " AND status = ?"
            params.append(status_filter)
            
        if search_query:
            query += " AND (identitas_dokumen LIKE ? OR nama_pdf LIKE ? OR nomor_hak LIKE ? OR nomor_gs LIKE ?)"
            wildcard = f"%{search_query}%"
            params.extend([wildcard, wildcard, wildcard, wildcard])
            
        query += " ORDER BY id ASC"
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

def get_all_documents(search_query: Optional[str] = None) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        if search_query:
            wildcard = f"%{search_query}%"
            cursor.execute("""
                SELECT d.*, b.nama_desa, b.kecamatan 
                FROM documents d
                JOIN batches b ON d.batch_id = b.id
                WHERE d.identitas_dokumen LIKE ? OR d.nama_pdf LIKE ?
                ORDER BY d.id DESC
            """, (wildcard, wildcard))
        else:
            cursor.execute("""
                SELECT d.*, b.nama_desa, b.kecamatan 
                FROM documents d
                JOIN batches b ON d.batch_id = b.id
                ORDER BY d.id DESC
            """)
        return [dict(row) for row in cursor.fetchall()]

def update_document(doc_id: int, **kwargs):
    if not kwargs:
        return
    fields = []
    values = []
    for k, v in kwargs.items():
        fields.append(f"{k} = ?")
        values.append(v)
    fields.append("updated_at = datetime('now', 'localtime')")
    values.append(doc_id)
    
    query = f"UPDATE documents SET {', '.join(fields)} WHERE id = ?"
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, values)
        conn.commit()

def delete_document(doc_id: int):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT identitas_dokumen, nama_pdf, batch_id FROM documents WHERE id = ?", (doc_id,))
        doc = cursor.fetchone()
        cursor.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
        conn.commit()
        if doc:
            add_log(conn, aktivitas="Hapus Dokumen", detail=f"Menghapus dokumen ID {doc_id} ({doc['identitas_dokumen'] or doc['nama_pdf']})", batch_id=doc['batch_id'])

# ==================== STATS OPERATIONS ====================

def get_overall_stats() -> Dict[str, Any]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM batches")
        total_batches = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM documents")
        total_docs = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM documents WHERE status = ?", (STATUS_MENUNGGU,))
        menunggu = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM documents WHERE status IN (?, ?, ?, ?)", 
                       (STATUS_PDF_DIPROSES, STATUS_MENUNGGU_TRACING, STATUS_MENUNGGU_SCALING, STATUS_MENUNGGU_VERIFIKASI))
        proses = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM documents WHERE status = ?", (STATUS_SELESAI,))
        selesai = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM documents WHERE status = ?", (STATUS_GAGAL,))
        gagal = cursor.fetchone()[0]
        
        persen_selesai = round((selesai / total_docs * 100), 1) if total_docs > 0 else 0.0
        
        return {
            "total_batches": total_batches,
            "total_documents": total_docs,
            "menunggu": menunggu,
            "proses": proses,
            "selesai": selesai,
            "gagal": gagal,
            "persen_selesai": persen_selesai,
        }

def get_batch_stats(batch_id: int) -> Dict[str, Any]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM documents WHERE batch_id = ?", (batch_id,))
        total = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM documents WHERE batch_id = ? AND status = ?", (batch_id, STATUS_SELESAI))
        selesai = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM documents WHERE batch_id = ? AND status = ?", (batch_id, STATUS_GAGAL))
        gagal = cursor.fetchone()[0]
        
        sisa = total - selesai
        persen = round((selesai / total * 100), 1) if total > 0 else 0.0
        
        return {
            "total": total,
            "selesai": selesai,
            "gagal": gagal,
            "sisa": sisa,
            "persen": persen,
            "is_all_completed": (total > 0 and sisa == 0),
        }

# ==================== ACTIVITY LOGS ====================

def add_log(conn: Optional[sqlite3.Connection] = None, aktivitas: str = "", detail: str = "", batch_id: Optional[int] = None, document_id: Optional[int] = None):
    if conn is not None:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO activity_logs (batch_id, document_id, aktivitas, detail)
            VALUES (?, ?, ?, ?)
        """, (batch_id, document_id, aktivitas, detail))
        conn.commit()
    else:
        with get_connection() as new_conn:
            cursor = new_conn.cursor()
            cursor.execute("""
                INSERT INTO activity_logs (batch_id, document_id, aktivitas, detail)
                VALUES (?, ?, ?, ?)
            """, (batch_id, document_id, aktivitas, detail))
            new_conn.commit()

def get_recent_logs(limit: int = 50) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT l.*, b.nama_desa 
            FROM activity_logs l
            LEFT JOIN batches b ON l.batch_id = b.id
            ORDER BY l.id DESC
            LIMIT ?
        """, (limit,))
        return [dict(row) for row in cursor.fetchall()]

# ==================== SETTINGS OPERATIONS ====================

def get_setting(key: str, default: str = "") -> str:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM app_settings WHERE key = ?", (key,))
        row = cursor.fetchone()
        return row[0] if row else default

def set_setting(key: str, value: str):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES (?, ?)", (key, value))
        conn.commit()
