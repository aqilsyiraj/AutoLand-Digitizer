@echo off
chcp 65001 >nul
echo =======================================================
echo   AutoLand Digitizer - Build Executable (Optimized)
echo =======================================================
echo.

:: Periksa instalasi Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python tidak terdeteksi pada sistem ini.
    pause
    exit /b 1
)

echo [1/4] Memeriksa dependensi lokal...
python -m pip install -r requirements.txt >nul 2>&1

echo.
echo [2/4] Mengompilasi aplikasi dengan PyInstaller (Optimized Spec)...
pyinstaller --noconfirm --clean AutoLandDigitizer.spec
if %errorlevel% neq 0 (
    echo [ERROR] Kompilasi gagal. Periksa log kesalahan di atas.
    pause
    exit /b 1
)

echo.
echo [3/4] Menyiapkan direktori penyimpanan lokal aplikasi...
if exist "dist\AutoLandDigitizer" (
    mkdir "dist\AutoLandDigitizer\data" 2>nul
    mkdir "dist\AutoLandDigitizer\dokumen_masuk" 2>nul
    mkdir "dist\AutoLandDigitizer\temporary" 2>nul
    mkdir "dist\AutoLandDigitizer\hasil_digitasi" 2>nul
    mkdir "dist\AutoLandDigitizer\backup" 2>nul
    mkdir "dist\AutoLandDigitizer\logs" 2>nul

    :: Hitung ukuran folder hasil kompilasi
    powershell -NoProfile -Command "$size = (Get-ChildItem -Path 'dist\AutoLandDigitizer' -Recurse | Measure-Object -Property Length -Sum).Sum / 1MB; Write-Host ('[INFO] Ukuran folder hasil build: {0:N1} MB' -f $size) -ForegroundColor Green"
)

echo.
echo [4/4] Membuat paket Portable (.zip)...
powershell -NoProfile -Command "Compress-Archive -Path 'dist\AutoLandDigitizer' -DestinationPath 'dist\AutoLandDigitizer_Portable.zip' -Force"
if exist "dist\AutoLandDigitizer_Portable.zip" (
    echo [SUKSES] Paket ZIP portable siap dibagikan: dist\AutoLandDigitizer_Portable.zip
)

:: Periksa apakah Inno Setup tersedia untuk membuat installer wizard (.exe)
where iscc >nul 2>&1
if %errorlevel% equ 0 (
    echo.
    echo Mengompilasi Installer Setup Wizard (.exe) via Inno Setup...
    iscc installer.iss
    echo [SUKSES] Setup installer telah dibuat di folder installer_output/
) else (
    echo.
    echo [INFO] Inno Setup (iscc) tidak terdeteksi di PATH sistem.
    echo Untuk membuat file setup wizard (.exe) satu klik:
    echo 1. Unduh Inno Setup gratis di: https://jrsoftware.org/isdl.php
    echo 2. Buka file 'installer.iss' lalu klik menu Build -> Compile.
)

echo.
echo =======================================================
echo   PROSES BUILD SELESAI DENGAN SUKSES!
echo   Folder Aplikasi: dist\AutoLandDigitizer\
echo   Executable     : dist\AutoLandDigitizer\AutoLandDigitizer.exe
echo   Paket Portable : dist\AutoLandDigitizer_Portable.zip
echo =======================================================
pause
