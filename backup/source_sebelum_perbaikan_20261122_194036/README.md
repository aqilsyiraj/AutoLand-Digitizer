# AutoLand Digitizer
**Aplikasi Desktop Windows untuk Otomatisasi & Pengelolaan Digitalisasi Dokumen Pertanahan**

---

## 📌 1. Pendahuluan
**AutoLand Digitizer** adalah aplikasi desktop native Windows 10/11 64-bit yang dirancang khusus untuk mempercepat, menstandarkan, dan mengotomatisasi pekerjaan digitalisasi dokumen pertanahan (Buku Tanah / Surat Ukur / Gambar Situasi) melalui integrasi langsung dengan **AutoCAD Desktop**.

Aplikasi ini beroperasi **100% lokal dan offline**, tanpa memerlukan koneksi internet, server cloud, atau API pihak ketiga. Seluruh database, file PDF sumber, denah hasil pemotongan (*crop*), dan file gambar DWG tersimpan secara aman di komputer lokal pengguna.

---

## 🚀 2. Fitur Utama

- **100% Lokal & Offline:** Keamanan data dokumen pertanahan terjamin tanpa koneksi internet.
- **Batch Berbasis Wilayah:** Pengelompokan dokumen berdasarkan Desa/Kelurahan, Kecamatan, dan Kabupaten.
- **Import & Preview PDF:** Mendukung dokumen PDF multi-halaman dengan penampil cepat (*PyMuPDF*).
- **Interactive Mouse Crop:** Pemotongan denah bidang tanah secara visual menggunakan mouse drag dengan resolusi tinggi (300 DPI).
- **Standarisasi Penomoran Resmi:** Pembuatan identitas dokumen otomatis sesuai standar:
  $$\text{Format: } [\text{Awalan Hak}]\ [\text{Nomor Hak}]\ [\text{Nomor GS}]/[\text{Tahun}]$$
  *Contoh:* `M. 1342 GS1152/1998`
- **Integrasi AutoCAD via Windows COM (pywin32):**
  - Deteksi dan pembukaan otomatis template DWG.
  - Penyisipan denah hasil crop (*raster image*) ke ModelSpace.
  - Pembacaan luas polyline tertutup (*Closed AcDbPolyline*).
  - Perhitungan faktor scaling otomatis.
  - Eksekusi scaling seragam (*uniform scale*) pada objek terpilih.
  - Penggantian identitas objek `TEXT` atau `MTEXT`.
  - Penyimpanan file DWG dengan nama dokumen yang aman.
- **Mode Simulasi AutoCAD:** Memungkinkan pengujian seluruh alur kerja pada komputer yang belum terpasang AutoCAD.
- **Ekspor Rekapitulasi Lengkap:**
  - Laporan Excel resmi (`.xlsx`) berformat rapi (*openpyxl*).
  - Data tabel CSV (`.csv`).
  - Paket arsip ZIP berisi seluruh file DWG hasil digitasi beserta lembar rekapitulasi.
- **Pertukaran Paket Offline (Flashdisk):** Fitur ekspor dan impor paket batch antar komputer tanpa jaringan.
- **Cadangan Database (Backup & Restore):** Pencadangan database SQLite lokal secara aman.

---

## 📐 3. Standar Penomoran Dokumen

Format penomoran dokumen disusun secara konsisten pada antarmuka aplikasi, isi teks gambar AutoCAD, nama file DWG, dan rekapitulasi Excel.

### Pemetaan Jenis Hak:
| Kode | Jenis Hak | Awalan | Contoh Identitas Dokumen |
|:---:|:---|:---:|:---|
| **1** | Hak Milik | `M.` | `M. 1342 GS1152/1998` |
| **3** | Hak Guna Bangunan | `B.` | `B. 550 GS204/2005` |
| **4** | Hak Pakai | `P.` | `P. 77 GS301/2010` |
| **8** | Wakaf | `W.` | `W. 12 GS99/2020` |

