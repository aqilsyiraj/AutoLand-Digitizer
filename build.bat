@echo off
chcp 65001 >nul
echo =======================================================
echo   AutoLand Digitizer - Build Executable (PyInstaller)
echo =======================================================
echo.

:: Periksa instalasi Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python tidak terdeteksi pada sistem ini.
    echo Harap install Python 3.10, 3.11, atau 3.12 terlebih dahulu.
    pause
    exit /b 1
)

echo [1/3] Memeriksa dependensi...
pip install -r requirements.txt

echo.
echo [2/3] Menjalankan PyInstaller...
pyinstaller --noconfirm --onedir --windowed ^
    --name "AutoLandDigitizer" ^
    --add-data "template;template" ^
    --add-data "ui;ui" ^
    --hidden-import "win32com.client" ^
    --hidden-import "pythoncom" ^
    --hidden-import "openpyxl" ^
    --hidden-import "pymupdf" ^
    --hidden-import "PIL" ^
    --hidden-import "numpy" ^
    --hidden-import "cv2" ^
    main.py

echo.
echo [3/3] Menyiapkan folder distribusi...
if exist "dist\AutoLandDigitizer" (
    mkdir "dist\AutoLandDigitizer\data" 2>nul
    mkdir "dist\AutoLandDigitizer\dokumen_masuk" 2>nul
    mkdir "dist\AutoLandDigitizer\temporary" 2>nul
    mkdir "dist\AutoLandDigitizer\hasil_digitasi" 2>nul
    mkdir "dist\AutoLandDigitizer\backup" 2>nul
    mkdir "dist\AutoLandDigitizer\logs" 2>nul
    echo [SUKSES] Executable berhasil dibuat di: dist\AutoLandDigitizer\AutoLandDigitizer.exe
) else (
    echo [ERROR] Kompilasi gagal. Periksa log kesalahan di atas.
)

echo.
pause
