# AutoLand Digitizer

Aplikasi desktop Windows untuk digitalisasi dokumen pertanahan menjadi **DWG AutoCAD + rekap Excel + berkas koordinat**.

Aplikasi berjalan **100% lokal/offline**. Deteksi batas bidang menggunakan OpenCV (computer vision) di komputer sendiri, tanpa internet, cloud, atau API berbayar.

---

## Alur Singkat (4 Langkah)

1. **Buat / pilih batch desa**  
   Menu `2. Batch / Desa` → isi nama desa, kecamatan, kabupaten → **Simpan Batch** → **Pilih** pada baris batch tersebut.

2. **Import PDF**  
   Menu `3. PDF & Antrean` → **+ Import PDF** → pilih satu atau beberapa PDF scan.

3. **Proses + koreksi polyline**  
   Klik tombol biru **Proses** pada baris dokumen:
   - **Langkah 1 — Pilih Halaman Denah:** aplikasi otomatis memilih halaman Gambar Situasi dan menggambar polyline hijau. Anda bisa mengganti halaman, memilih kandidat, lalu **geser titik hijau** untuk koreksi. Klik 2x pada garis untuk menambah titik; klik kanan titik untuk menghapus.
   - **Langkah 2 — Periksa & Isi Data:** isi Jenis Hak, Nomor Hak, Nomor GS, Tahun, dan Luas Dokumen (m²). Nilai GS/Tahun/Luas sudah dicoba diisi otomatis dari nama file/teks PDF, tetapi **tetap periksa sendiri**.
   - **Langkah 3 — Proses Otomatis:** tekan satu tombol. Aplikasi memotong denah 300 DPI, menyimpannya di folder `Gambar_Denah`, **memasukkan gambar denah ke DWG**, membuat polyline di atasnya, menghitung dan menerapkan skala, lalu **menulis blok data dokumen di atas denah**.
   - **Langkah 4 — Selesai:** ringkasan hasil dan tombol buka folder.

   Isi akhir DWG di AutoCAD:
   - gambar denah hasil potongan PDF,
   - polyline batas yang sudah diskalakan sesuai luas dokumen,
   - blok teks data dokumen: identitas, jenis hak, nomor hak, nomor GS, tahun, luas dokumen, luas akhir DWG, lokasi desa/kecamatan/kabupaten, nomor batch, tanggal, dan operator.

4. **Ekspor rekap**  
   Menu `6. Laporan & Ekspor` → pilih batch → **Ekspor Excel** / **Ekspor CSV** atau **Paket ZIP** (DWG + gambar denah + koordinat + rekap).

> Tidak perlu lagi menggambar `PL` manual di AutoCAD. Operator hanya memeriksa dan mengoreksi titik bila deteksi kurang tepat.

> Saat terhubung, aplikasi memakai satu gambar AutoCAD aktif. Gambar kosong bawaan tambahan ditutup, sehingga tidak muncul `Drawing1` + `Drawing2`.

## Kemudahan Penggunaan (UI)

Antarmuka sudah dibangun ulang dengan satu sistem desain yang sama di semua halaman:

- **Header halaman konsisten:** judul ringkas, sub judul satu kalimat, dan aksi utama di kanan atas.
- **Satu kartu = satu topik.** Formulir, tabel, ringkasan, dan pengaturan tidak lagi bercampur dalam satu panel.
- **Petunjuk bisa dibuka saat dibutuhkan.** Banner panduan ringkas di Dashboard, Batch, Antrean, Hasil, Laporan, dan Pengaturan.
- **Kolom tabel diukur ulang** untuk layar laptop 1366×768: tidak ada scroll horizontal pada tabel utama, teks tidak terpotong, dan tombol aksi tidak saling menimpa.
- **Teks tombol jelas:** **Proses**, **DWG**, **Ulang**, **Hapus**, **Ekspor Excel**, dan sebagainya — bukan ikon kecil tanpa label. Aksi baris dan kolomnya dibuat lebih padat tanpa memotong teks.
- **Setiap kolom penting punya label + keterangan singkat** dan tooltip. Nama file dan identitas yang terpotong tetap bisa dibaca lewat tooltip.
- **Status memakai pill berwarna** dan indikator 4 langkah wizard menunjukkan langkah aktif/selesai.
- **Pratinjau denah punya legenda warna:** hijau = polyline, biru = area potongan, oranye = titik yang sedang digeser.
- Warna biru/hijau dipilih untuk kontras tinggi di layar kantor; tidak ada gradien ungu atau teks dekoratif yang mengganggu pembacaan.