> **Catatan Sanitasi Nama File:**
> Pada sistem operasi Windows, karakter garis miring (`/`) dan spasi diubah menjadi karakter aman garis bawah (`_`).
> Identitas `M. 1342 GS1152/1998` akan disimpan sebagai file DWG bernama `M_1342_GS1152_1998.dwg`.

---

## 🧮 4. Rumus Perhitungan Scaling Otomatis

Aplikasi menghitung faktor pengali skala seragam (*uniform scale factor*) menggunakan rumus matematika:

$$\text{Faktor Scaling} = \sqrt{\frac{\text{Luas Dokumen}}{\text{Luas Polyline AutoCAD}}}$$

**Keterangan:**
- $\text{Luas Dokumen}$: Nilai luas yang tertera pada dokumen pertanahan ($m^2$).
- $\text{Luas Polyline AutoCAD}$: Nilai luas bidang hasil *tracing* operator di ModelSpace AutoCAD ($m^2$).
- Satuan gambar AutoCAD yang digunakan adalah **meter (m)** dan luas dalam **meter persegi ($m^2$)**.

**Contoh Perhitungan:**
- Luas dokumen: $150\text{ m}^2$
- Luas hasil tracing polyline: $100\text{ m}^2$
- Faktor scaling: $\sqrt{\frac{150}{100}} = \sqrt{1.5} \approx 1.224745$

Setelah proses scaling diterapkan di AutoCAD, aplikasi membaca kembali luas polyline tersebut untuk memverifikasi tingkat akurasi dan menampilkan selisihnya terhadap luas target dokumen.

---

## 📂 5. Struktur Folder Aplikasi

```
AutoLand_Digitizer/
├── main.py                     # Entry point aplikasi desktop PySide6
├── config.py                   # Konfigurasi direktori, konstanta, dan status
├── requirements.txt            # Daftar library Python
├── build.bat                   # Script pembuatan executable (.exe) PyInstaller
├── install.bat                 # Script instalasi dependensi otomatis
├── run.bat                     # Script peluncur aplikasi cepat
├── installer.iss               # Script Inno Setup untuk Windows Installer
│
├── app/                        # Modul Antarmuka Pengguna (PySide6)
│   ├── main_window.py          # Jendela utama dengan sidebar navigasi
│   ├── dashboard.py            # Halaman ringkasan metrik dan aktivitas
│   ├── batch_page.py           # Halaman pembuatan & seleksi batch desa
│   ├── queue_page.py           # Halaman antrean dokumen dan filter status
│   ├── digitization_page.py    # Wizard alur kerja digitasi & AutoCAD
│   ├── result_page.py          # Halaman daftar file DWG selesai
│   ├── report_page.py          # Halaman rekapitulasi & ekspor Excel/ZIP
│   └── settings_page.py        # Pengaturan template, COM, dan backup DB
│
├── services/                   # Logika Bisnis & Integrasi Sistem
│   ├── naming_service.py       # Standarisasi penomoran & sanitasi nama file
│   ├── geometry_service.py     # Rumus scaling & verifikasi toleransi luas
│   ├── pdf_service.py          # Ekstraksi halaman & cropping resolusi tinggi (300 DPI)
│   ├── image_service.py        # Rotasi & peningkatan kontras gambar
│   ├── autocad_service.py      # Komunikasi Windows COM Automation AutoCAD
│   ├── export_service.py       # Ekspor Excel (.xlsx), CSV, dan ZIP
│   └── backup_service.py       # Cadangan SQLite & paket offline flashdisk
│
├── database/                   # Manajemen Database SQLite Lokal
│   ├── db.py                   # Koneksi context manager & operasi CRUD
│   └── models.py               # Definisi skema dan struktur tabel
│
├── ui/                         # Aset Desain & Komponen Antarmuka
│   ├── styles/style.py         # Tema desktop modern (QSS Design System)
│   └── components/
│       ├── crop_canvas.py      # Kanvas interaktif mouse drag crop PDF
│       ├── stat_card.py        # Kartu indikator metrik dashboard
│       └── status_badge.py     # Badge pill status berwarna
│
├── template/
│   └── template.dwg            # Template gambar dasar AutoCAD
│
├── data/                       # Database SQLite lokal (autoland.db)
├── dokumen_masuk/              # Salinan dokumen PDF yang diimpor
├── temporary/                  # Gambar raster denah hasil crop
├── hasil_digitasi/             # File DWG hasil digitasi per batch desa
├── backup/                     # File cadangan database (.db)
└── logs/                       # Log aktivitas dan penanganan kesalahan
```

