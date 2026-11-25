@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

echo =======================================================
echo   AutoLand Digitizer - Build Executable (Optimized)
echo =======================================================
echo.

rem ------------------------------------------------------------------
rem Baca versi aplikasi dari config.py agar installer selalu sinkron.
rem Untuk merilis update: ubah APP_VERSION di config.py, lalu jalankan
rem build.bat ini. Tidak perlu mengedit installer.iss secara manual.
rem ------------------------------------------------------------------
set "APPVER="
for /f "tokens=2 delims== " %%v in ('findstr /b /c:"APP_VERSION" config.py') do set "APPVER=%%~v"
if not defined APPVER set "APPVER=1.0.0"
echo [INFO] Versi aplikasi: %APPVER%
echo.

python --version >nul 2>&1
if errorlevel 1 goto :no_python

echo [1/5] Memeriksa dependensi lokal...
python -m pip install -r requirements.txt >nul 2>&1

echo.
echo [2/5] Mengompilasi aplikasi dengan PyInstaller (Optimized Spec)...
pyinstaller --noconfirm --clean AutoLandDigitizer.spec
if errorlevel 1 goto :build_failed

echo.
echo [3/5] Menyiapkan direktori penyimpanan lokal aplikasi...
if not exist "dist\AutoLandDigitizer" goto :skip_prepare

rem Bersihkan sisa data runtime agar tidak ikut terbawa ke paket.
rem Data pengguna tetap aman di folder instalasi, bukan di folder build.
for %%d in (data dokumen_masuk temporary hasil_digitasi backup logs) do (
    if exist "dist\AutoLandDigitizer\%%d" rmdir /s /q "dist\AutoLandDigitizer\%%d"
    mkdir "dist\AutoLandDigitizer\%%d" 2>nul
)

rem Template DWG harus berada di samping .exe, bukan hanya di _internal,
rem karena config.py saat frozen membaca BASE_DIR\template\template.dwg.
if exist "template" xcopy "template" "dist\AutoLandDigitizer\template" /E /I /Y >nul

rem Panduan singkat untuk pengguna akhir.
if exist "docs\PANDUAN_INSTALASI.txt" copy /y "docs\PANDUAN_INSTALASI.txt" "dist\AutoLandDigitizer\PANDUAN_INSTALASI.txt" >nul

powershell -NoProfile -Command "$size = (Get-ChildItem -Path 'dist\AutoLandDigitizer' -Recurse | Measure-Object -Property Length -Sum).Sum / 1MB; Write-Host ('[INFO] Ukuran folder hasil build: {0:N1} MB' -f $size) -ForegroundColor Green"

:skip_prepare
echo.
echo [4/5] Membuat paket Portable (.zip)...
if exist "dist\AutoLandDigitizer_Portable.zip" del /q "dist\AutoLandDigitizer_Portable.zip"
powershell -NoProfile -Command "Compress-Archive -Path 'dist\AutoLandDigitizer' -DestinationPath 'dist\AutoLandDigitizer_Portable.zip' -Force"
if exist "dist\AutoLandDigitizer_Portable.zip" echo [SUKSES] Paket ZIP portable siap dibagikan: dist\AutoLandDigitizer_Portable.zip

echo.
echo [5/5] Membuat Installer Setup Wizard (.exe)...
rem Cari ISCC.exe di PATH atau di folder instalasi Inno Setup versi 6/7.
set "ISCC="
powershell -NoProfile -Command "$c=Get-Command iscc -ErrorAction SilentlyContinue; if($c){$p=$c.Source}else{$p=Get-ChildItem 'C:\Program Files\Inno Setup*','C:\Program Files (x86)\Inno Setup*','%LOCALAPPDATA%\Programs\Inno Setup*' -Filter ISCC.exe -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty FullName}; if($p){Set-Content -LiteralPath '%TEMP%\autoland_iscc.txt' -Value $p -Encoding ASCII}" 2>nul
if exist "%TEMP%\autoland_iscc.txt" set /p ISCC=<"%TEMP%\autoland_iscc.txt"
del "%TEMP%\autoland_iscc.txt" 2>nul

if not defined ISCC goto :no_iscc

echo [INFO] Inno Setup: %ISCC%
"%ISCC%" /DMyAppVersion=%APPVER% installer.iss
if errorlevel 1 goto :iscc_failed
echo [SUKSES] Installer dibuat di folder installer_output\
goto :summary

:no_iscc
echo [INFO] Inno Setup tidak terdeteksi.
echo Untuk membuat installer satu klik:
echo 1. Unduh Inno Setup gratis di: https://jrsoftware.org/isdl.php
echo 2. Buka file installer.iss lalu klik menu Build -^> Compile.
goto :summary

:iscc_failed
echo [ERROR] Kompilasi installer gagal. Periksa log di atas.
goto :summary

:summary
echo.
echo =======================================================
echo   PROSES BUILD SELESAI!
echo   Versi          : %APPVER%
echo   Folder Aplikasi: dist\AutoLandDigitizer\
echo   Executable     : dist\AutoLandDigitizer\AutoLandDigitizer.exe
echo   Paket Portable : dist\AutoLandDigitizer_Portable.zip
if defined ISCC echo   Installer      : installer_output\AutoLandDigitizer_Installer_v%APPVER%.exe
echo =======================================================

if /i not "%~1"=="--no-pause" pause
endlocal
exit /b 0

:no_python
echo [ERROR] Python tidak terdeteksi pada sistem ini.
pause
exit /b 1

:build_failed
echo [ERROR] Kompilasi gagal. Periksa log kesalahan di atas.
pause
exit /b 1