---

## Output

Untuk setiap dokumen yang selesai, tersedia:

- **DWG**: `hasil_digitasi/Batch_[ID]_[Desa]/[Identitas].dwg`
- **Gambar denah**: `hasil_digitasi/Batch_[ID]_[Desa]/Gambar_Denah/crop_doc_[ID]_[acak].png` — dipakai sebagai raster di dalam DWG dan ikut dikirim dalam Paket ZIP.
- **Koordinat CSV**: `hasil_digitasi/Batch_[ID]_[Desa]/koordinat/Koordinat_[Identitas].csv`
- **Koordinat JSON**: berisi metadata deteksi, skala m/piksel, dan seluruh titik polyline.
- **Rekap Excel/CSV**: dibuat dari menu `6. Laporan & Ekspor`; memuat status, metode/keyakinan deteksi, nama DWG, dan nama berkas koordinat.

Format identitas: `[Awalan Hak] [Nomor Hak] GS[Nomor]/[Tahun]`, contoh `M. 1342 GS1152/1998`.

---

## AutoCAD 2021 (Tanpa Mode Simulasi)

Aplikasi **terhubung langsung ke AutoCAD Desktop 2021** memakai Windows COM Automation.

- Jika AutoCAD belum terbuka, aplikasi akan menjalankannya otomatis.
- Aplikasi memakai **satu dokumen aktif**. Gambar kosong bawaan tambahan ditutup saat koneksi dibuat, jadi tidak muncul `Drawing1` + `Drawing2`.
- Jika AutoCAD tidak ditemukan, proses dihentikan dengan pesan yang jelas — tidak ada fallback simulasi.
- Template bawaan hanya placeholder. Jika template resmi belum dipilih di menu `7. Pengaturan`, aplikasi membuat **DWG baru otomatis** di AutoCAD.
- Mode Simulasi sudah dihapus dari pengaturan, antarmuka, dan kode; file DWG yang dihasilkan selalu berasal dari AutoCAD asli.

---

## Instalasi

### Menjalankan dari source

```cmd
pip install -r requirements.txt
python main.py
```

### Membuat executable

```cmd
build.bat
```

Hasil: `dist\AutoLandDigitizer\AutoLandDigitizer.exe`.

---

## Catatan Teknis Singkat

- Deteksi memakai PyMuPDF untuk merender halaman + OpenCV untuk threshold adaptif, contour, dan penyederhanaan poligon.
- Kandidat polyline disimpan di SQLite beserta confidence, kotak crop, dan koordinat ternormalisasi.
- Skala dihitung dari `sqrt(Luas Dokumen / Luas Polyline)` dan diverifikasi ulang terhadap toleransi luas.
- Data, PDF, dan hasil tidak pernah dikirim keluar komputer.

Struktur utama:

```text
app/                  halaman antarmuka (wizard digitasi ada di digitization_page.py)
services/             deteksi OpenCV, AutoCAD COM, PDF, ekspor, backup
database/db.py        SQLite + migrasi kolom deteksi
ui/components/        kanvas crop + koreksi titik polyline
template/             template DWG (ganti dengan template resmi kantor Anda)
data/                 database lokal
hasil_digitasi/       DWG, koordinat, dan rekap
backup/               cadangan database
```

> Template bawaan `template/template.dwg` hanya placeholder. Untuk hasil produksi, pilih template DWG resmi melalui menu `7. Pengaturan`.

---

## Pengujian

```cmd
python run_tests.py
```

Pengujian memakai database temporari sehingga tidak mengubah data produksi di `data/autoland.db`. Skrip menjalankan tiap modul test dalam proses terpisah agar Qt/OpenCV tidak saling mengganggu saat ditutup. Jika PySide6 mengalami crash setelah unittest mencetak `OK`, skrip tetap melaporkan lulus disertai catatan.