---

## 💻 6. Panduan Instalasi & Menjalankan Aplikasi

### Persyaratan Sistem:
- Windows 10 / Windows 11 (64-bit).
- Python 3.10, 3.11, 3.12, atau yang lebih baru.
- AutoCAD Desktop (AutoCAD 2018 s/d 2026 atau versi yang mendukung Windows COM API).
  *(Jika AutoCAD belum terpasang, pengguna dapat mengaktifkan "Mode Simulasi" di menu Pengaturan).*

### Cara Menjalankan dari Source Code:
1. Buka folder proyek di Command Prompt atau PowerShell.
2. Jalankan script instalasi otomatis:
   ```cmd
   install.bat
   ```
   *atau install secara manual:*
   ```cmd
   pip install -r requirements.txt
   ```
3. Jalankan aplikasi:
   ```cmd
   run.bat
   ```
   *atau:*
   ```cmd
   python main.py
   ```

---

## 🛠️ 7. Panduan Langkah Operasional Digitalisasi

1. **Buat / Pilih Batch Wilayah:**
   - Masuk ke menu **Batch Pekerjaan**.
   - Masukkan Nama Desa, Kecamatan, Kabupaten, Tanggal, dan Operator.
   - Klik **Simpan Batch** dan pilih sebagai **Batch Aktif**.

2. **Import Dokumen PDF:**
   - Masuk ke menu **Antrean Dokumen**.
   - Klik **+ Import File PDF...** dan pilih satu atau beberapa file PDF denah.
   - Dokumen otomatis terdaftar dengan status `MENUNGGU`.

3. **Mulai Proses Digitasi:**
   - Klik tombol **Digitasi** pada salah satu baris dokumen.
   - Halaman beralih ke menu **Proses Digitasi**:
     - **Langkah 1 (Denah & Crop PDF):** Pilih nomor halaman denah. Gunakan mouse untuk melakukan drag memilih area denah tanah. Klik **Konfirmasi Potongan**.
     - **Langkah 2 (Identitas & Luas):** Pilih Jenis Hak (Hak Milik, HGB, Hak Pakai, Wakaf), isi Nomor Hak, Nomor GS, Tahun, dan Luas Dokumen ($m^2$). Klik **Simpan Informasi Dokumen**.
     - **Langkah 3 (AutoCAD Tracing & Scaling):**
       - Klik **Buka Template DWG di AutoCAD**.
       - Klik **Sisipkan Gambar Denah (Raster)** untuk memasukkan denah ke ModelSpace.
       - Operator melakukan penjiplakan batas bidang di AutoCAD menggunakan perintah `PL` dan pastikan polyline ditutup (*Close*).
       - Klik **Ambil Luas Polyline AutoCAD** untuk membaca nilai luas hasil tracing.
       - Aplikasi otomatis menghitung faktor scaling: $\sqrt{\text{Luas Dokumen} / \text{Luas Tracing}}$.
       - Klik **Terapkan Scaling di AutoCAD**. Operator memilih objek gambar dan titik dasar (*base point*). Luas akhir polyline akan otomatis diverifikasi.
     - **Langkah 4 (Ganti Teks & Simpan DWG):**
       - Klik **Ganti Teks Identitas di AutoCAD**. Klik objek `TEXT` atau `MTEXT` di AutoCAD untuk mengubah teks menjadi identitas resmi (misal: `M. 1342 GS1152/1998`).
       - Klik **Simpan Hasil Digitasi (DWG)**. File DWG akan tersimpan rapi di folder `hasil_digitasi/Batch_[ID]_[NamaDesa]/` dan status dokumen berubah menjadi `SELESAI`.

