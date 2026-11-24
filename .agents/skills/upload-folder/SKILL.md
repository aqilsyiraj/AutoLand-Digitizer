---
name: upload-folder
description: Impor folder dokumen PDF ke AutoLand Digitizer secara rekursif. Use when user menyuruh mengupload atau mengimpor folder yang berisi PDF dengan isi subfolder di dalamnya; fitur ini bukan upload file tunggal, melainkan upload folder beserta seluruh isinya.
---

# Upload Folder PDF ke AutoLand Digitizer

Fitur ini mengimpor **semua file PDF di dalam folder yang dipilih, termasuk folder di dalamnya (rekursif)**, ke dalam Antrean dokumen aplikasi AutoLand Digitizer. Ini digunakan misalnya saat operator punya satu folder dokumen pertanahan yang isinya berisi subfolder PDF.

## Status implementasi

Fitur ini **sudah diimplementasikan** di aplikasi AutoLand Digitizer:

- Tombol `Import Folder` berdampingan dengan `Import PDF` di header Queue Page (`app/queue_page.py`, `_setup_ui` → `btn_import_folder`).
- Method `_import_folder_dialog` di `app/queue_page.py`.

Gunakan snippet di bawah hanya jika hendak menambah fitur serupa di kode lain, atau supaya Anda memahami isinya.

## Cara pakai (referensi / kode lain — saat ini diimplementasikan di app/queue_page.py)

```python
import os
import shutil
from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QMessageBox

from database.db import create_document, get_documents_by_batch
from config import DOKUMEN_MASUK_DIR


def _import_folder_dialog(self):
    if not self.active_batch_id:
        QMessageBox.warning(self, "Belum Ada Batch", "Pilih batch aktif terlebih dahulu.")
        return

    folder = QFileDialog.getExistingDirectory(self, "Pilih Folder Dokumen", "")
    if not folder:
        return

    root = Path(folder)
    pdf_paths = sorted(root.rglob("*.pdf"), key=lambda p: str(p))
    if not pdf_paths:
        QMessageBox.information(
            self, "Tidak Ada PDF", f"Tidak ditemukan file PDF (termasuk subfolder) di:\n{root}"
        )
        return

    preview = "\n".join(str(p.relative_to(root)) for p in pdf_paths[:50])
    if len(pdf_paths) > 50:
        preview += f"\n… dan {len(pdf_paths) - 50} lagi"
    QMessageBox.information(
        self, "Preview Impor Folder",
        f"{len(pdf_paths)} PDF ditemukan di folder ini:\n{preview}",
    )

    known = {
        os.path.basename(d.get("nama_pdf", "")).lower()
        for d in get_documents_by_batch(self.active_batch_id)
    }
    added = skipped = 0
    for path in pdf_paths:
        name = path.name
        if name.lower() in known:
            skipped += 1
            continue
        known.add(name.lower())
        dest_dir = DOKUMEN_MASUK_DIR / f"Batch_{self.active_batch_id}"
        dest_dir.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(str(path), str(dest_dir / name))
            used_path = str(dest_dir / name)
        except Exception:
            used_path = str(path)
        create_document(
            batch_id=self.active_batch_id,
            nama_pdf=name,
            path_pdf=used_path,
            status="MENUNGGU",
        )
        added += 1

    self.load_data()  # refresh tabel antrean
    QMessageBox.information(
        self, "Impor Folder Selesai",
        f"PDF diimpor: {added}\n"
        f"Dilewati karena nama PDF sudah ada di batch ini: {skipped}",
    )
```

### Subsistem dari skill-creator

- **Nama folder:** `upload-folder` (kebab-case) — bukan di `.claude/skills` di sini karena agent active ini adalah OpenCode; skill terinstall ke `.agents/skills/` yang alamatnya dicari oleh OpenCode.
- **Pemicu kapan skill ini dipakai:** operator menyuruh "upload folder", "impor folder", atau "tambahkan semua PDF dari folder X ke antrean", termasuk kalimat "folder di dalam folder".
- **Tools yang dipakai:** `PySide6.QtWidgets.QFileDialog` (`getExistingDirectory`, `getOpenFileNames`), `pathlib.Path.rglob`, `shutil.copy2`, `database.db.create_document`, `app.queue_page.QueuePage.load_data`, `os.path.basename`/`os.path`.
- **Fitur lain opsional yang bisa tambahkan:** pengelompokkan per subfolder (jalur relatif direkam ke `nama_pdf` sebagai `sub/nama.pdf`), filter ekstensi case-insensitif (`*.pdf` / `*.PDF`), batas maksimum jumlah file per import.

### Kontrak kepemilikan (versi 1)

- Status dokumen baru selalu **MENUNGGU** — fitur ini hanya impor, proses digitasi tetap lewat menu "Proses" pada Queue (konsisten dengan `_import_pdf_dialog`).
- Nama dokumen unik per batch: duplikat berbasis nama file di-skip.
- Sumber PDF tetap tetap (ada di lokasi aslinya juga) — impor menggunakan *copy*, tidak *move*.
