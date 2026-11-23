@echo off
chcp 65001 >nul
echo =======================================================
echo   AutoLand Digitizer - Instalasi Dependensi Lokal
echo =======================================================
echo.

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python belum terpasang di sistem ini.
    echo Silakan unduh dan pasang Python 64-bit dari https://www.python.org/
    echo Pastikan opsi "Add Python to PATH" dicentang saat instalasi.
    pause
    exit /b 1
)

echo Menginstal seluruh library yang dibutuhkan...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo.
echo =======================================================
echo   Instalasi Selesai!
echo   Jalankan aplikasi dengan mengklik ganda: run.bat
echo =======================================================
pause