4. **Ekspor Rekapitulasi Akhir:**
   - Setelah seluruh dokumen dalam satu desa selesai, masuk ke menu **Rekapitulasi**.
   - Sistem memeriksa kesiapan batch.
   - Klik **Ekspor Excel (.xlsx)** untuk menghasilkan lembar rekapitulasi tabel resmi, atau **Buat Paket ZIP** untuk mengemas seluruh file DWG beserta rekapitulasi.

---

## 📦 8. Distribusi ke Komputer Lain (Tanpa Python)

Aplikasi dapat dikompilasi menjadi satu paket executable mandiri yang dapat langsung dijalankan oleh rekan kerja tanpa harus memasang Python:

1. **Kompilasi Menggunakan PyInstaller:**
   Jalankan file script pembangun:
   ```cmd
   build.bat
   ```
   Hasil file `.exe` dan pustaka pendukung akan terbentuk di dalam folder:
   `dist\AutoLandDigitizer\`

2. **Membuat Installer Setup (.exe):**
   - Pasang software gratis **Inno Setup** (https://jrsoftware.org/isdl.php).
   - Klik kanan pada file `installer.iss` dan pilih **Compile**.
   - File installer setup mandiri akan dibuat di folder `installer_output/`.
   - Salin file installer tersebut ke flashdisk dan pasang di komputer lain dengan satu kali klik.

---

## 🧪 9. Pengujian & Status Verifikasi Sistem

Aplikasi telah dilengkapi dengan pengujian unit otomatis (*automated unit tests*):
```cmd
python -m unittest tests/test_services.py
python -m unittest tests/test_pdf.py
python -m unittest tests/test_ui.py
```

### Hasil Verifikasi:
| Komponen | Status Pengujian | Keterangan |
|---|:---:|---|
| **Standarisasi Penomoran (`naming_service`)** | **Lolos (Passed)** | Format `M. 1342 GS1152/1998`, normalisasi GS, sanitasi file Windows |
| **Perhitungan Scaling Geometri (`geometry_service`)** | **Lolos (Passed)** | Rumus $\sqrt{\text{Luas Dokumen}/\text{Luas Tracing}}$, toleransi luas akhir |
| **Operasi Database SQLite (`db.py`)** | **Lolos (Passed)** | CRUD Batch, Dokumen, Log aktivitas, statistik, transaksi aman |
| **Pengolahan & Pemotongan PDF (`pdf_service`)** | **Lolos (Passed)** | Ekstraksi halaman, render pixmap, crop 300 DPI, rotasi gambar |
| **Ekspor Excel & CSV (`export_service`)** | **Lolos (Passed)** | File `.xlsx` terformat rapi dengan openpyxl, file `.csv`, arsip `.zip` |
| **Cadangan & Pemulihan (`backup_service`)** | **Lolos (Passed)** | Backup database `.db`, restore konsisten, ekspor/impor paket flashdisk |
| **Antarmuka Pengguna Desktop (`PySide6`)** | **Lolos (Passed)** | Navigasi sidebar, 7 halaman utama, kanvas interaktif crop |
| **AutoCAD COM Automation (`autocad_service`)** | **Mode Simulasi Lolos** | Mode simulasi teruji 100%. Komunikasi COM fisik membutuhkan AutoCAD terpasang pada komputer target. |

---

## 🔒 10. Keamanan & Kepatuhan Data Lokal

- **Tidak Ada Koneksi Internet:** Tidak ada modul `requests`, socket online, atau telemetri jarak jauh.
- **Integritas Berkas:** File PDF sumber tidak pernah dimodifikasi atau dihapus secara otomatis.
- **Konfirmasi Penimpaan File:** Aplikasi mencegah penimpaan file DWG yang sudah ada tanpa izin eksplisit dari operator.
- **Pencatatan Aktivitas:** Setiap operasi penting tercatat di tabel `activity_logs` dan file `logs/autoland_activity.log`.
